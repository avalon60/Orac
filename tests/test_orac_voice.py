"""Tests for local Orac voice support.

# Author: Clive Bostock
# Date: 2026-05-04
# Description: Verifies local Piper voice path resolution and TTS queueing.
"""

from __future__ import annotations

from pathlib import Path
import asyncio
import contextlib
import io
import json
import os
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

if "langchain_openai" not in sys.modules:
  stub_module = types.ModuleType("langchain_openai")

  class _StubChatOpenAI:  # pragma: no cover - import shim for test isolation
    def __init__(self, *args, **kwargs):
      self.args = args
      self.kwargs = kwargs

    def invoke(self, prompt):
      return prompt

  stub_module.ChatOpenAI = _StubChatOpenAI
  sys.modules["langchain_openai"] = stub_module

if "oracledb" not in sys.modules:
  stub_oracledb = types.ModuleType("oracledb")

  class _StubConnection:
    pass

  class _StubDatabaseError(Exception):
    pass

  stub_oracledb.Connection = _StubConnection
  stub_oracledb.DatabaseError = _StubDatabaseError
  stub_oracledb.NUMBER = object()
  sys.modules["oracledb"] = stub_oracledb

from controller.orac import Orac
from lib.api_key_store import ApiKeyStore
from lib.config_mgr import ConfigManager
from model.network import OracListener
from orac_voice.activation import EnterActivationListener
from orac_voice.activation import VoiceActivationError
from orac_voice.activation import WakeWordActivationListener
from orac_voice.audio_capture import _normalise_input_device
from orac_voice.barge_in import BargeInConfig
from orac_voice.barge_in import BargeInController
from orac_voice.barge_in import BargeInResult
from orac_voice.barge_in import OpenWakeWordBargeInController
from orac_voice.barge_in import VAD_BARGE_IN_EXPERIMENTAL_WARNING
from orac_voice.barge_in import load_barge_in_config
from orac_voice.interruption_policy import InterruptionAction
from orac_voice.interruption_policy import InterruptionPolicy
from orac_voice.interruption_policy import InterruptionState
from orac_voice.wake_openwakeword import OpenWakeWordActivationListener
from orac_voice.wake_openwakeword import _best_detection
from orac_voice.wake_porcupine import PorcupineActivationListener
from orac_voice.stt_faster_whisper import FasterWhisperSttEngine
from orac_voice.stt_faster_whisper import _normalise_compute_type
from orac_voice.stt_faster_whisper import _normalise_device
from orac_voice.tts_coalescer import TtsChunkCoalescer
from orac_voice.tts_piper import PiperTtsEngine
from orac_voice.tts_worker import TtsWorker
from orac_voice.vad_silero import VadEndpointConfig, VadEndpointDetector
from orac_voice.audio_capture import VadCaptureResult
from orac_voice.voice_events import VoiceSttEnded, VoiceSttFinal
from orac_voice.voice_events import VoiceTurnComplete
from orac_voice.voice_events import VoiceVadSpeechEnded, VoiceVadTimeout
from orac_voice.wake_stt_phrase import SttPhraseWakeWordActivationListener
from orac_voice.wake_stt_phrase import _matches_wake_phrase
from orac_voice.voice_loop_local import _is_exit_phrase
from orac_voice.voice_loop_local import _create_activation_listener
from orac_voice.voice_loop_local import _create_barge_in_controller
from orac_voice.voice_loop_local import _load_activation_mode
from orac_voice.voice_loop_local import _load_record_mode
from orac_voice.voice_loop_local import _load_wake_rearm_seconds
from orac_voice.voice_loop_local import _send_orac_prompt
from orac_voice.voice_loop_local import _voice_session_async
from orac_voice.voice_loop_local import build_parser


class _FakeTtsEngine:
  """Fake TTS engine that records requested synthesis."""

  def __init__(self, wav_path: Path) -> None:
    self.wav_path = wav_path
    self.calls: list[tuple[str, str, str]] = []
    self.cancel_calls = 0
    self.block_event: threading.Event | None = None

  def synthesise_to_wav(
    self,
    text: str,
    *,
    session_id: str,
    turn_id: str,
  ) -> Path:
    """Record synthesis and return a fake WAV path."""
    self.calls.append((session_id, turn_id, text))
    if self.block_event is not None:
      self.block_event.wait(timeout=2.0)
    return self.wav_path

  def cancel(self) -> None:
    """Record cancellation."""
    self.cancel_calls += 1
    if self.block_event is not None:
      self.block_event.set()


class _FakePlayback:
  """Fake audio playback that records WAV paths."""

  def __init__(self) -> None:
    self.played: list[Path] = []
    self.cancel_calls = 0

  def play_wav(self, wav_path: Path) -> None:
    """Record one playback call."""
    self.played.append(wav_path)

  def cancel(self) -> None:
    """Record cancellation."""
    self.cancel_calls += 1


class _FakeDisplaySender:
  """Fake display sender that records requested states."""

  def __init__(self) -> None:
    self.states: list[tuple[str, str | None, str | None, str | None]] = []

  def send_state(
    self,
    state: str,
    *,
    message: str | None = None,
    session_id: str | None = None,
    turn_id: str | None = None,
  ) -> None:
    """Record a state change."""
    self.states.append((state, message, session_id, turn_id))

  def send(self, event) -> None:
    """Record a generic display event using the state-change form."""
    if isinstance(event, dict):
      state = str(event.get("state") or "")
      message = event.get("message")
      session_id = event.get("session_id")
      turn_id = event.get("turn_id")
      self.states.append((state, message, session_id, turn_id))
      return
    self.states.append(
      (
        getattr(event, "state", ""),
        getattr(event, "message", None),
        getattr(event, "session_id", None),
        getattr(event, "turn_id", None),
      )
    )


class _FakeVoiceWorker:
  """Fake voice worker used to verify stream routing."""

  def __init__(self) -> None:
    self.enqueued: list[tuple[str, str, str]] = []
    self.cancelled_sessions: list[str] = []
    self.cancelled_turns: list[tuple[str, str]] = []
    self.cleared_turns: list[tuple[str, str]] = []

  def enqueue_text(self, *, session_id: str, turn_id: str, text: str) -> bool:
    """Record queued text."""
    self.enqueued.append((session_id, turn_id, text))
    return True

  def cancel_turn(self, *, session_id: str, turn_id: str) -> int:
    """Record turn cancellation."""
    self.cancelled_turns.append((session_id, turn_id))
    return 0

  def clear_cancelled_turn(self, *, session_id: str, turn_id: str) -> None:
    """Record cleared turn cancellation state."""
    self.cleared_turns.append((session_id, turn_id))

  def cancel_session(self, *, session_id: str) -> int:
    """Record session cancellation."""
    self.cancelled_sessions.append(session_id)
    return 0


class _FakeActivationListener:
  """Fake activation listener used to exercise session lifecycle flow."""

  def __init__(self, results: list[types.SimpleNamespace]) -> None:
    self.results = results
    self.wait_calls = 0
    self.close_calls = 0

  def wait_for_activation(self, *, session_id: str):
    """Return the next configured activation result."""
    self.wait_calls += 1
    if self.results:
      return self.results.pop(0)
    return types.SimpleNamespace(activated=False, exit_requested=True)

  def close(self) -> None:
    """Record listener shutdown."""
    self.close_calls += 1


class _FakeNetworkOrchestrator:
  """Fake orchestrator for network listener cleanup tests."""

  def __init__(self) -> None:
    self.cancelled_sessions: list[str] = []
    self.cancelled_turns: list[tuple[str, str]] = []

  def cancel_voice_session(self, *, session_id: str) -> int:
    """Record an unexpected session-level cancellation."""
    self.cancelled_sessions.append(session_id)
    return 0

  def cancel_voice_turn(self, *, session_id: str, turn_id: str) -> int:
    """Record turn-level cancellation."""
    self.cancelled_turns.append((session_id, turn_id))
    return 0


class _FakeStreamWriter:
  """Minimal asyncio stream writer for voice client protocol tests."""

  def __init__(self) -> None:
    self.writes: list[bytes] = []
    self.close_calls = 0
    self.wait_closed_calls = 0
    self.closed = False

  def write(self, data: bytes) -> None:
    """Record bytes written by the client."""
    self.writes.append(data)

  async def drain(self) -> None:
    """Match the StreamWriter drain interface."""

  def close(self) -> None:
    """Record stream shutdown."""
    self.close_calls += 1
    self.closed = True

  async def wait_closed(self) -> None:
    """Match the StreamWriter close handshake."""
    self.wait_closed_calls += 1


class _FakeWakeCapture:
  """Fake capture layer for wake activation tests."""

  def __init__(self, result: VadCaptureResult) -> None:
    self.result = result
    self.cancel_calls = 0

  def record_until_silence_to_wav(self, **_kwargs) -> VadCaptureResult:
    """Return the configured fake VAD capture result."""
    return self.result

  def cancel(self) -> None:
    """Record cancellation."""
    self.cancel_calls += 1


class _FakeWakeStt:
  """Fake STT layer for wake activation tests."""

  def __init__(self, text: str) -> None:
    self.text = text
    self.calls: list[Path] = []

  def transcribe_wav(self, wav_path: Path) -> str:
    """Return configured recognised text."""
    self.calls.append(wav_path)
    return self.text


class _FakeOpenWakeWordModel:
  """Fake openWakeWord model for activation tests."""

  def __init__(self, predictions: list[dict[str, float]]) -> None:
    self.predictions = predictions
    self.calls: list[np.ndarray] = []

  def predict(self, audio: np.ndarray) -> dict[str, float]:
    """Return the next configured prediction dictionary."""
    self.calls.append(audio)
    if not self.predictions:
      return {}
    return self.predictions.pop(0)


class _FakeOpenWakeWordAudioSource:
  """Fake openWakeWord audio source for activation tests."""

  def __init__(self, *, frame_delay_seconds: float = 0.0) -> None:
    self.start_calls = 0
    self.close_calls = 0
    self.read_calls = 0
    self.frame_delay_seconds = frame_delay_seconds

  def start(self) -> None:
    """Record audio source startup."""
    self.start_calls += 1

  def read_frame(self) -> np.ndarray:
    """Return one fake 80 ms PCM frame."""
    self.read_calls += 1
    if self.frame_delay_seconds > 0:
      time.sleep(self.frame_delay_seconds)
    return np.zeros(1280, dtype=np.int16)

  def close(self) -> None:
    """Record audio source cleanup."""
    self.close_calls += 1


class _FakeApiKeyStore:
  """Fake API key store for Porcupine activation tests."""

  def __init__(self, value: str | None) -> None:
    self.value = value

  def get_api_key(self, resource_name: str) -> str:
    """Return or fail with a key-store-style error."""
    from lib.api_key_store import ApiKeyStoreError

    if self.value is None:
      raise ApiKeyStoreError(f"API key resource '{resource_name}' missing")
    return self.value


class _FakeBargeInVad:
  """Fake VAD engine with configured probabilities."""

  def __init__(self, probabilities: list[float]) -> None:
    self.probabilities = probabilities

  def speech_probability(self, _samples) -> float:
    """Return the next configured probability."""
    if not self.probabilities:
      return 0.0
    return self.probabilities.pop(0)


class _FakeBargeInSource:
  """Fake barge-in microphone source for unit tests."""

  def __init__(self, chunks: int = 10) -> None:
    self.chunks = chunks
    self.start_calls = 0
    self.close_calls = 0

  def start(self) -> None:
    """Record source startup."""
    self.start_calls += 1

  def read_chunk(self):
    """Return one fake audio chunk."""
    if self.chunks <= 0:
      time.sleep(0.01)
      return np.zeros(1, dtype=np.float32)
    self.chunks -= 1
    return np.zeros(1, dtype=np.float32)

  def close(self) -> None:
    """Record source cleanup."""
    self.close_calls += 1


class _FakeOpenWakeWordBargeInSource:
  """Fake openWakeWord barge-in microphone source for unit tests."""

  def __init__(self, frames: int = 10) -> None:
    self.frames = frames
    self.start_calls = 0
    self.close_calls = 0

  def start(self) -> None:
    """Record source startup."""
    self.start_calls += 1

  def read_frame(self):
    """Return one fake PCM frame."""
    if self.frames <= 0:
      time.sleep(0.01)
    else:
      self.frames -= 1
    return np.zeros(1280, dtype=np.int16)

  def close(self) -> None:
    """Record source cleanup."""
    self.close_calls += 1


