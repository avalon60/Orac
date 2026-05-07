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
from orac_voice.activation import EnterActivationListener
from orac_voice.activation import VoiceActivationError
from orac_voice.activation import WakeWordActivationListener
from orac_voice.audio_capture import _normalise_input_device
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
from orac_voice.voice_events import VoiceVadSpeechEnded, VoiceVadTimeout
from orac_voice.wake_stt_phrase import SttPhraseWakeWordActivationListener
from orac_voice.wake_stt_phrase import _matches_wake_phrase
from orac_voice.voice_loop_local import _is_exit_phrase
from orac_voice.voice_loop_local import _create_activation_listener
from orac_voice.voice_loop_local import _load_activation_mode
from orac_voice.voice_loop_local import _load_record_mode
from orac_voice.voice_loop_local import _load_wake_rearm_seconds
from orac_voice.voice_loop_local import _send_orac_prompt
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


class _FakeVoiceWorker:
  """Fake voice worker used to verify stream routing."""

  def __init__(self) -> None:
    self.enqueued: list[tuple[str, str, str]] = []
    self.cancelled_sessions: list[str] = []

  def enqueue_text(self, *, session_id: str, turn_id: str, text: str) -> bool:
    """Record queued text."""
    self.enqueued.append((session_id, turn_id, text))
    return True

  def cancel_session(self, *, session_id: str) -> int:
    """Record session cancellation."""
    self.cancelled_sessions.append(session_id)
    return 0


class _FakeStreamWriter:
  """Minimal asyncio stream writer for voice client protocol tests."""

  def __init__(self) -> None:
    self.writes: list[bytes] = []

  def write(self, data: bytes) -> None:
    """Record bytes written by the client."""
    self.writes.append(data)

  async def drain(self) -> None:
    """Match the StreamWriter drain interface."""


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

  def test_orac_cancel_voice_session_delegates_to_worker(self) -> None:
    """Orac should expose general session cancellation for clients."""
    orchestrator = Orac.__new__(Orac)
    worker = _FakeVoiceWorker()
    orchestrator._tts_worker = worker

    orchestrator.cancel_voice_session(session_id="session1")

    self.assertEqual(worker.cancelled_sessions, ["session1"])


class OracVoiceProtocolTests(unittest.IsolatedAsyncioTestCase):
  """Tests for local voice prompt protocol handling."""

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


if __name__ == "__main__":
  unittest.main()
