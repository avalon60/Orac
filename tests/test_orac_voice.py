"""Tests for local Orac voice support.

# Author: Clive Bostock
# Date: 2026-05-04
# Description: Verifies local Piper voice path resolution and TTS queueing.
"""

from __future__ import annotations

from pathlib import Path
import os
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch


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
from lib.config_mgr import ConfigManager
from orac_voice.audio_capture import _normalise_input_device
from orac_voice.stt_faster_whisper import FasterWhisperSttEngine
from orac_voice.stt_faster_whisper import _normalise_compute_type
from orac_voice.stt_faster_whisper import _normalise_device
from orac_voice.tts_piper import PiperTtsEngine
from orac_voice.tts_worker import TtsWorker
from orac_voice.voice_events import VoiceSttEnded, VoiceSttFinal
from orac_voice.voice_loop_local import _is_exit_phrase, build_parser


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

  def test_voice_session_exit_phrase_matching_is_punctuation_tolerant(self) -> None:
    """Recognised exit phrases should support common trailing punctuation."""
    phrases = {"exit", "quit", "stop listening", "goodbye"}

    self.assertTrue(_is_exit_phrase("Goodbye.", phrases))
    self.assertTrue(_is_exit_phrase(" stop listening! ", phrases))
    self.assertFalse(_is_exit_phrase("goodbye for now", phrases))

  def test_stt_voice_events_are_serialisable(self) -> None:
    """STT events should convert paths and timestamps into JSON-friendly values."""
    wav_path = Path("/tmp/orac_voice/capture.wav")
    ended = VoiceSttEnded(session_id="s1", turn_id="t1", wav_path=wav_path)
    final = VoiceSttFinal(session_id="s1", turn_id="t1", text="hello")

    self.assertEqual(ended.to_dict()["wav_path"], str(wav_path))
    self.assertEqual(final.to_dict()["text"], "hello")

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

  def test_orac_cancel_voice_session_delegates_to_worker(self) -> None:
    """Orac should expose general session cancellation for clients."""
    orchestrator = Orac.__new__(Orac)
    worker = _FakeVoiceWorker()
    orchestrator._tts_worker = worker

    orchestrator.cancel_voice_session(session_id="session1")

    self.assertEqual(worker.cancelled_sessions, ["session1"])


if __name__ == "__main__":
  unittest.main()