class _FakeOpenWakeWordBargeInModel:
  """Fake openWakeWord model with configured predictions."""

  def __init__(self, predictions: list[dict[str, float]]) -> None:
    self.predictions = predictions

  def predict(self, _audio: np.ndarray) -> dict[str, float]:
    """Return the next configured prediction set."""
    if not self.predictions:
      return {}
    return self.predictions.pop(0)


class _ImmediateBargeInController:
  """Fake controller that interrupts as soon as monitoring starts."""

  def __init__(self) -> None:
    self.config = types.SimpleNamespace(return_mode="command_capture")
    self.interrupted = False
    self.start_calls = 0
    self.stop_calls = 0

  def reset_for_speech(self) -> None:
    """Match the real controller API."""

  def start(self, *, on_interrupt) -> None:
    """Immediately trigger interruption."""
    self.start_calls += 1
    self.interrupted = True
    on_interrupt(BargeInResult(speech_ms=250, return_mode="command_capture"))

  def stop(self) -> None:
    """Record stop calls."""
    self.stop_calls += 1

  def clear_interruption(self) -> None:
    """Clear the interruption flag."""
    self.interrupted = False


class _DelayedBargeInController:
  """Fake controller that interrupts after monitoring has already started."""

  def __init__(self, *, delay_seconds: float = 0.02) -> None:
    self.config = types.SimpleNamespace(
      return_mode="command_capture",
      post_response_ms=500,
      post_response_cancel_enabled=True,
    )
    self.delay_seconds = delay_seconds
    self.interrupted = False
    self.start_calls = 0
    self.stop_calls = 0
    self._timer: asyncio.TimerHandle | None = None

  def reset_for_speech(self) -> None:
    """Match the real controller API."""

  def start(self, *, on_interrupt) -> None:
    """Schedule an interruption after stream frames have been consumed."""
    self.start_calls += 1

    def _trigger() -> None:
      self.interrupted = True
      on_interrupt(BargeInResult(speech_ms=250, return_mode="command_capture"))

    loop = asyncio.get_running_loop()
    self._timer = loop.call_later(self.delay_seconds, _trigger)

  def stop(self) -> None:
    """Record stop calls and clean up any pending timer."""
    self.stop_calls += 1
    if self._timer is not None and not self.interrupted:
      self._timer.cancel()

  def clear_interruption(self) -> None:
    """Clear an ignored interruption."""
    self.interrupted = False


class _DisabledBargeInController:
  """Fake disabled controller that must never be started."""

  def __init__(self) -> None:
    self.config = types.SimpleNamespace(enabled=False)
    self.interrupted = False
    self.start_calls = 0
    self.stop_calls = 0
    self.reset_calls = 0

  def reset_for_speech(self) -> None:
    """Record an invalid reset attempt."""
    self.reset_calls += 1
    raise AssertionError("disabled barge-in must not reset for speech")

  def start(self, *, on_interrupt) -> None:
    """Record an invalid monitor start attempt."""
    del on_interrupt
    self.start_calls += 1
    raise AssertionError("disabled barge-in must not start")

  def stop(self) -> None:
    """Record an invalid monitor stop attempt."""
    self.stop_calls += 1
    raise AssertionError("disabled barge-in must not stop")


class OracVoiceTests(unittest.TestCase):
  """Tests for local voice support components."""

  def test_config_manager_resolves_orac_home_interpolation(self) -> None:
    """ConfigManager should resolve ${ORAC_HOME} from environment."""
    with patch.dict(os.environ, {"ORAC_HOME": str(PROJECT_ROOT)}, clear=False):
      config_mgr = ConfigManager(
        config_file_path=PROJECT_ROOT / "resources" / "config" / "orac.ini"
      )
      voice_dir = config_mgr.path_config_value(
        "voice",
        "tts_voice_dir",
        suppress_warnings=True,
      )

    self.assertEqual(voice_dir, PROJECT_ROOT / "var" / "voices" / "piper")

  def test_audio_capture_normalises_configured_input_device(self) -> None:
    """Input device config should support default, numeric, and named devices."""
    self.assertIsNone(_normalise_input_device("default"))
    self.assertIsNone(_normalise_input_device("  "))
    self.assertEqual(_normalise_input_device("2"), 2)
    self.assertEqual(_normalise_input_device("USB Microphone"), "USB Microphone")

  def test_stt_auto_settings_resolve_to_safe_cpu_defaults(self) -> None:
    """STT auto config should avoid accidental CUDA selection."""
    self.assertEqual(_normalise_device("auto"), "cpu")
    self.assertEqual(_normalise_device(""), "cpu")
    self.assertEqual(_normalise_device("cuda"), "cuda")
    self.assertEqual(_normalise_compute_type("auto"), "int8")
    self.assertEqual(_normalise_compute_type(""), "int8")
    self.assertEqual(_normalise_compute_type("float32"), "float32")

  def test_voice_session_cli_mode_is_available(self) -> None:
    """Voice session mode should be exposed by the local voice CLI parser."""
    args = build_parser().parse_args(["--voice-session", "--record-seconds", "10"])

    self.assertTrue(args.voice_session)
    self.assertEqual(args.record_seconds, 10)

  def test_voice_cli_accepts_record_mode_override(self) -> None:
    """Voice CLI should expose fixed and VAD recording modes."""
    fixed_args = build_parser().parse_args(
      ["--listen-once", "--record-mode", "fixed"]
    )
    vad_args = build_parser().parse_args(
      ["--listen-once", "--record-mode", "vad"]
    )

    self.assertEqual(_load_record_mode(fixed_args), "fixed")
    self.assertEqual(_load_record_mode(vad_args), "vad")

  def test_voice_cli_accepts_activation_mode_override(self) -> None:
    """Voice CLI should expose the activation layer mode override."""
    args = build_parser().parse_args(
      ["--voice-session", "--activation-mode", "enter"]
    )

    self.assertEqual(_load_activation_mode(args), "enter")

  def test_enter_activation_listener_activates_on_enter(self) -> None:
    """Enter activation should preserve the current press-to-speak flow."""
    listener = EnterActivationListener(exit_phrases={"exit", "quit"})

    with patch("builtins.input", return_value=""):
      result = listener.wait_for_activation(session_id="s1")

    self.assertTrue(result.activated)
    self.assertFalse(result.exit_requested)

  def test_enter_activation_listener_exits_on_typed_exit(self) -> None:
    """Enter activation should close cleanly on typed exit phrases."""
    listener = EnterActivationListener(exit_phrases={"exit", "quit"})

    with patch("builtins.input", return_value="exit"):
      result = listener.wait_for_activation(session_id="s1")

    self.assertFalse(result.activated)
    self.assertTrue(result.exit_requested)

  def test_wake_word_activation_fails_clearly_without_engine(self) -> None:
    """Wake-word mode should not silently fall back to Enter mode."""
    listener = WakeWordActivationListener(
      wake_engine="none",
      wake_phrase="orac",
      wake_model="",
      wake_threshold=0.6,
    )

    with self.assertRaises(VoiceActivationError) as raised:
      listener.wait_for_activation(session_id="s1")

    self.assertIn("requires a supported wake_engine", str(raised.exception))

  def test_activation_factory_builds_openwakeword_listener(self) -> None:
    """Configured openWakeWord mode should use the real wake listener."""
    args = build_parser().parse_args(
      ["--voice-session", "--activation-mode", "openwakeword"]
    )

    listener = _create_activation_listener(
      args=args,
      exit_phrases={"exit"},
      capture=_FakeWakeCapture(VadCaptureResult(wav_path=Path("/tmp/wake.wav"))),
      stt_engine=_FakeWakeStt("orac"),
    )

    self.assertIsInstance(listener, OpenWakeWordActivationListener)

  def test_openwakeword_activation_reports_missing_dependency(self) -> None:
    """openWakeWord mode should fail clearly when dependency is unavailable."""
    listener = OpenWakeWordActivationListener(
      model_names=["hey_jarvis"],
      audio_source=_FakeOpenWakeWordAudioSource(),
    )

    with patch.dict(sys.modules, {"openwakeword": None}):
      with self.assertRaises(VoiceActivationError) as raised:
        listener.wait_for_activation(session_id="s1")

    self.assertIn("requires the openwakeword package", str(raised.exception))

  def test_openwakeword_activation_requires_a_usable_model(self) -> None:
    """openWakeWord mode should require explicit paths or model names."""
    listener = OpenWakeWordActivationListener(
      model_paths=[],
      model_names=[],
      audio_source=_FakeOpenWakeWordAudioSource(),
    )

    with self.assertRaises(VoiceActivationError) as raised:
      listener.wait_for_activation(session_id="s1")

    self.assertIn("requires openwakeword_model_paths", str(raised.exception))

  def test_openwakeword_detection_returns_model_score_details(self) -> None:
    """Simulated openWakeWord detection should include result metadata."""
    audio_source = _FakeOpenWakeWordAudioSource()
    model = _FakeOpenWakeWordModel([{"hey_jarvis": 0.72}])
    listener = OpenWakeWordActivationListener(
      model_names=["hey_jarvis"],
      threshold=0.5,
      audio_source=audio_source,
      model_factory=lambda: model,
      refractory_seconds=0.0,
    )

    with contextlib.redirect_stdout(io.StringIO()):
      result = listener.wait_for_activation(session_id="s1")

    self.assertTrue(result.activated)
    self.assertEqual(result.backend, "openwakeword")
    self.assertEqual(result.wake_engine, "openwakeword")
    self.assertEqual(result.wake_word, "hey_jarvis")
    self.assertEqual(result.model, "hey_jarvis")
    self.assertEqual(result.score, 0.72)
    self.assertIsNotNone(result.timestamp)
    self.assertEqual(audio_source.start_calls, 1)
    self.assertEqual(audio_source.close_calls, 1)
    self.assertEqual(len(model.calls), 1)

  def test_openwakeword_ignores_scores_below_threshold(self) -> None:
    """openWakeWord should avoid activation below the configured threshold."""
    model_name, score = _best_detection({"hey_jarvis": 0.62}, 0.75)

    self.assertIsNone(model_name)
    self.assertIsNone(score)

  def test_openwakeword_refractory_guard_ignores_first_detection(self) -> None:
    """Re-arm guard should ignore immediate detections after listener start."""
    audio_source = _FakeOpenWakeWordAudioSource(frame_delay_seconds=0.02)
    model = _FakeOpenWakeWordModel([
      {"hey_jarvis": 0.9},
      {"hey_jarvis": 0.9},
    ])
    listener = OpenWakeWordActivationListener(
      model_names=["hey_jarvis"],
      threshold=0.75,
      audio_source=audio_source,
      model_factory=lambda: model,
      refractory_seconds=0.03,
    )

    with contextlib.redirect_stdout(io.StringIO()):
      result = listener.wait_for_activation(session_id="s1")

    self.assertTrue(result.activated)
    self.assertGreaterEqual(len(model.calls), 2)

  def test_openwakeword_multiple_models_identifies_firing_model(self) -> None:
    """Multiple configured models should report the highest firing score."""
    model_name, score = _best_detection(
      {"hey_jarvis": 0.42, "hey_orac": 0.91},
      0.5,
    )

    self.assertEqual(model_name, "hey_orac")
    self.assertEqual(score, 0.91)

  def test_openwakeword_activation_does_not_use_stt(self) -> None:
    """Real wake-word activation should not transcribe during activation."""
    stt_engine = _FakeWakeStt("orac")
    audio_source = _FakeOpenWakeWordAudioSource()
    listener = OpenWakeWordActivationListener(
      model_names=["hey_jarvis"],
      threshold=0.5,
      audio_source=audio_source,
      model_factory=lambda: _FakeOpenWakeWordModel([{"hey_jarvis": 0.8}]),
      refractory_seconds=0.0,
    )

    with contextlib.redirect_stdout(io.StringIO()):
      result = listener.wait_for_activation(session_id="s1")

    self.assertTrue(result.activated)
    self.assertEqual(stt_engine.calls, [])

  def test_wake_rearm_delay_uses_configured_default(self) -> None:
    """Voice sessions should pause briefly before listening again."""
    self.assertGreaterEqual(_load_wake_rearm_seconds(), 0.0)

  def test_porcupine_activation_reports_missing_dependency(self) -> None:
    """Porcupine mode should fail clearly when dependency is unavailable."""
    listener = PorcupineActivationListener(
      builtin_keyword="porcupine",
      key_store=_FakeApiKeyStore("secret-value"),
    )

    with patch.dict(sys.modules, {"pvporcupine": None}):
      with self.assertRaises(VoiceActivationError) as raised:
        listener.wait_for_activation(session_id="s1")

    self.assertIn("requires the pvporcupine package", str(raised.exception))
    self.assertNotIn("secret-value", str(raised.exception))

  def test_porcupine_activation_reports_missing_access_key(self) -> None:
    """Porcupine mode should fail clearly when AccessKey is missing."""
    fake_module = types.SimpleNamespace(
      KEYWORDS={"porcupine"},
      create=lambda **_kwargs: object(),
    )
    listener = PorcupineActivationListener(
      builtin_keyword="porcupine",
      key_store=_FakeApiKeyStore(None),
    )

    with patch.dict(sys.modules, {"pvporcupine": fake_module}):
      with self.assertRaises(VoiceActivationError) as raised:
        listener.wait_for_activation(session_id="s1")

    message = str(raised.exception)
    self.assertIn("Picovoice AccessKey is missing", message)
    self.assertNotIn("secret-value", message)

  def test_porcupine_activation_reports_incomplete_access_key(self) -> None:
    """Porcupine mode should reject obviously incomplete AccessKeys."""
    fake_module = types.SimpleNamespace(
      KEYWORDS={"porcupine"},
      create=lambda **_kwargs: object(),
    )
    listener = PorcupineActivationListener(
      builtin_keyword="porcupine",
      key_store=_FakeApiKeyStore("short-key"),
    )

    with patch.dict(sys.modules, {"pvporcupine": fake_module}):
      with self.assertRaises(VoiceActivationError) as raised:
        listener.wait_for_activation(session_id="s1")

    message = str(raised.exception)
    self.assertIn("looks incomplete", message)
    self.assertNotIn("short-key", message)

  def test_porcupine_activation_requires_keyword_configuration(self) -> None:
    """Porcupine mode should require a custom or built-in keyword."""
    fake_module = types.SimpleNamespace(
      KEYWORDS={"porcupine"},
      create=lambda **_kwargs: object(),
    )
    listener = PorcupineActivationListener(
      key_store=_FakeApiKeyStore("long-enough-secret-value")
    )

    with patch.dict(sys.modules, {"pvporcupine": fake_module}):
      with self.assertRaises(VoiceActivationError) as raised:
        listener.wait_for_activation(session_id="s1")

    message = str(raised.exception)
    self.assertIn("requires porcupine_keyword_path", message)
    self.assertNotIn("secret-value", message)

  def test_api_key_store_round_trips_encrypted_key(self) -> None:
    """API key store should persist encrypted keys outside orac.ini."""
    with tempfile.TemporaryDirectory() as tmp_name:
      store_path = Path(tmp_name) / "api_keys.ini"
      store = ApiKeyStore(store_path=store_path)
      store.set_api_key("picovoice/access_key", "secret-value")

      stored_text = store_path.read_text(encoding="utf-8")
      recovered = ApiKeyStore(store_path=store_path).get_api_key(
        "picovoice/access_key"
      )

    self.assertEqual(recovered, "secret-value")
    self.assertNotIn("secret-value", stored_text)

  def test_activation_factory_builds_porcupine_listener(self) -> None:
    """Configured Porcupine mode should use the production listener."""
    args = build_parser().parse_args(
      ["--voice-session", "--activation-mode", "porcupine"]
    )

    listener = _create_activation_listener(
      args=args,
      exit_phrases={"exit"},
      capture=_FakeWakeCapture(VadCaptureResult(wav_path=Path("/tmp/wake.wav"))),
      stt_engine=_FakeWakeStt("orac"),
    )

    self.assertIsInstance(listener, PorcupineActivationListener)

  def test_stt_phrase_wake_activation_detects_configured_phrase(self) -> None:
    """Experimental STT phrase wake listener should activate on phrase match."""
    wav_path = Path("/tmp/orac_voice/wake.wav")
    capture = _FakeWakeCapture(VadCaptureResult(wav_path=wav_path))
    stt_engine = _FakeWakeStt("Hello Oracle.")
    listener = SttPhraseWakeWordActivationListener(
      wake_phrase="orac,oracle",
      capture=capture,
      stt_engine=stt_engine,
    )

    with contextlib.redirect_stdout(io.StringIO()):
      result = listener.wait_for_activation(session_id="s1")

    self.assertTrue(result.activated)
    self.assertEqual(result.wake_engine, "stt_phrase")
    self.assertEqual(stt_engine.calls, [wav_path])

  def test_stt_phrase_wake_activation_ignores_non_matching_phrase(self) -> None:
    """Experimental wake listener should ignore unrelated recognised text."""
    wav_path = Path("/tmp/orac_voice/wake.wav")
    listener = SttPhraseWakeWordActivationListener(
      wake_phrase="orac",
      capture=_FakeWakeCapture(VadCaptureResult(wav_path=wav_path)),
      stt_engine=_FakeWakeStt("background speech"),
    )

    with contextlib.redirect_stdout(io.StringIO()):
      result = listener.wait_for_activation(session_id="s1")

    self.assertFalse(result.activated)
    self.assertFalse(result.exit_requested)

  def test_stt_phrase_wake_activation_handles_no_speech_timeout(self) -> None:
    """No wake speech should return a non-activated result."""
    listener = SttPhraseWakeWordActivationListener(
      wake_phrase="orac",
      capture=_FakeWakeCapture(
        VadCaptureResult(wav_path=None, no_speech_timeout=True)
      ),
      stt_engine=_FakeWakeStt(""),
    )

    with contextlib.redirect_stdout(io.StringIO()):
      result = listener.wait_for_activation(session_id="s1")

    self.assertFalse(result.activated)
    self.assertFalse(result.exit_requested)

  def test_stt_phrase_matching_respects_word_boundaries(self) -> None:
    """Wake phrase matching should avoid substring-only false positives."""
    self.assertTrue(_matches_wake_phrase("hello orac", {"orac"}))
    self.assertFalse(_matches_wake_phrase("thoracic", {"orac"}))

  def test_stt_phrase_matching_accepts_common_orac_variants(self) -> None:
    """Wake phrase matching should tolerate common STT variants."""
    self.assertTrue(_matches_wake_phrase("hey orack", {"orac"}))
    self.assertTrue(_matches_wake_phrase("aurok are you there", {"orac"}))
    self.assertTrue(_matches_wake_phrase("ora could you help", {"orac"}))

  def test_activation_factory_builds_stt_phrase_listener(self) -> None:
    """Configured stt_phrase wake engine should use the experimental listener."""
    args = build_parser().parse_args(
      ["--voice-session", "--activation-mode", "stt_phrase"]
    )
    capture = _FakeWakeCapture(VadCaptureResult(wav_path=Path("/tmp/wake.wav")))
    stt_engine = _FakeWakeStt("orac")

    listener = _create_activation_listener(
      args=args,
      exit_phrases={"exit"},
      capture=capture,
      stt_engine=stt_engine,
    )

    self.assertIsInstance(listener, SttPhraseWakeWordActivationListener)

  def test_voice_session_exit_phrase_matching_is_punctuation_tolerant(self) -> None:
    """Recognised exit phrases should support common trailing punctuation."""
    phrases = {"exit", "quit", "stop listening", "goodbye"}

    self.assertTrue(_is_exit_phrase("Goodbye.", phrases))
    self.assertTrue(_is_exit_phrase(" stop listening! ", phrases))
    self.assertFalse(_is_exit_phrase("goodbye for now", phrases))
    self.assertFalse(_is_exit_phrase("Stay state.", phrases))

  def test_stt_voice_events_are_serialisable(self) -> None:
    """STT events should convert paths and timestamps into JSON-friendly values."""
    wav_path = Path("/tmp/orac_voice/capture.wav")
    ended = VoiceSttEnded(session_id="s1", turn_id="t1", wav_path=wav_path)
    final = VoiceSttFinal(session_id="s1", turn_id="t1", text="hello")

    self.assertEqual(ended.to_dict()["wav_path"], str(wav_path))
    self.assertEqual(final.to_dict()["text"], "hello")

  def test_vad_voice_events_are_serialisable(self) -> None:
    """VAD events should serialise endpoint metadata cleanly."""
    timeout = VoiceVadTimeout(
      session_id="s1",
      turn_id="t1",
      initial_timeout_seconds=3.0,
    )
    ended = VoiceVadSpeechEnded(
      session_id="s1",
      turn_id="t1",
      duration_seconds=1.25,
      max_duration_reached=False,
    )

    self.assertEqual(timeout.to_dict()["initial_timeout_seconds"], 3.0)
    self.assertEqual(ended.to_dict()["duration_seconds"], 1.25)

  def test_vad_endpoint_detector_stops_after_silence(self) -> None:
    """VAD detector should start on speech and end after configured silence."""
    detector = VadEndpointDetector(
      config=VadEndpointConfig(
        chunk_ms=100,
        min_speech_ms=200,
        min_silence_ms=300,
        min_record_seconds=0.2,
        initial_timeout_seconds=2.0,
        max_record_seconds=5.0,
      )
    )

    self.assertFalse(detector.process_probability(0.8).speech_started)
    self.assertTrue(detector.process_probability(0.8).speech_started)
    self.assertFalse(detector.process_probability(0.1).speech_ended)
    self.assertFalse(detector.process_probability(0.1).speech_ended)
    self.assertTrue(detector.process_probability(0.1).speech_ended)

  def test_vad_endpoint_detector_times_out_before_speech(self) -> None:
    """VAD detector should report no-speech timeout before a false prompt."""
    detector = VadEndpointDetector(
      config=VadEndpointConfig(
        chunk_ms=100,
        min_speech_ms=200,
        initial_timeout_seconds=0.3,
        max_record_seconds=5.0,
      )
    )

    self.assertFalse(detector.process_probability(0.0).no_speech_timeout)
    self.assertFalse(detector.process_probability(0.0).no_speech_timeout)
    self.assertTrue(detector.process_probability(0.0).no_speech_timeout)

  def test_barge_in_ignores_speech_during_initial_grace_period(self) -> None:
    """Barge-in VAD should ignore speech during configured startup grace."""
    controller = BargeInController(
      config=BargeInConfig(
        enable_experimental_barge_in=True,
        chunk_ms=100,
        min_speech_ms=200,
        grace_ms=500,
        ignore_during_tts_start_ms=300,
      ),
      audio_source=_FakeBargeInSource(),
      vad_engine=_FakeBargeInVad([]),
    )
    controller.reset_for_speech(now=100.0)

    result = controller.process_probability(1.0, now=100.2)

    self.assertIsNone(result)
    self.assertFalse(controller.interrupted)

  def test_barge_in_triggers_after_grace_and_minimum_speech(self) -> None:
    """Barge-in VAD should interrupt after enough post-grace speech."""
    controller = BargeInController(
      config=BargeInConfig(
        enable_experimental_barge_in=True,
        chunk_ms=100,
        min_speech_ms=200,
        grace_ms=100,
        ignore_during_tts_start_ms=100,
      ),
      audio_source=_FakeBargeInSource(),
      vad_engine=_FakeBargeInVad([]),
    )
    controller.reset_for_speech(now=100.0)

    first = controller.process_probability(1.0, now=100.2)
    second = controller.process_probability(1.0, now=100.3)

    self.assertIsNone(first)
    self.assertIsNotNone(second)
    self.assertTrue(controller.interrupted)
    self.assertEqual(second.return_mode, "command_capture")

  def test_barge_in_disabled_does_not_start_monitoring(self) -> None:
    """Disabled barge-in should leave microphone monitoring inactive."""
    source = _FakeBargeInSource()
    controller = BargeInController(
      config=BargeInConfig(enable_experimental_barge_in=False),
      audio_source=source,
      vad_engine=_FakeBargeInVad([1.0]),
    )

    controller.start()
    controller.stop()

    self.assertEqual(source.start_calls, 0)

  def test_openwakeword_barge_in_ignores_non_wake_speech(self) -> None:
    """Wake-word barge-in should ignore predictions below threshold."""
    controller = OpenWakeWordBargeInController(
      config=BargeInConfig(
        enable_experimental_barge_in=True,
        mode="openwakeword",
        grace_ms=100,
        ignore_during_tts_start_ms=100,
        openwakeword_threshold=0.75,
      ),
      audio_source=_FakeOpenWakeWordBargeInSource(),
      model_factory=lambda: _FakeOpenWakeWordBargeInModel([]),
    )
    controller.reset_for_speech(now=100.0)

    result = controller.process_predictions({"hey_jarvis": 0.2}, now=100.2)

    self.assertIsNone(result)
    self.assertFalse(controller.interrupted)

  def test_openwakeword_barge_in_detects_wake_word(self) -> None:
    """Wake-word barge-in should interrupt when a model crosses threshold."""
    controller = OpenWakeWordBargeInController(
      config=BargeInConfig(
        enable_experimental_barge_in=True,
        mode="openwakeword",
        grace_ms=100,
        ignore_during_tts_start_ms=100,
        openwakeword_threshold=0.75,
        return_mode="wake_listening",
      ),
      audio_source=_FakeOpenWakeWordBargeInSource(),
      model_factory=lambda: _FakeOpenWakeWordBargeInModel([]),
    )
    controller.reset_for_speech(now=100.0)

    result = controller.process_predictions({"hey_jarvis": 0.92}, now=100.2)

    self.assertIsNotNone(result)
    self.assertTrue(controller.interrupted)
    self.assertEqual(result.return_mode, "wake_listening")
    self.assertIn("hey_jarvis", result.reason)

  def test_barge_in_factory_returns_none_when_disabled(self) -> None:
    """Disabled barge-in config should not construct a controller."""
    with patch(
      "orac_voice.voice_loop_local.load_barge_in_config",
      return_value=BargeInConfig(enable_experimental_barge_in=False),
    ):
      with patch(
        "orac_voice.voice_loop_local.BargeInController"
      ) as controller_cls:
        controller = _create_barge_in_controller()

    self.assertIsNone(controller)
    controller_cls.assert_not_called()

  def test_default_voice_config_keeps_barge_in_disabled(self) -> None:
    """The repository voice config should keep barge-in disabled by default."""
    config_mgr = ConfigManager(
      config_file_path=PROJECT_ROOT / "resources" / "config" / "orac.ini"
    )
    config = load_barge_in_config(config_mgr)

    self.assertFalse(config.enable_experimental_barge_in)

  def test_legacy_barge_in_keys_map_to_experimental_flag(self) -> None:
    """Legacy keys should still map onto the single experimental flag."""
    with tempfile.TemporaryDirectory() as tmp_name:
      config_path = Path(tmp_name) / "orac.ini"
      config_path.write_text(
        "\n".join(
          [
            "[voice]",
            "barge_in_enabled = true",
            "barge_in_mode = vad",
            "barge_in_acknowledge_self_trigger_risk = true",
          ]
        ),
        encoding="utf-8",
      )
      config_mgr = ConfigManager(config_file_path=config_path)
      config = load_barge_in_config(config_mgr)

    self.assertTrue(config.enable_experimental_barge_in)

  def test_barge_in_controller_starts_vad_with_acknowledgement(self) -> None:
    """Enabled experimental VAD mode should start the monitoring thread."""
    source = _FakeBargeInSource(chunks=1)
    controller = BargeInController(
      config=BargeInConfig(
        enable_experimental_barge_in=True,
        mode="vad",
      ),
      audio_source=source,
      vad_engine=_FakeBargeInVad([0.0]),
    )

    controller.start()
    time.sleep(0.05)
    controller.stop()

    self.assertGreaterEqual(source.start_calls, 1)
    self.assertGreaterEqual(source.close_calls, 1)

  def test_barge_in_factory_enables_experimental_controller(self) -> None:
    """Enabled experimental barge-in should construct a controller."""
    config = BargeInConfig(enable_experimental_barge_in=True, mode="vad")
    with patch(
      "orac_voice.voice_loop_local.load_barge_in_config",
      return_value=config,
    ):
      with patch("orac_voice.voice_loop_local.logger.warning") as warning_mock:
        controller = _create_barge_in_controller()

    self.assertIsInstance(controller, BargeInController)
    warning_mock.assert_called_once_with(VAD_BARGE_IN_EXPERIMENTAL_WARNING)

  def test_barge_in_factory_keeps_disabled_barge_in_silent(self) -> None:
    """Disabled experimental barge-in should not warn or construct."""
    config = BargeInConfig(
      enable_experimental_barge_in=False,
      mode="vad",
    )
    with patch(
      "orac_voice.voice_loop_local.load_barge_in_config",
      return_value=config,
    ):
      with patch("orac_voice.voice_loop_local.logger.warning") as warning_mock:
        with patch(
          "orac_voice.voice_loop_local.BargeInController"
        ) as controller_cls:
          controller = _create_barge_in_controller()

    self.assertIsNone(controller)
    controller_cls.assert_not_called()
    warning_mock.assert_not_called()

  def test_interruption_policy_ignores_vad_blip_during_speaking(self) -> None:
    """Short acoustic blips should not force an interruption."""
    policy = InterruptionPolicy(
      allow_interruptions=True,
      min_speech_ms=250,
    )
    policy.begin_output_turn(output_turn_id="turn-1")

    decision = policy.consider_acoustic_interrupt(
      output_turn_id="turn-1",
      speech_ms=100,
    )

    self.assertEqual(decision.action, InterruptionAction.IGNORE)
    self.assertEqual(decision.reason, "speech below interruption threshold")
    self.assertEqual(policy.state, InterruptionState.SPEAKING)
    self.assertTrue(policy.accept_output_event(output_turn_id="turn-1"))

  def test_interruption_policy_respects_allow_interruptions(self) -> None:
    """Disabled interruptions should leave the speaking turn untouched."""
    policy = InterruptionPolicy(
      allow_interruptions=False,
      min_speech_ms=100,
    )
    policy.begin_output_turn(output_turn_id="turn-1")

    decision = policy.consider_acoustic_interrupt(
      output_turn_id="turn-1",
      speech_ms=500,
    )

    self.assertEqual(decision.action, InterruptionAction.IGNORE)
    self.assertEqual(decision.reason, "interruptions disabled")
    self.assertEqual(policy.state, InterruptionState.SPEAKING)

  def test_interruption_policy_false_interrupt_pauses_then_resumes(self) -> None:
    """Short recognised output should pause and then resume semantically."""
    policy = InterruptionPolicy(
      allow_interruptions=True,
      min_speech_ms=100,
      min_recognised_words=3,
      resume_false_interruption_enabled=True,
    )
    policy.begin_output_turn(output_turn_id="turn-1")

    decision = policy.consider_acoustic_interrupt(
      output_turn_id="turn-1",
      speech_ms=150,
      recognised_text="yes",
    )
    resumed = policy.resume_false_interruption(output_turn_id="turn-1")

    self.assertEqual(decision.action, InterruptionAction.PAUSE)
    self.assertEqual(decision.reason, "false interruption; waiting to resume")
    self.assertEqual(policy.state, InterruptionState.SPEAKING)
    self.assertEqual(resumed.action, InterruptionAction.RESUME)
    self.assertEqual(resumed.reason, "false interruption resumed")

  def test_interruption_policy_confirmed_interrupt_closes_output_turn(
    self,
  ) -> None:
    """A confirmed interruption should close the active output turn."""
    policy = InterruptionPolicy(
      allow_interruptions=True,
      min_speech_ms=100,
    )
    policy.begin_output_turn(output_turn_id="turn-1")

    decision = policy.consider_acoustic_interrupt(
      output_turn_id="turn-1",
      speech_ms=200,
      recognised_text="cancel that",
    )

    self.assertEqual(decision.action, InterruptionAction.INTERRUPT)
    self.assertEqual(policy.state, InterruptionState.INTERRUPTED)
    self.assertFalse(policy.accept_output_event(output_turn_id="turn-1"))

  def test_interruption_policy_ignores_late_playback_complete_after_interrupt(
    self,
  ) -> None:
    """Late playback completion should be ignored after interruption."""
    policy = InterruptionPolicy(
      allow_interruptions=True,
      min_speech_ms=100,
    )
    policy.begin_output_turn(output_turn_id="turn-1")
    policy.consider_acoustic_interrupt(
      output_turn_id="turn-1",
      speech_ms=200,
    )

    self.assertFalse(policy.mark_output_finished(output_turn_id="turn-1"))
    self.assertEqual(policy.state, InterruptionState.INTERRUPTED)

  def test_interruption_policy_duplicate_interruptions_are_idempotent(
    self,
  ) -> None:
    """Repeated interruption events for one turn should be ignored."""
    policy = InterruptionPolicy(
      allow_interruptions=True,
      min_speech_ms=100,
    )
    policy.begin_output_turn(output_turn_id="turn-1")

    first = policy.consider_acoustic_interrupt(
      output_turn_id="turn-1",
      speech_ms=200,
    )
    second = policy.consider_acoustic_interrupt(
      output_turn_id="turn-1",
      speech_ms=220,
    )

    self.assertEqual(first.action, InterruptionAction.INTERRUPT)
    self.assertEqual(second.action, InterruptionAction.IGNORE)
    self.assertTrue(second.is_duplicate)

  def test_piper_engine_uses_configured_runtime_output_directory(self) -> None:
    """Piper should write generated WAV files below ORAC_HOME/var/tmp."""
    with tempfile.TemporaryDirectory() as tmp_name:
      tmp_root = Path(tmp_name)
      voice_dir = tmp_root / "voices"
      voice_dir.mkdir()
      model_path = voice_dir / "test_voice.onnx"
      model_path.write_bytes(b"fake model")
      piper_bin = tmp_root / "piper"
      piper_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
      piper_bin.chmod(0o755)

      with patch.dict(os.environ, {"ORAC_HOME": str(tmp_root)}, clear=False):
        engine = PiperTtsEngine(
          config_file_path=PROJECT_ROOT / "resources" / "config" / "orac.ini",
          voice_name="test_voice",
          voice_dir=voice_dir,
          piper_bin=piper_bin,
        )

    self.assertEqual(engine.output_dir, tmp_root / "var" / "tmp" / "orac_voice")

  def test_piper_synthesis_returns_generated_wav_path(self) -> None:
    """Piper wrapper should return the WAV path created by subprocess."""
    with tempfile.TemporaryDirectory() as tmp_name:
      tmp_root = Path(tmp_name)
      voice_dir = tmp_root / "voices"
      voice_dir.mkdir()
      (voice_dir / "test_voice.onnx").write_bytes(b"fake model")
      piper_bin = tmp_root / "piper"
      piper_bin.write_text(
        "#!/bin/sh\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  if [ \"$1\" = \"--output_file\" ]; then\n"
        "    shift\n"
        "    printf RIFFfake > \"$1\"\n"
        "  fi\n"
        "  shift\n"
        "done\n"
        "cat >/dev/null\n",
        encoding="utf-8",
      )
      piper_bin.chmod(0o755)

      with patch.dict(os.environ, {"ORAC_HOME": str(tmp_root)}, clear=False):
        engine = PiperTtsEngine(
          config_file_path=PROJECT_ROOT / "resources" / "config" / "orac.ini",
          voice_name="test_voice",
          voice_dir=voice_dir,
          piper_bin=piper_bin,
        )
        wav_path = engine.synthesise_to_wav(
          "Hello.",
          session_id="session1",
          turn_id="turn1",
        )

    self.assertTrue(str(wav_path).endswith(".wav"))

  def test_faster_whisper_engine_reuses_loaded_model(self) -> None:
    """STT wrapper should use the cached model for transcription."""

    class _FakeWhisperModel:
      def __init__(self) -> None:
        self.calls = 0

      def transcribe(self, wav_path: str, **_kwargs):
        self.calls += 1
        return [
          types.SimpleNamespace(text=" Hello "),
          types.SimpleNamespace(text=" Orac. "),
        ], object()

    with tempfile.TemporaryDirectory() as tmp_name:
      tmp_root = Path(tmp_name)
      wav_path = tmp_root / "speech.wav"
      wav_path.write_bytes(b"RIFFfake")
      with patch.dict(os.environ, {"ORAC_HOME": str(PROJECT_ROOT)}, clear=False):
        engine = FasterWhisperSttEngine(
          config_file_path=PROJECT_ROOT / "resources" / "config" / "orac.ini",
        )
      fake_model = _FakeWhisperModel()
      engine._model = fake_model

      text = engine.transcribe_wav(wav_path)
      second_text = engine.transcribe_wav(wav_path)

    self.assertEqual(text, "Hello Orac.")
    self.assertEqual(second_text, "Hello Orac.")
    self.assertEqual(fake_model.calls, 2)

  def test_tts_worker_enqueue_does_not_block_caller(self) -> None:
    """TTS worker should queue text and process it in the background."""
    with tempfile.TemporaryDirectory() as tmp_name:
      wav_path = Path(tmp_name) / "out.wav"
      wav_path.write_bytes(b"RIFFfake")
      tts_engine = _FakeTtsEngine(wav_path=wav_path)
      playback = _FakePlayback()
      worker = TtsWorker(tts_engine=tts_engine, audio_playback=playback)
      worker.start()
      started = time.perf_counter()
      queued = worker.enqueue_text(
        session_id="s1",
        turn_id="t1",
        text="Hello there.",
      )
      elapsed = time.perf_counter() - started
      drained = worker.wait_until_idle(timeout=2.0)
      worker.stop()

    self.assertTrue(queued)
    self.assertLess(elapsed, 0.1)
    self.assertTrue(drained)
    self.assertEqual(tts_engine.calls, [("s1", "t1", "Hello there.")])
    self.assertEqual(playback.played, [wav_path])

  def test_tts_worker_skips_punctuation_only_chunks(self) -> None:
    """TTS worker should not queue chunks that Piper cannot speak usefully."""
    with tempfile.TemporaryDirectory() as tmp_name:
      wav_path = Path(tmp_name) / "out.wav"
      wav_path.write_bytes(b"RIFFfake")
      tts_engine = _FakeTtsEngine(wav_path=wav_path)
      playback = _FakePlayback()
      worker = TtsWorker(tts_engine=tts_engine, audio_playback=playback)

      slash_queued = worker.enqueue_text(
        session_id="s1",
        turn_id="t1",
        text="/",
      )
      dash_queued = worker.enqueue_text(
        session_id="s1",
        turn_id="t1",
        text="...",
      )
      word_queued = worker.enqueue_text(
        session_id="s1",
        turn_id="t1",
        text="Act I.",
      )

    self.assertFalse(slash_queued)
    self.assertFalse(dash_queued)
    self.assertTrue(word_queued)

  def test_tts_worker_removes_markdown_markers_before_speech(self) -> None:
    """TTS worker should not ask Piper to read Markdown emphasis markers."""
    with tempfile.TemporaryDirectory() as tmp_name:
      wav_path = Path(tmp_name) / "out.wav"
      wav_path.write_bytes(b"RIFFfake")
      tts_engine = _FakeTtsEngine(wav_path=wav_path)
      playback = _FakePlayback()
      worker = TtsWorker(tts_engine=tts_engine, audio_playback=playback)
      worker.start()
      queued = worker.enqueue_text(
        session_id="s1",
        turn_id="t1",
        text=(
          "He is best known for *Hamlet*, *Macbeth*, "
          "*Romeo and Juliet*, and *King Lear*."
        ),
      )
      drained = worker.wait_until_idle(timeout=2.0)
      worker.stop()

    self.assertTrue(queued)
    self.assertTrue(drained)
    self.assertEqual(
      tts_engine.calls,
      [
        (
          "s1",
          "t1",
          "He is best known for Hamlet, Macbeth, "
          "Romeo and Juliet, and King Lear.",
        )
      ],
    )

  def test_tts_worker_cancel_session_discards_late_chunks(self) -> None:
    """Session cancellation should discard queued and late chunks."""
    with tempfile.TemporaryDirectory() as tmp_name:
      wav_path = Path(tmp_name) / "out.wav"
      wav_path.write_bytes(b"RIFFfake")
      tts_engine = _FakeTtsEngine(wav_path=wav_path)
      playback = _FakePlayback()
      worker = TtsWorker(tts_engine=tts_engine, audio_playback=playback)
      worker.enqueue_text(session_id="s1", turn_id="t1", text="First.")
      worker.enqueue_text(session_id="s1", turn_id="t2", text="Second.")

      removed = worker.cancel_session(session_id="s1")
      late_queued = worker.enqueue_text(
        session_id="s1",
        turn_id="t3",
        text="Late.",
      )

    self.assertEqual(removed, 2)
    self.assertFalse(late_queued)

  def test_tts_worker_clear_cancelled_turn_allows_future_same_turn_id(
    self,
  ) -> None:
    """Clearing a completed turn cancellation should allow new TTS chunks."""
    with tempfile.TemporaryDirectory() as tmp_name:
      wav_path = Path(tmp_name) / "out.wav"
      wav_path.write_bytes(b"RIFFfake")
      worker = TtsWorker(
        tts_engine=_FakeTtsEngine(wav_path=wav_path),
        audio_playback=_FakePlayback(),
      )

      worker.cancel_turn(session_id="s1", turn_id="t1")
      blocked = worker.enqueue_text(
        session_id="s1",
        turn_id="t1",
        text="Blocked.",
      )
      worker.clear_cancelled_turn(session_id="s1", turn_id="t1")
      allowed = worker.enqueue_text(
        session_id="s1",
        turn_id="t1",
        text="Allowed.",
      )

    self.assertFalse(blocked)
    self.assertTrue(allowed)

  def test_tts_worker_cancel_active_turn_interrupts_engines(self) -> None:
    """Active turn cancellation should interrupt synthesis/playback layers."""
    with tempfile.TemporaryDirectory() as tmp_name:
      wav_path = Path(tmp_name) / "out.wav"
      wav_path.write_bytes(b"RIFFfake")
      tts_engine = _FakeTtsEngine(wav_path=wav_path)
      tts_engine.block_event = threading.Event()
      playback = _FakePlayback()
      worker = TtsWorker(tts_engine=tts_engine, audio_playback=playback)
      worker.start()
      worker.enqueue_text(session_id="s1", turn_id="t1", text="Long speech.")
      deadline = time.time() + 1.0
      while not tts_engine.calls and time.time() < deadline:
        time.sleep(0.01)

      removed = worker.cancel_turn(session_id="s1", turn_id="t1")
      worker.wait_until_idle(timeout=2.0)
      worker.stop(drain=True)

    self.assertEqual(removed, 0)
    self.assertEqual(tts_engine.cancel_calls, 1)
    self.assertEqual(playback.cancel_calls, 1)

  def test_tts_worker_emits_playback_lifecycle_events(self) -> None:
    """TTS worker should emit explicit playback start and finish events."""
    events = []
    with tempfile.TemporaryDirectory() as tmp_name:
      wav_path = Path(tmp_name) / "out.wav"
      wav_path.write_bytes(b"RIFFfake")
      tts_engine = _FakeTtsEngine(wav_path=wav_path)
      playback = _FakePlayback()
      worker = TtsWorker(
        tts_engine=tts_engine,
        audio_playback=playback,
        event_handler=events.append,
      )
      worker.start()
      worker.enqueue_text(session_id="s1", turn_id="t1", text="Hello there.")
      drained = worker.wait_until_idle(timeout=2.0)
      worker.stop()

    event_types = [event.event_type for event in events]
    self.assertTrue(drained)
    self.assertIn("VoiceTtsPlaybackStarted", event_types)
    self.assertIn("VoiceTtsPlaybackFinished", event_types)

  def test_tts_worker_emits_turn_complete_after_input_closes(self) -> None:
    """TTS worker should own voice_turn_complete once playback drains."""
    events = []
    with tempfile.TemporaryDirectory() as tmp_name:
      wav_path = Path(tmp_name) / "out.wav"
      wav_path.write_bytes(b"RIFFfake")
      tts_engine = _FakeTtsEngine(wav_path=wav_path)
      playback = _FakePlayback()
      worker = TtsWorker(
        tts_engine=tts_engine,
        audio_playback=playback,
        event_handler=events.append,
      )
      worker.start()
      worker.enqueue_text(session_id="s1", turn_id="t1", text="Hello there.")
      worker.mark_turn_input_complete(session_id="s1", turn_id="t1")
      drained = worker.wait_until_idle(timeout=2.0)
      worker.stop()

    event_types = [event.event_type for event in events]
    self.assertTrue(drained)
    self.assertIn("VoiceTurnComplete", event_types)
    self.assertLess(
      event_types.index("VoiceTtsPlaybackFinished"),
      event_types.index("VoiceTurnComplete"),
    )

  def test_orac_forwards_tts_playback_events_to_subscribers(self) -> None:
    """Orac should publish TTS playback events to active voice streams."""
    orchestrator = Orac.__new__(Orac)
    orchestrator.model_name = "test-model"
    orchestrator._voice_event_subscribers = {}
    orchestrator._voice_event_subscriber_lock = threading.Lock()
    frames = []
    from orac_voice.voice_events import VoiceTtsPlaybackStarted

    subscription = type(
      "_Subscription",
      (),
      {
        "callback": frames.append,
        "playback_expected": False,
        "playback_started": False,
        "playback_terminal": False,
      },
    )()
    orchestrator._register_voice_event_subscriber(
      session_id="s1",
      turn_id="t1",
      subscription=subscription,
    )

    orchestrator._handle_voice_event(
      VoiceTtsPlaybackStarted(
        session_id="s1",
        turn_id="t1",
        utterance_id="utt1",
      )
    )

    self.assertEqual(len(frames), 1)
    self.assertEqual(frames[0]["type"], "tts_playback_started")
    self.assertEqual(frames[0]["payload"]["turn_id"], "t1")
    self.assertEqual(frames[0]["payload"]["utterance_id"], "utt1")

  def test_orac_forwards_turn_complete_events_to_subscribers(self) -> None:
    """Orac should forward worker-owned turn completion frames unchanged."""
    orchestrator = Orac.__new__(Orac)
    orchestrator.model_name = "test-model"
    orchestrator._voice_event_subscribers = {}
    orchestrator._voice_event_subscriber_lock = threading.Lock()
    frames = []

    subscription = type(
      "_Subscription",
      (),
      {
        "callback": frames.append,
        "playback_expected": False,
        "playback_started": False,
        "playback_terminal": False,
      },
    )()
    orchestrator._register_voice_event_subscriber(
      session_id="s1",
      turn_id="t1",
      subscription=subscription,
    )

    orchestrator._handle_voice_event(
      VoiceTurnComplete(
        session_id="s1",
        turn_id="t1",
        reason="completed",
      )
    )

    self.assertEqual(len(frames), 1)
    self.assertEqual(frames[0]["type"], "voice_turn_complete")
    self.assertEqual(frames[0]["payload"]["turn_id"], "t1")

  def test_orac_routes_text_chunk_but_not_text_delta_to_voice(self) -> None:
    """Orac should route only speech chunks to the TTS queue."""
    orchestrator = Orac.__new__(Orac)
    worker = _FakeVoiceWorker()
    orchestrator._tts_worker = worker
    req_env = {"id": "req1", "meta": {"session_id": "session1"}}

    orchestrator._route_stream_event_to_voice(
      req_env,
      "text_delta",
      {"delta": "not speech"},
    )
    orchestrator._route_stream_event_to_voice(
      req_env,
      "text_chunk",
      {"chunk": "Speak this.", "turn_id": "turn1"},
    )

    self.assertEqual(worker.enqueued, [("session1", "turn1", "Speak this.")])

  def test_tts_coalescer_merges_short_complete_chunks(self) -> None:
    """TTS coalescer should merge short chunks for one turn."""
    coalescer = TtsChunkCoalescer(enabled=True, max_chars=220, min_chunks=2)

    first = coalescer.add_chunk(
      session_id="s1",
      turn_id="t1",
      text="First sentence.",
    )
    second = coalescer.add_chunk(
      session_id="s1",
      turn_id="t1",
      text="Second sentence.",
    )

    self.assertEqual(first, [])
    self.assertEqual(second, ["First sentence. Second sentence."])

  def test_tts_coalescer_flushes_before_limit_without_splitting(self) -> None:
    """Max chars should flush whole chunks, never split a sentence."""
    coalescer = TtsChunkCoalescer(enabled=True, max_chars=50, min_chunks=3)

    first = coalescer.add_chunk(
      session_id="s1",
      turn_id="t1",
      text="This is the first complete sentence.",
    )
    second = coalescer.add_chunk(
      session_id="s1",
      turn_id="t1",
      text="This is the second complete sentence.",
    )
    final = coalescer.flush(session_id="s1", turn_id="t1")

    self.assertEqual(first, [])
    self.assertEqual(second, ["This is the first complete sentence."])
    self.assertEqual(final, "This is the second complete sentence.")

  def test_orac_coalesces_voice_chunks_until_stream_end(self) -> None:
    """Orac should flush pending coalesced speech on stream end."""
    orchestrator = Orac.__new__(Orac)
    worker = _FakeVoiceWorker()
    orchestrator._tts_worker = worker
    orchestrator._tts_coalescer = TtsChunkCoalescer(
      enabled=True,
      max_chars=220,
      min_chunks=2,
    )
    req_env = {"id": "req1", "meta": {"session_id": "session1"}}

    orchestrator._route_stream_event_to_voice(
      req_env,
      "text_chunk",
      {"chunk": "First sentence.", "turn_id": "turn1"},
    )
    self.assertEqual(worker.enqueued, [])

    orchestrator._route_stream_event_to_voice(
      req_env,
      "stream_end",
      {"turn_id": "turn1"},
    )

    self.assertEqual(worker.enqueued, [("session1", "turn1", "First sentence.")])

  def test_orac_does_not_expect_playback_until_tts_is_queued(self) -> None:
    """Coalesced text chunks should not alone create playback wait state."""
    orchestrator = Orac.__new__(Orac)
    worker = _FakeVoiceWorker()
    orchestrator._tts_worker = worker
    orchestrator._tts_coalescer = TtsChunkCoalescer(
      enabled=True,
      max_chars=220,
      min_chunks=2,
    )
    orchestrator._voice_event_subscribers = {}
    orchestrator._voice_event_subscriber_lock = threading.Lock()
    subscription = type(
      "_Subscription",
      (),
      {
        "callback": lambda _frame: None,
        "playback_expected": False,
        "playback_started": False,
        "playback_terminal": False,
      },
    )()
    orchestrator._register_voice_event_subscriber(
      session_id="session1",
      turn_id="turn1",
      subscription=subscription,
    )
    req_env = {"id": "turn1", "meta": {"session_id": "session1"}}

    orchestrator._route_stream_event_to_voice(
      req_env,
      "text_chunk",
      {"chunk": "Short answer.", "turn_id": "turn1"},
    )

    self.assertEqual(worker.enqueued, [])
    self.assertFalse(subscription.playback_expected)

  def test_orac_cancel_voice_session_delegates_to_worker(self) -> None:
    """Orac should expose general session cancellation for clients."""
    orchestrator = Orac.__new__(Orac)
    worker = _FakeVoiceWorker()
    orchestrator._tts_worker = worker

    orchestrator.cancel_voice_session(session_id="session1")

    self.assertEqual(worker.cancelled_sessions, ["session1"])

  def test_orac_voice_cancel_request_marks_and_cancels_turn(self) -> None:
    """Voice cancel route should stop the selected voice turn."""
    orchestrator = Orac.__new__(Orac)
    orchestrator.model_name = "test-model"
    orchestrator._voice_cancelled_turns = set()
    worker = _FakeVoiceWorker()
    orchestrator._tts_worker = worker
    orchestrator._tts_coalescer = None
    req_env = {
      "id": "req_cancel",
      "payload": {
        "session_id": "voice-session",
        "turn_id": "turn1",
        "scope": "turn",
        "reason": "barge-in",
      },
    }

    response_text = orchestrator._handle_voice_cancel_request(req_env)
    response = json.loads(response_text)

    self.assertEqual(response["payload"]["cancelled"], True)
    self.assertEqual(worker.cancelled_turns, [("voice-session", "turn1")])
    self.assertTrue(
      orchestrator._is_voice_turn_cancelled(
        session_id="voice-session",
        turn_id="turn1",
      )
    )

  def test_orac_clear_voice_turn_cancelled_clears_tts_worker_state(self) -> None:
    """Completed cancelled turns should not poison later TTS enqueueing."""
    orchestrator = Orac.__new__(Orac)
    orchestrator._voice_cancelled_turns = {("voice-session", "turn1")}
    worker = _FakeVoiceWorker()
    orchestrator._tts_worker = worker

    orchestrator._clear_voice_turn_cancelled(
      session_id="voice-session",
      turn_id="turn1",
    )

    self.assertFalse(
      orchestrator._is_voice_turn_cancelled(
        session_id="voice-session",
        turn_id="turn1",
      )
    )
    self.assertEqual(worker.cleared_turns, [("voice-session", "turn1")])

  def test_network_listener_remembers_only_streamed_voice_prompt_turns(
    self,
  ) -> None:
    """Voice cancel control connections must not poison the voice session."""
    listener = OracListener(orchestrator=_FakeNetworkOrchestrator())
    voice_turns: set[tuple[str, str]] = set()
    prompt_frame = {
      "route": "orac.prompt",
      "id": "req1",
      "meta": {
        "session_id": "voice-session",
        "stream": True,
      },
    }
    cancel_frame = {
      "route": "orac.voice.cancel",
      "id": "cancel1",
      "meta": {
        "session_id": "voice-session",
        "stream": False,
      },
      "payload": {
        "session_id": "voice-session",
        "turn_id": "req1",
        "scope": "turn",
      },
    }

    listener._remember_voice_turn(json.dumps(prompt_frame), voice_turns)
    listener._remember_voice_turn(json.dumps(cancel_frame), voice_turns)

    self.assertEqual(voice_turns, {("voice-session", "req1")})

  def test_network_listener_connection_cleanup_cancels_turn_not_session(
    self,
  ) -> None:
    """Closed stream connections should not session-mute future voice turns."""
    orchestrator = _FakeNetworkOrchestrator()
    listener = OracListener(orchestrator=orchestrator)

    listener._cancel_voice_turns({("voice-session", "req1")})

    self.assertEqual(orchestrator.cancelled_turns, [("voice-session", "req1")])
    self.assertEqual(orchestrator.cancelled_sessions, [])


class OracVoiceProtocolTests(unittest.IsolatedAsyncioTestCase):
  """Tests for local voice prompt protocol handling."""

  def setUp(self) -> None:
    """Install protocol shims for each isolated async test."""
    self._install_fake_slave_module()

  def _install_fake_slave_module(self) -> None:
    """Install a fake ``view.slave`` module for isolated protocol tests."""
    fake_slave = types.ModuleType("view.slave")
    fake_slave.LLM_TIMEOUT = 1.0
    fake_slave.STREAM_EVENT_TYPES = {
      "stream_start",
      "text_delta",
      "text_chunk",
      "stream_end",
      "stream_cancelled",
      "tts_playback_started",
      "tts_playback_finished",
      "tts_playback_cancelled",
      "tts_playback_error",
      "voice_turn_complete",
    }
    fake_slave.build_prompt_request = lambda prompt_text, **_kwargs: {
      "v": 1,
      "type": "request",
      "id": "req_current",
      "payload": {
        "messages": [{"role": "user", "content": prompt_text}],
      },
    }
    fake_slave.strip_reasoning_tags = lambda value: value
    fake_slave.strip_reasoning_tags_from_delta = lambda value: value
    self._slave_patch = patch.dict(
      sys.modules,
      {"view.slave": fake_slave},
    )
    self._slave_patch.start()
    self.addCleanup(self._slave_patch.stop)

  async def test_voice_prompt_consumes_stream_final_response_frame(self) -> None:
    """Voice session should not leave stale final frames for the next turn."""
    reader = asyncio.StreamReader()
    writer = _FakeStreamWriter()
    frames = [
      {"v": 1, "type": "stream_start", "payload": {}},
      {"v": 1, "type": "text_delta", "payload": {"delta": "First"}},
      {"v": 1, "type": "stream_end", "payload": {"stop_reason": "stop"}},
      {"v": 1, "type": "response", "payload": {"content": "First final"}},
      {"v": 1, "type": "stream_start", "payload": {}},
      {"v": 1, "type": "text_delta", "payload": {"delta": "Second"}},
      {"v": 1, "type": "stream_end", "payload": {"stop_reason": "stop"}},
      {"v": 1, "type": "response", "payload": {"content": "Second final"}},
    ]
    for frame in frames:
      reader.feed_data((json.dumps(frame) + "\n").encode("utf-8"))
    reader.feed_eof()

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
      first_status = await _send_orac_prompt(
        reader=reader,
        writer=writer,
        prompt_text="first",
      )
      second_status = await _send_orac_prompt(
        reader=reader,
        writer=writer,
        prompt_text="second",
      )

    self.assertEqual(first_status, 0)
    self.assertEqual(second_status, 0)
    self.assertIn("Orac: First", output.getvalue())
    self.assertIn("Orac: Second", output.getvalue())
    self.assertNotIn("Orac: First final", output.getvalue())

  async def test_voice_prompt_skips_stale_reply_frame(self) -> None:
    """Voice session should ignore frames for an earlier request id."""
    reader = asyncio.StreamReader()
    writer = _FakeStreamWriter()
    frames = [
      {
        "v": 1,
        "type": "response",
        "reply_to": "req_old",
        "payload": {"content": "Old response"},
      },
      {
        "v": 1,
        "type": "stream_start",
        "reply_to": "req_current",
        "payload": {},
      },
      {
        "v": 1,
        "type": "text_delta",
        "reply_to": "req_current",
        "payload": {"delta": "Current response"},
      },
      {
        "v": 1,
        "type": "stream_end",
        "reply_to": "req_current",
        "payload": {"stop_reason": "stop"},
      },
      {
        "v": 1,
        "type": "response",
        "reply_to": "req_current",
        "payload": {"content": "Current final"},
      },
    ]
    for frame in frames:
      reader.feed_data((json.dumps(frame) + "\n").encode("utf-8"))
    reader.feed_eof()

    output = io.StringIO()
    with patch(
      "view.slave.build_prompt_request",
      return_value={
        "v": 1,
        "type": "request",
        "id": "req_current",
        "payload": {"messages": [{"role": "user", "content": "current"}]},
      },
    ):
      with contextlib.redirect_stdout(output):
        status = await _send_orac_prompt(
          reader=reader,
          writer=writer,
          prompt_text="current",
        )

    self.assertEqual(status, 0)
    self.assertIn("Orac: Current response", output.getvalue())
    self.assertNotIn("Old response", output.getvalue())

  async def test_disabled_barge_in_starts_no_monitor_and_sends_no_cancel(
    self,
  ) -> None:
    """Disabled barge-in should be inert during playback lifecycle events."""
    self._install_fake_slave_module()
    reader = asyncio.StreamReader()
    writer = _FakeStreamWriter()
    frames = [
      {
        "v": 1,
        "type": "stream_start",
        "reply_to": "req_current",
        "payload": {},
      },
      {
        "v": 1,
        "type": "text_delta",
        "reply_to": "req_current",
        "payload": {"delta": "Long answer."},
      },
      {
        "v": 1,
        "type": "text_chunk",
        "reply_to": "req_current",
        "payload": {"chunk": "Long answer.", "turn_id": "req_current"},
      },
      {
        "v": 1,
        "type": "stream_end",
        "reply_to": "req_current",
        "payload": {"stop_reason": "stop"},
      },
      {
        "v": 1,
        "type": "response",
        "reply_to": "req_current",
        "payload": {"content": "Long answer."},
      },
      {
        "v": 1,
        "type": "tts_playback_started",
        "reply_to": "req_current",
        "payload": {
          "turn_id": "req_current",
          "timestamp": "2026-05-08T10:00:00+00:00",
          "utterance_id": "utt1",
        },
      },
      {
        "v": 1,
        "type": "tts_playback_finished",
        "reply_to": "req_current",
        "payload": {
          "turn_id": "req_current",
          "timestamp": "2026-05-08T10:00:01+00:00",
          "utterance_id": "utt1",
        },
      },
    ]
    for frame in frames:
      reader.feed_data((json.dumps(frame) + "\n").encode("utf-8"))
    reader.feed_eof()

    controller = _DisabledBargeInController()
    cancel_calls = []

    async def _fake_cancel(**kwargs) -> None:
      cancel_calls.append(kwargs)

    with patch(
      "orac_voice.voice_loop_local._send_voice_cancel_request",
      side_effect=_fake_cancel,
    ):
      status = await _send_orac_prompt(
        reader=reader,
        writer=writer,
        prompt_text="current",
        barge_in_controller=controller,
        voice_session_id="voice-session",
        cancel_host="127.0.0.1",
        cancel_port=8765,
      )

    self.assertEqual(status, 0)
    self.assertEqual(controller.reset_calls, 0)
    self.assertEqual(controller.start_calls, 0)
    self.assertEqual(controller.stop_calls, 0)
    self.assertEqual(cancel_calls, [])

  async def test_voice_prompt_does_not_wait_on_text_chunk_without_playback(
    self,
  ) -> None:
    """Text chunks alone should not force a playback lifecycle wait."""
    self._install_fake_slave_module()
    reader = asyncio.StreamReader()
    writer = _FakeStreamWriter()
    frames = [
      {
        "v": 1,
        "type": "stream_start",
        "reply_to": "req_current",
        "payload": {},
      },
      {
        "v": 1,
        "type": "text_delta",
        "reply_to": "req_current",
        "payload": {"delta": "OK."},
      },
      {
        "v": 1,
        "type": "text_chunk",
        "reply_to": "req_current",
        "payload": {"chunk": "OK.", "turn_id": "req_current"},
      },
      {
        "v": 1,
        "type": "stream_end",
        "reply_to": "req_current",
        "payload": {"stop_reason": "stop"},
      },
      {
        "v": 1,
        "type": "response",
        "reply_to": "req_current",
        "payload": {"content": "OK."},
      },
    ]
    for frame in frames:
      reader.feed_data((json.dumps(frame) + "\n").encode("utf-8"))
    reader.feed_eof()

    started_at = time.monotonic()
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
      status = await _send_orac_prompt(
        reader=reader,
        writer=writer,
        prompt_text="current",
        barge_in_controller=None,
        voice_session_id="voice-session",
      )
    elapsed = time.monotonic() - started_at

    self.assertEqual(status, 0)
    self.assertLess(elapsed, 0.5)
    self.assertIn("Orac: OK.", output.getvalue())

  async def test_voice_prompt_emits_display_states_for_turn_lifecycle(
    self,
  ) -> None:
    """Prompt handling emits thinking, speaking, and idle display states."""
    reader = asyncio.StreamReader()
    writer = _FakeStreamWriter()
    frames = [
      {
        "v": 1,
        "type": "stream_start",
        "reply_to": "req_current",
        "payload": {},
      },
      {
        "v": 1,
        "type": "text_delta",
        "reply_to": "req_current",
        "payload": {"delta": "OK."},
      },
      {
        "v": 1,
        "type": "text_chunk",
        "reply_to": "req_current",
        "payload": {"chunk": "OK.", "turn_id": "req_current"},
      },
      {
        "v": 1,
        "type": "stream_end",
        "reply_to": "req_current",
        "payload": {"stop_reason": "stop"},
      },
      {
        "v": 1,
        "type": "response",
        "reply_to": "req_current",
        "payload": {"content": "OK."},
      },
      {
        "v": 1,
        "type": "tts_playback_started",
        "reply_to": "req_current",
        "payload": {"turn_id": "req_current", "utterance_id": "utt1"},
      },
      {
        "v": 1,
        "type": "tts_playback_finished",
        "reply_to": "req_current",
        "payload": {"turn_id": "req_current", "utterance_id": "utt1"},
      },
      {
        "v": 1,
        "type": "voice_turn_complete",
        "reply_to": "req_current",
        "payload": {
          "turn_id": "req_current",
          "request_id": "req_current",
          "timestamp": "2026-05-07T20:00:01+00:00",
        },
      },
    ]
    for frame in frames:
      reader.feed_data((json.dumps(frame) + "\n").encode("utf-8"))
    reader.feed_eof()

    sender = _FakeDisplaySender()
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
      status = await _send_orac_prompt(
        reader=reader,
        writer=writer,
        prompt_text="current",
        voice_session_id="voice-session",
        display_sender=sender,
      )

    self.assertEqual(status, 0)
    self.assertEqual(
      [state[0] for state in sender.states],
      ["thinking", "speaking", "idle"],
    )
    self.assertEqual(sender.states[-1][1], "Listening for wake word")
    self.assertTrue(
      all(state[2] == "voice-session" for state in sender.states)
    )
    self.assertTrue(all(state[3] == "req_current" for state in sender.states))

  async def test_voice_prompt_stays_speaking_until_last_chunk_finishes(
    self,
  ) -> None:
    """Prompt handling should not return to idle between spoken chunks."""
    reader = asyncio.StreamReader()
    writer = _FakeStreamWriter()
    frames = [
      {
        "v": 1,
        "type": "stream_start",
        "reply_to": "req_current",
        "payload": {},
      },
      {
        "v": 1,
        "type": "text_delta",
        "reply_to": "req_current",
        "payload": {"delta": "Freddie Mercury was"},
      },
      {
        "v": 1,
        "type": "text_chunk",
        "reply_to": "req_current",
        "payload": {"chunk": "Freddie Mercury was", "turn_id": "req_current"},
      },
      {
        "v": 1,
        "type": "tts_playback_started",
        "reply_to": "req_current",
        "payload": {"turn_id": "req_current", "utterance_id": "utt1"},
      },
      {
        "v": 1,
        "type": "tts_playback_finished",
        "reply_to": "req_current",
        "payload": {"turn_id": "req_current", "utterance_id": "utt1"},
      },
      {
        "v": 1,
        "type": "text_delta",
        "reply_to": "req_current",
        "payload": {"delta": " the lead singer of Queen."},
      },
      {
        "v": 1,
        "type": "text_chunk",
        "reply_to": "req_current",
        "payload": {
          "chunk": "the lead singer of Queen.",
          "turn_id": "req_current",
        },
      },
      {
        "v": 1,
        "type": "stream_end",
        "reply_to": "req_current",
        "payload": {"stop_reason": "stop"},
      },
      {
        "v": 1,
        "type": "response",
        "reply_to": "req_current",
        "payload": {
          "content": "Freddie Mercury was the lead singer of Queen.",
        },
      },
      {
        "v": 1,
        "type": "tts_playback_started",
        "reply_to": "req_current",
        "payload": {"turn_id": "req_current", "utterance_id": "utt2"},
      },
      {
        "v": 1,
        "type": "tts_playback_finished",
        "reply_to": "req_current",
        "payload": {"turn_id": "req_current", "utterance_id": "utt2"},
      },
      {
        "v": 1,
        "type": "voice_turn_complete",
        "reply_to": "req_current",
        "payload": {
          "turn_id": "req_current",
          "request_id": "req_current",
          "timestamp": "2026-05-07T20:00:02+00:00",
        },
      },
    ]
    for frame in frames:
      reader.feed_data((json.dumps(frame) + "\n").encode("utf-8"))
    reader.feed_eof()

    sender = _FakeDisplaySender()
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
      status = await _send_orac_prompt(
        reader=reader,
        writer=writer,
        prompt_text="current",
        voice_session_id="voice-session",
        display_sender=sender,
      )

    self.assertEqual(status, 0)
    self.assertEqual(
      [state[0] for state in sender.states],
      ["thinking", "speaking", "speaking", "idle"],
    )
    self.assertEqual(sender.states[-1][1], "Listening for wake word")
    self.assertTrue(all(state[0] != "idle" for state in sender.states[:-1]))

  async def test_voice_prompt_waits_for_all_playback_utterances(
    self,
  ) -> None:
    """Long responses should finish after all spoken utterances, not chunks."""
    reader = asyncio.StreamReader()
    writer = _FakeStreamWriter()
    frames = [
      {
        "v": 1,
        "type": "stream_start",
        "reply_to": "req_current",
        "payload": {},
      },
      {
        "v": 1,
        "type": "text_delta",
        "reply_to": "req_current",
        "payload": {"delta": "Freddie Mercury was"},
      },
      {
        "v": 1,
        "type": "text_chunk",
        "reply_to": "req_current",
        "payload": {"chunk": "Freddie Mercury was", "turn_id": "req_current"},
      },
      {
        "v": 1,
        "type": "text_delta",
        "reply_to": "req_current",
        "payload": {"delta": " a British singer."},
      },
      {
        "v": 1,
        "type": "text_chunk",
        "reply_to": "req_current",
        "payload": {"chunk": "a British singer.", "turn_id": "req_current"},
      },
      {
        "v": 1,
        "type": "text_delta",
        "reply_to": "req_current",
        "payload": {"delta": " He fronted Queen."},
      },
      {
        "v": 1,
        "type": "text_chunk",
        "reply_to": "req_current",
        "payload": {"chunk": "He fronted Queen.", "turn_id": "req_current"},
      },
      {
        "v": 1,
        "type": "text_delta",
        "reply_to": "req_current",
        "payload": {"delta": " His voice was distinctive."},
      },
      {
        "v": 1,
        "type": "text_chunk",
        "reply_to": "req_current",
        "payload": {"chunk": "His voice was distinctive.", "turn_id": "req_current"},
      },
      {
        "v": 1,
        "type": "stream_end",
        "reply_to": "req_current",
        "payload": {"stop_reason": "stop"},
      },
      {
        "v": 1,
        "type": "response",
        "reply_to": "req_current",
        "payload": {
          "content": (
            "Freddie Mercury was a British singer. He fronted Queen. "
            "His voice was distinctive."
          ),
        },
      },
      {
        "v": 1,
        "type": "tts_playback_started",
        "reply_to": "req_current",
        "payload": {"turn_id": "req_current", "utterance_id": "utt1"},
      },
      {
        "v": 1,
        "type": "tts_playback_finished",
        "reply_to": "req_current",
        "payload": {"turn_id": "req_current", "utterance_id": "utt1"},
      },
      {
        "v": 1,
        "type": "tts_playback_started",
        "reply_to": "req_current",
        "payload": {"turn_id": "req_current", "utterance_id": "utt2"},
      },
      {
        "v": 1,
        "type": "tts_playback_finished",
        "reply_to": "req_current",
        "payload": {"turn_id": "req_current", "utterance_id": "utt2"},
      },
      {
        "v": 1,
        "type": "voice_turn_complete",
        "reply_to": "req_current",
        "payload": {
          "turn_id": "req_current",
          "request_id": "req_current",
          "timestamp": "2026-05-07T20:00:03+00:00",
        },
      },
    ]
    for frame in frames:
      reader.feed_data((json.dumps(frame) + "\n").encode("utf-8"))
    reader.feed_eof()

    sender = _FakeDisplaySender()
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
      status = await _send_orac_prompt(
        reader=reader,
        writer=writer,
        prompt_text="current",
        voice_session_id="voice-session",
        display_sender=sender,
      )

    self.assertEqual(status, 0)
    self.assertIn("Orac: Freddie Mercury was", output.getvalue())
    self.assertEqual(sender.states[-1][0], "idle")
    self.assertEqual(sender.states[-1][1], "Listening for wake word")

  async def test_voice_prompt_barge_in_cancels_active_turn(self) -> None:
    """Barge-in should stop consuming the current response stream."""
    reader = asyncio.StreamReader()
    writer = _FakeStreamWriter()
    frames = [
      {
        "v": 1,
        "type": "stream_start",
        "reply_to": "req_current",
        "payload": {},
      },
      {
        "v": 1,
        "type": "text_delta",
        "reply_to": "req_current",
        "payload": {"delta": "First part. "},
      },
      {
        "v": 1,
        "type": "text_chunk",
        "reply_to": "req_current",
        "payload": {"chunk": "First part.", "turn_id": "req_current"},
      },
      {
        "v": 1,
        "type": "tts_playback_started",
        "reply_to": "req_current",
        "payload": {
          "turn_id": "req_current",
          "timestamp": "2026-05-07T20:00:00+00:00",
          "utterance_id": "utt1",
        },
      },
      {
        "v": 1,
        "type": "text_delta",
        "reply_to": "req_current",
        "payload": {"delta": "Should not be consumed."},
      },
    ]
    for frame in frames:
      reader.feed_data((json.dumps(frame) + "\n").encode("utf-8"))

    cancel_calls = []
    output = io.StringIO()

    async def _fake_cancel(**kwargs) -> None:
      cancel_calls.append(kwargs)

    with patch(
      "view.slave.build_prompt_request",
      return_value={
        "v": 1,
        "type": "request",
        "id": "req_current",
        "payload": {"messages": [{"role": "user", "content": "current"}]},
      },
    ):
      with patch(
        "orac_voice.voice_loop_local._send_voice_cancel_request",
        side_effect=_fake_cancel,
      ):
        with contextlib.redirect_stdout(output):
          controller = _ImmediateBargeInController()
          status = await _send_orac_prompt(
            reader=reader,
            writer=writer,
            prompt_text="current",
            barge_in_controller=controller,
            voice_session_id="voice-session",
            cancel_host="127.0.0.1",
            cancel_port=8765,
          )

    self.assertEqual(status, 0)
    self.assertEqual(len(cancel_calls), 1)
    self.assertEqual(cancel_calls[0]["session_id"], "voice-session")
    self.assertEqual(cancel_calls[0]["turn_id"], "req_current")
    self.assertEqual(controller.stop_calls, 1)
    self.assertIn("[interrupted]", output.getvalue())
    self.assertNotIn("Should not be consumed", output.getvalue())

  async def test_voice_prompt_enables_barge_in_on_playback_started(self) -> None:
    """Barge-in should start from explicit playback lifecycle events."""
    reader = asyncio.StreamReader()
    writer = _FakeStreamWriter()
    frames = [
      {
        "v": 1,
        "type": "stream_start",
        "reply_to": "req_current",
        "payload": {},
      },
      {
        "v": 1,
        "type": "text_delta",
        "reply_to": "req_current",
        "payload": {"delta": "Long answer."},
      },
      {
        "v": 1,
        "type": "text_chunk",
        "reply_to": "req_current",
        "payload": {"chunk": "Long answer.", "turn_id": "req_current"},
      },
      {
        "v": 1,
        "type": "stream_end",
        "reply_to": "req_current",
        "payload": {"stop_reason": "stop"},
      },
      {
        "v": 1,
        "type": "tts_playback_started",
        "reply_to": "req_current",
        "payload": {
          "turn_id": "req_current",
          "timestamp": "2026-05-07T20:00:00+00:00",
          "utterance_id": "utt1",
        },
      },
      {
        "v": 1,
        "type": "response",
        "reply_to": "req_current",
        "payload": {"content": "Long answer."},
      },
    ]
    for frame in frames:
      reader.feed_data((json.dumps(frame) + "\n").encode("utf-8"))
    reader.feed_eof()

    controller = _ImmediateBargeInController()
    cancel_calls = []
    output = io.StringIO()

    async def _fake_cancel(**kwargs) -> None:
      cancel_calls.append(kwargs)

    with patch(
      "view.slave.build_prompt_request",
      return_value={
        "v": 1,
        "type": "request",
        "id": "req_current",
        "payload": {"messages": [{"role": "user", "content": "current"}]},
      },
    ):
      with patch(
        "orac_voice.voice_loop_local._send_voice_cancel_request",
        side_effect=_fake_cancel,
      ):
        with contextlib.redirect_stdout(output):
          status = await _send_orac_prompt(
            reader=reader,
            writer=writer,
            prompt_text="current",
            barge_in_controller=controller,
            voice_session_id="voice-session",
            cancel_host="127.0.0.1",
            cancel_port=8765,
          )

    self.assertEqual(status, 0)
    self.assertEqual(controller.start_calls, 1)
    self.assertEqual(len(cancel_calls), 1)
    self.assertEqual(cancel_calls[0]["session_id"], "voice-session")
    self.assertEqual(cancel_calls[0]["turn_id"], "req_current")
    self.assertIn("[interrupted]", output.getvalue())

  async def test_voice_prompt_disables_barge_in_on_playback_finished(self) -> None:
    """VAD after playback_finished should be ignored by the voice client."""
    reader = asyncio.StreamReader()
    writer = _FakeStreamWriter()
    frames = [
      {
        "v": 1,
        "type": "stream_start",
        "reply_to": "req_current",
        "payload": {},
      },
      {
        "v": 1,
        "type": "text_delta",
        "reply_to": "req_current",
        "payload": {"delta": "Long answer."},
      },
      {
        "v": 1,
        "type": "text_chunk",
        "reply_to": "req_current",
        "payload": {"chunk": "Long answer.", "turn_id": "req_current"},
      },
      {
        "v": 1,
        "type": "tts_playback_started",
        "reply_to": "req_current",
        "payload": {
          "turn_id": "req_current",
          "timestamp": "2026-05-07T20:00:00+00:00",
          "utterance_id": "utt1",
        },
      },
      {
        "v": 1,
        "type": "tts_playback_finished",
        "reply_to": "req_current",
        "payload": {
          "turn_id": "req_current",
          "timestamp": "2026-05-07T20:00:01+00:00",
          "utterance_id": "utt1",
        },
      },
      {
        "v": 1,
        "type": "stream_end",
        "reply_to": "req_current",
        "payload": {"stop_reason": "stop"},
      },
      {
        "v": 1,
        "type": "response",
        "reply_to": "req_current",
        "payload": {"content": "Long answer."},
      },
    ]
    for frame in frames:
      reader.feed_data((json.dumps(frame) + "\n").encode("utf-8"))
    reader.feed_eof()

    controller = _DelayedBargeInController()
    cancel_calls = []
    output = io.StringIO()

    async def _fake_cancel(**kwargs) -> None:
      cancel_calls.append(kwargs)

    with patch(
      "view.slave.build_prompt_request",
      return_value={
        "v": 1,
        "type": "request",
        "id": "req_current",
        "payload": {"messages": [{"role": "user", "content": "current"}]},
      },
    ):
      with patch(
        "orac_voice.voice_loop_local._send_voice_cancel_request",
        side_effect=_fake_cancel,
      ):
        with contextlib.redirect_stdout(output):
          status = await _send_orac_prompt(
            reader=reader,
            writer=writer,
            prompt_text="current",
            barge_in_controller=controller,
            voice_session_id="voice-session",
            cancel_host="127.0.0.1",
            cancel_port=8765,
          )

    self.assertEqual(status, 0)
    self.assertEqual(controller.start_calls, 1)
    self.assertEqual(controller.stop_calls, 1)
    self.assertEqual(cancel_calls, [])
    self.assertFalse(controller.interrupted)

  async def test_voice_session_continues_after_failed_turn(self) -> None:
    """A nonzero turn result should not terminate wake listening."""
    args = build_parser().parse_args(
      ["--voice-session", "--activation-mode", "openwakeword"]
    )
    sender = _FakeDisplaySender()
    activation_listener = _FakeActivationListener(
      [
        types.SimpleNamespace(activated=True, exit_requested=False),
        types.SimpleNamespace(activated=True, exit_requested=False),
        types.SimpleNamespace(activated=False, exit_requested=True),
      ]
    )
    reader_1 = asyncio.StreamReader()
    writer_1 = _FakeStreamWriter()
    reader_2 = asyncio.StreamReader()
    writer_2 = _FakeStreamWriter()
    prompt_calls: list[str] = []
    transcriptions = iter([
      ("voice-session", "turn-1", "First question"),
      ("voice-session", "turn-2", "Second question"),
    ])
    prompt_statuses = iter([1, 0])

    async def _fake_open_connection(*_args, **_kwargs):
      if not prompt_calls:
        return reader_1, writer_1
      return reader_2, writer_2

    async def _fake_send_orac_prompt(**kwargs) -> int:
      prompt_calls.append(str(kwargs["prompt_text"]))
      return next(prompt_statuses)

    def _fake_transcribe_once(*_args, **_kwargs):
      return next(transcriptions)

    with patch(
      "orac_voice.voice_loop_local.SoundDeviceAudioCapture.from_config",
      return_value=_FakeWakeCapture(
        VadCaptureResult(wav_path=Path("/tmp/fake-voice-capture.wav"))
      ),
    ):
      with patch(
        "orac_voice.voice_loop_local.FasterWhisperSttEngine.from_config",
        return_value=object(),
      ):
        with patch(
          "orac_voice.voice_loop_local._create_barge_in_controller",
          return_value=None,
        ):
          with patch(
            "orac_voice.voice_loop_local.DisplayEventSender.from_config",
            return_value=sender,
          ):
            with patch(
              "orac_voice.voice_loop_local._create_activation_listener",
              return_value=activation_listener,
            ):
              with patch(
                "orac_voice.voice_loop_local._load_wake_rearm_seconds",
                return_value=0.0,
              ):
                with patch(
                  "orac_voice.voice_loop_local._transcribe_once",
                  side_effect=_fake_transcribe_once,
                ):
                  with patch(
                    "orac_voice.voice_loop_local._send_orac_prompt",
                    side_effect=_fake_send_orac_prompt,
                  ):
                    with patch(
                      "orac_voice.voice_loop_local.asyncio.open_connection",
                      side_effect=_fake_open_connection,
                    ):
                      status = await _voice_session_async(args)

    self.assertEqual(status, 0)
    self.assertEqual(prompt_calls, ["First question", "Second question"])
    self.assertEqual(activation_listener.wait_calls, 3)
    self.assertEqual(writer_1.close_calls, 1)
    self.assertEqual(writer_1.wait_closed_calls, 1)
    self.assertEqual(writer_2.close_calls, 1)
    self.assertEqual(writer_2.wait_closed_calls, 1)
    self.assertTrue(
      any(
        state[0] == "idle" and state[1] == "Listening for wake word"
        for state in sender.states
      )
    )
    self.assertEqual(sender.states[-1][0], "idle")
    self.assertEqual(sender.states[-1][1], "Listening for wake word")

  async def test_voice_prompt_waits_after_final_response_for_playback_end(self) -> None:
    """Final text response should not re-arm wake before playback finishes."""
    reader = asyncio.StreamReader()
    writer = _FakeStreamWriter()
    frames = [
      {
        "v": 1,
        "type": "stream_start",
        "reply_to": "req_current",
        "payload": {},
      },
      {
        "v": 1,
        "type": "text_delta",
        "reply_to": "req_current",
        "payload": {"delta": "Long answer."},
      },
      {
        "v": 1,
        "type": "text_chunk",
        "reply_to": "req_current",
        "payload": {"chunk": "Long answer.", "turn_id": "req_current"},
      },
      {
        "v": 1,
        "type": "stream_end",
        "reply_to": "req_current",
        "payload": {"stop_reason": "stop"},
      },
      {
        "v": 1,
        "type": "tts_playback_started",
        "reply_to": "req_current",
        "payload": {
          "turn_id": "req_current",
          "timestamp": "2026-05-07T20:00:00+00:00",
          "utterance_id": "utt1",
        },
      },
      {
        "v": 1,
        "type": "response",
        "reply_to": "req_current",
        "payload": {"content": "Long answer."},
      },
      {
        "v": 1,
        "type": "tts_playback_finished",
        "reply_to": "req_current",
        "payload": {
          "turn_id": "req_current",
          "timestamp": "2026-05-07T20:00:01+00:00",
          "utterance_id": "utt1",
        },
      },
    ]
    for frame in frames:
      reader.feed_data((json.dumps(frame) + "\n").encode("utf-8"))
    reader.feed_eof()

    controller = _DelayedBargeInController(delay_seconds=10.0)
    output = io.StringIO()

    with patch(
      "view.slave.build_prompt_request",
      return_value={
        "v": 1,
        "type": "request",
        "id": "req_current",
        "payload": {"messages": [{"role": "user", "content": "current"}]},
      },
    ):
      with contextlib.redirect_stdout(output):
        status = await _send_orac_prompt(
          reader=reader,
          writer=writer,
          prompt_text="current",
          barge_in_controller=controller,
          voice_session_id="voice-session",
          cancel_host="127.0.0.1",
          cancel_port=8765,
        )

    self.assertEqual(status, 0)
    self.assertEqual(controller.start_calls, 1)
    self.assertEqual(controller.stop_calls, 1)
    self.assertNotIn("[interrupted]", output.getvalue())

  async def test_voice_prompt_disables_barge_in_on_playback_cancelled(self) -> None:
    """playback_cancelled should also stop local barge-in monitoring."""
    reader = asyncio.StreamReader()
    writer = _FakeStreamWriter()
    frames = [
      {
        "v": 1,
        "type": "stream_start",
        "reply_to": "req_current",
        "payload": {},
      },
      {
        "v": 1,
        "type": "text_chunk",
        "reply_to": "req_current",
        "payload": {"chunk": "Long answer.", "turn_id": "req_current"},
      },
      {
        "v": 1,
        "type": "tts_playback_started",
        "reply_to": "req_current",
        "payload": {
          "turn_id": "req_current",
          "timestamp": "2026-05-07T20:00:00+00:00",
          "utterance_id": "utt1",
        },
      },
      {
        "v": 1,
        "type": "tts_playback_cancelled",
        "reply_to": "req_current",
        "payload": {
          "turn_id": "req_current",
          "timestamp": "2026-05-07T20:00:01+00:00",
          "utterance_id": "utt1",
          "reason": "test cancellation",
        },
      },
      {
        "v": 1,
        "type": "stream_end",
        "reply_to": "req_current",
        "payload": {"stop_reason": "stop"},
      },
      {
        "v": 1,
        "type": "response",
        "reply_to": "req_current",
        "payload": {"content": "Long answer."},
      },
    ]
    for frame in frames:
      reader.feed_data((json.dumps(frame) + "\n").encode("utf-8"))
    reader.feed_eof()

    controller = _DelayedBargeInController()
    cancel_calls = []

    async def _fake_cancel(**kwargs) -> None:
      cancel_calls.append(kwargs)

    with patch(
      "view.slave.build_prompt_request",
      return_value={
        "v": 1,
        "type": "request",
        "id": "req_current",
        "payload": {"messages": [{"role": "user", "content": "current"}]},
      },
    ):
      with patch(
        "orac_voice.voice_loop_local._send_voice_cancel_request",
        side_effect=_fake_cancel,
      ):
        status = await _send_orac_prompt(
          reader=reader,
          writer=writer,
          prompt_text="current",
          barge_in_controller=controller,
          voice_session_id="voice-session",
          cancel_host="127.0.0.1",
          cancel_port=8765,
        )

    self.assertEqual(status, 0)
    self.assertEqual(controller.start_calls, 1)
    self.assertEqual(controller.stop_calls, 1)
    self.assertEqual(cancel_calls, [])
    self.assertFalse(controller.interrupted)


if __name__ == "__main__":
  unittest.main()
