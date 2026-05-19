#!/usr/bin/env python3
# Author: Clive Bostock
# Date: 2026-05-05
# Description: Provides local voice activation support for Orac.
"""Command line test harness for local Orac voice input and output."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid

from loguru import logger

from lib.config_mgr import ConfigManager
from orac_voice.activation import DEFAULT_ACTIVATION_MODE
from orac_voice.activation import DEFAULT_WAKE_ENGINE
from orac_voice.activation import DEFAULT_WAKE_PHRASE
from orac_voice.activation import EnterActivationListener
from orac_voice.activation import VoiceActivationError
from orac_voice.activation import VoiceActivationListener
from orac_voice.activation import WakeWordActivationListener
from orac_voice.audio_capture import SoundDeviceAudioCapture
from orac_voice.barge_in import BargeInController
from orac_voice.barge_in import BargeInResult
from orac_voice.barge_in import OpenWakeWordBargeInController
from orac_voice.barge_in import VAD_BARGE_IN_EXPERIMENTAL_WARNING
from orac_voice.barge_in import WAKEWORD_BARGE_IN_EXPERIMENTAL_WARNING
from orac_voice.barge_in import load_barge_in_config
from orac_voice.interruption_policy import InterruptionAction
from orac_voice.interruption_policy import InterruptionPolicy
from orac_voice.stt_faster_whisper import FasterWhisperSttEngine
from orac_voice.tts_worker import create_local_tts_worker_from_config
from orac_voice.tts_piper import resolve_orac_home
from orac_voice.wake_openwakeword import DEFAULT_OPENWAKEWORD_FRAME_MS
from orac_voice.wake_openwakeword import DEFAULT_OPENWAKEWORD_MODEL_NAMES
from orac_voice.wake_openwakeword import DEFAULT_OPENWAKEWORD_REFRACTORY_SECONDS
from orac_voice.wake_openwakeword import DEFAULT_OPENWAKEWORD_THRESHOLD
from orac_voice.wake_openwakeword import OpenWakeWordActivationListener
from orac_voice.wake_porcupine import PorcupineActivationListener
from orac_voice.wake_porcupine import DEFAULT_PORCUPINE_ACCESS_KEY_RESOURCE
from orac_voice.wake_stt_phrase import SttPhraseWakeWordActivationListener
from orac_voice.voice_events import (
  VoiceEvent,
  VoiceSttEnded,
  VoiceSttError,
  VoiceSttFinal,
  VoiceSttStarted,
  VoiceVadListeningStarted,
  VoiceVadSpeechEnded,
  VoiceVadSpeechStarted,
  VoiceVadTimeout,
)
from view.display_event_pipe import DisplayEvent
from view.display_event_pipe import DisplayEventSender


DEFAULT_WAIT_SECONDS = 180.0
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_SESSION_EXIT_PHRASES = ("exit", "quit", "stop listening", "goodbye")
DEFAULT_RECORD_MODE = "fixed"
DEFAULT_WAKE_REARM_SECONDS = 1.0
DEFAULT_CONSOLE_TIMESTAMPS = True
DEFAULT_DISPLAY_BRIDGE_SCRIPT = "web/orac-display/bridge.js"


class NoSpeechDetectedError(RuntimeError):
  """Raised when a recording attempt captures no usable speech."""


def _log_voice_event(event: VoiceEvent) -> None:
  """Log a safe summary of one voice event.

  Args:
    event (VoiceEvent): Voice event to summarise.
  """
  logger.debug("Voice event: {}", event.to_dict())


def _emit(event: VoiceEvent) -> None:
  """Emit a local voice event through the safe logger."""
  _log_voice_event(event)


def _send_display_event(
  display_sender: DisplayEventSender | None,
  event: str,
  *,
  session_id: str | None = None,
  turn_id: str | None = None,
  **payload: object,
) -> None:
  """Emit one lightweight display event if the display pipe is enabled."""
  if display_sender is None:
    return

  event_payload: dict[str, object] = {
    "event": event,
  }
  if session_id is not None:
    event_payload["session_id"] = session_id
  if turn_id is not None:
    event_payload["turn_id"] = turn_id
  for key, value in payload.items():
    if value is not None:
      event_payload[key] = value
  display_sender.send(event_payload)


def _display_runtime_identity_from_frame(
  frame: dict[str, object],
) -> tuple[str, str, str, str] | None:
  """Extract the current LLM/persona identity from an Orac frame."""
  meta = frame.get("meta")
  if not isinstance(meta, dict):
    return None

  model = str(meta.get("model") or "").strip()
  personality_code = str(meta.get("personality_code") or "").strip().upper()
  personality_name = str(meta.get("personality_name") or "").strip()
  persona = personality_name or personality_code
  if model and not persona:
    personality_code = "DEFAULT"
    persona = personality_code
  if not model and not persona:
    return None
  return model, persona, personality_code, personality_name


def _send_configured_runtime_identity(
  display_sender: DisplayEventSender | None,
  *,
  session_id: str | None = None,
) -> None:
  """Emit the configured model/persona before the first Orac response."""
  if display_sender is None:
    return

  config_mgr = _voice_config_manager()
  model = config_mgr.config_value(
    "service",
    "default_model_name",
    default="",
  ).strip()
  persona = "DEFAULT"
  _send_display_event(
    display_sender,
    "runtime.identity",
    session_id=session_id,
    model=model,
    persona=persona,
    personality_code=persona,
    personality_name=persona,
  )


def _load_console_timestamps() -> bool:
  """Return whether local voice console lines include timestamps."""
  config_mgr = _voice_config_manager()
  return config_mgr.bool_config_value(
    "voice",
    "console_timestamps",
    default=DEFAULT_CONSOLE_TIMESTAMPS,
  )


def _console_prefix() -> str:
  """Return a short local timestamp prefix for voice console output."""
  return datetime.now().strftime("[%H:%M:%S] ")


def _console_line(message: str = "") -> None:
  """Print one local voice console line with optional timestamp."""
  if message and _load_console_timestamps():
    print(f"{_console_prefix()}{message}", flush=True)
    return
  print(message, flush=True)


def _console_start(message: str) -> None:
  """Print the start of a streaming console line."""
  prefix = _console_prefix() if _load_console_timestamps() else ""
  print(f"{prefix}{message}", end="", flush=True)


def build_parser() -> argparse.ArgumentParser:
  """Build the command line parser.

  Returns:
    argparse.ArgumentParser: Configured parser.
  """
  parser = argparse.ArgumentParser(
    prog="python -m orac_voice.voice_loop_local",
    description="Test local Orac speech input and output.",
  )
  mode_group = parser.add_mutually_exclusive_group(required=True)
  mode_group.add_argument(
    "--tts-test",
    metavar="TEXT",
    help="Text to synthesise and play locally.",
  )
  mode_group.add_argument(
    "--listen-once",
    action="store_true",
    help="Record one fixed-duration microphone sample and transcribe it.",
  )
  mode_group.add_argument(
    "--voice-turn",
    action="store_true",
    help="Record speech, transcribe it, and submit it to the Orac prompt path.",
  )
  mode_group.add_argument(
    "--voice-session",
    action="store_true",
    help="Run repeated local spoken turns until exit.",
  )
  parser.add_argument(
    "--voice",
    help="Override the configured Piper voice name.",
  )
  parser.add_argument(
    "--voice-dir",
    help="Override the configured Piper voice directory.",
  )
  parser.add_argument(
    "--wait-seconds",
    type=float,
    default=DEFAULT_WAIT_SECONDS,
    help="Maximum seconds to wait for queued speech. Default: %(default)s.",
  )
  parser.add_argument(
    "--browser-mode",
    action="store_true",
    help="Start the Node browser display bridge for display events.",
  )
  parser.add_argument(
    "--buttons",
    action="store_true",
    help="Show the browser UI state buttons in the side panel.",
  )
  parser.add_argument(
    "--display-browser",
    action="store_true",
    help=argparse.SUPPRESS,
  )
  parser.add_argument(
    "--display-browser-host",
    help=argparse.SUPPRESS,
  )
  parser.add_argument(
    "--display-browser-port",
    type=int,
    help=argparse.SUPPRESS,
  )
  parser.add_argument(
    "--record-seconds",
    type=float,
    help="Override configured microphone recording duration.",
  )
  parser.add_argument(
    "--record-mode",
    choices=("fixed", "vad"),
    help="Override configured speech recording mode.",
  )
  parser.add_argument(
    "--activation-mode",
    choices=("enter", "openwakeword", "wake_word", "porcupine", "stt_phrase"),
    help="Override configured voice activation mode for --voice-session.",
  )
  parser.add_argument(
    "--host",
    default=DEFAULT_HOST,
    help="Orac TCP host for voice prompt modes. Default: %(default)s.",
  )
  parser.add_argument(
    "--port",
    type=int,
    default=DEFAULT_PORT,
    help="Orac TCP port for voice prompt modes. Default: %(default)s.",
  )
  return parser


def _load_exit_phrases() -> set[str]:
  """Load configured voice-session exit phrases.

  Returns:
    set[str]: Normalised phrases that should end a local voice session.
  """
  config_path = resolve_orac_home() / "resources" / "config" / "orac.ini"
  config_mgr = ConfigManager(config_file_path=config_path)
  configured = config_mgr.config_value(
    "voice",
    "session_exit_phrases",
    default=",".join(DEFAULT_SESSION_EXIT_PHRASES),
  )
  phrases = {
    phrase.strip().lower()
    for phrase in configured.split(",")
    if phrase.strip()
  }
  return phrases or set(DEFAULT_SESSION_EXIT_PHRASES)


def _is_exit_phrase(text: str, exit_phrases: set[str]) -> bool:
  """Return whether recognised or typed text should end the voice session."""
  cleaned = text.strip().lower().strip(".!?;:")
  return cleaned in exit_phrases


def _load_record_mode(args: argparse.Namespace) -> str:
  """Load the configured or overridden recording mode."""
  if args.record_mode:
    return args.record_mode

  config_path = resolve_orac_home() / "resources" / "config" / "orac.ini"
  config_mgr = ConfigManager(config_file_path=config_path)
  mode = config_mgr.config_value(
    "voice",
    "stt_record_mode",
    default=DEFAULT_RECORD_MODE,
  )
  cleaned = mode.strip().lower()
  if cleaned not in {"fixed", "vad"}:
    raise ValueError(f"Unsupported voice.stt_record_mode: {mode}")
  return cleaned


def _voice_config_manager() -> ConfigManager:
  """Create a ConfigManager for the Orac runtime configuration."""
  config_path = resolve_orac_home() / "resources" / "config" / "orac.ini"
  return ConfigManager(config_file_path=config_path)


def _load_activation_mode(args: argparse.Namespace) -> str:
  """Load the configured or overridden voice activation mode."""
  if args.activation_mode:
    return args.activation_mode

  config_mgr = _voice_config_manager()
  mode = config_mgr.config_value(
    "voice",
    "activation_mode",
    default=DEFAULT_ACTIVATION_MODE,
  )
  cleaned = mode.strip().lower()
  if cleaned not in {
    "enter",
    "openwakeword",
    "wake_word",
    "porcupine",
    "stt_phrase",
  }:
    raise ValueError(f"Unsupported voice.activation_mode: {mode}")
  return cleaned


def _load_wake_rearm_seconds() -> float:
  """Load the delay before wake listening resumes after a response."""
  config_mgr = _voice_config_manager()
  return max(
    0.0,
    float(
      config_mgr.config_value(
        "voice",
        "wake_rearm_seconds",
        default=str(DEFAULT_WAKE_REARM_SECONDS),
      )
    ),
  )


def _create_barge_in_controller() -> BargeInController | OpenWakeWordBargeInController | None:
  """Create the configured barge-in controller, if enabled."""
  config_mgr = _voice_config_manager()
  try:
    config = load_barge_in_config(config_mgr)
  except ValueError as exc:
    raise VoiceActivationError(str(exc)) from exc
  if not config.enable_experimental_barge_in:
    return None
  if config.mode == "vad":
    logger.warning(VAD_BARGE_IN_EXPERIMENTAL_WARNING)
    return BargeInController(config=config)
  if config.mode == "wakeword":
    logger.warning(WAKEWORD_BARGE_IN_EXPERIMENTAL_WARNING)
    return OpenWakeWordBargeInController(config=config)
  raise VoiceActivationError(f"Unsupported voice.barge_in_mode: {config.mode}")


def _create_activation_listener(
  *,
  args: argparse.Namespace,
  exit_phrases: set[str],
  capture: SoundDeviceAudioCapture | None = None,
  stt_engine: FasterWhisperSttEngine | None = None,
) -> VoiceActivationListener:
  """Create the configured local voice activation listener."""
  activation_mode = _load_activation_mode(args)
  if activation_mode == "enter":
    return EnterActivationListener(exit_phrases=exit_phrases)

  config_mgr = _voice_config_manager()
  wake_engine = config_mgr.config_value(
    "voice",
    "wake_engine",
    default=DEFAULT_WAKE_ENGINE,
  )
  wake_phrase = config_mgr.config_value(
    "voice",
    "wake_phrase",
    default=DEFAULT_WAKE_PHRASE,
  )
  wake_model = config_mgr.config_value("voice", "wake_model", default="")
  wake_threshold = float(
    config_mgr.config_value("voice", "wake_threshold", default="0.6")
  )
  if activation_mode in {"openwakeword", "porcupine", "stt_phrase"}:
    wake_engine = activation_mode

  if wake_engine.strip().lower() in {"", "none"}:
    raise VoiceActivationError(
      "activation_mode=wake_word requires a supported wake_engine. "
      "No wake-word engine is currently configured."
    )
  cleaned_wake_engine = wake_engine.strip().lower()
  if cleaned_wake_engine == "openwakeword":
    return OpenWakeWordActivationListener.from_config(
      model_paths=config_mgr.config_value(
        "voice",
        "openwakeword_model_paths",
        default="",
      ),
      model_names=config_mgr.config_value(
        "voice",
        "openwakeword_model_names",
        default=",".join(DEFAULT_OPENWAKEWORD_MODEL_NAMES),
      ),
      model_dirs=config_mgr.config_value(
        "voice",
        "openwakeword_model_dirs",
        default="",
      ),
      threshold=float(
        config_mgr.config_value(
          "voice",
          "openwakeword_threshold",
          default=str(DEFAULT_OPENWAKEWORD_THRESHOLD),
        )
      ),
      inference_framework=config_mgr.config_value(
        "voice",
        "openwakeword_inference_framework",
        default="auto",
      ),
      input_device=config_mgr.config_value(
        "voice",
        "stt_input_device",
        default="default",
      ),
      frame_ms=int(
        config_mgr.config_value(
          "voice",
          "wake_chunk_ms",
          default=str(DEFAULT_OPENWAKEWORD_FRAME_MS),
        )
      ),
      status_callback=_console_line,
      refractory_seconds=float(
        config_mgr.config_value(
          "voice",
          "openwakeword_refractory_seconds",
          default=str(DEFAULT_OPENWAKEWORD_REFRACTORY_SECONDS),
        )
      ),
    )
  if cleaned_wake_engine == "porcupine":
    return PorcupineActivationListener(
      access_key_resource=config_mgr.config_value(
        "voice",
        "porcupine_access_key_resource",
        default=DEFAULT_PORCUPINE_ACCESS_KEY_RESOURCE,
      ),
      keyword_path=config_mgr.config_value(
        "voice",
        "porcupine_keyword_path",
        default="",
      ),
      builtin_keyword=config_mgr.config_value(
        "voice",
        "porcupine_builtin_keyword",
        default="",
      ),
      sensitivity=float(
        config_mgr.config_value(
          "voice",
          "porcupine_sensitivity",
          default=str(wake_threshold),
        )
      ),
    )
  if cleaned_wake_engine == "stt_phrase":
    if capture is None or stt_engine is None:
      raise VoiceActivationError(
        "wake_engine=stt_phrase requires local capture and STT components."
      )
    return SttPhraseWakeWordActivationListener(
      wake_phrase=wake_phrase,
      capture=capture,
      stt_engine=stt_engine,
      exit_phrases=exit_phrases,
    )
  return WakeWordActivationListener(
    wake_engine=wake_engine,
    wake_phrase=wake_phrase,
    wake_model=wake_model,
    wake_threshold=wake_threshold,
  )


def _run_tts_test(args: argparse.Namespace) -> int:
  """Run the existing local TTS smoke test.

  Args:
    args (argparse.Namespace): Parsed CLI arguments.

  Returns:
    int: Process exit code.
  """
  try:
    worker = create_local_tts_worker_from_config(
      event_handler=_log_voice_event,
      voice_name=args.voice,
      voice_dir=args.voice_dir,
    )
    if worker is None:
      logger.error("Voice output is disabled in orac.ini")
      return 2

    session_id = "local-voice-test"
    turn_id = f"tts-test-{uuid.uuid4().hex[:12]}"
    worker.start()
    queued = worker.enqueue_text(
      session_id=session_id,
      turn_id=turn_id,
      text=args.tts_test,
    )
    if not queued:
      logger.error("--tts-test must not be empty")
      worker.stop(drain=False)
      return 2

    if not worker.wait_until_idle(timeout=args.wait_seconds):
      logger.error("Timed out waiting for local voice output")
      worker.stop(drain=False)
      return 1

    if worker.error_count:
      message = worker.last_error.message if worker.last_error else "unknown"
      logger.error("Local voice output failed: {}", message)
      worker.stop(drain=True)
      return 1

    worker.stop(drain=True)
    return 0
  except Exception as exc:
    logger.error("Local voice test failed: {}", exc)
    return 1


def _transcribe_once(
  args: argparse.Namespace,
  *,
  capture: SoundDeviceAudioCapture | None = None,
  stt_engine: FasterWhisperSttEngine | None = None,
  session_id: str | None = None,
  prompt: str | None = "Press Enter to record speech.",
  display_sender: DisplayEventSender | None = None,
) -> tuple[str, str, str]:
  """Capture and transcribe one local microphone sample.

  Args:
    args (argparse.Namespace): Parsed CLI arguments.
    capture (SoundDeviceAudioCapture | None): Optional reusable capture layer.
    stt_engine (FasterWhisperSttEngine | None): Optional reusable STT engine.
    session_id (str | None): Optional stable voice session id.
    prompt (str): Prompt shown before recording.
    display_sender (DisplayEventSender | None): Optional display event sender.

  Returns:
    tuple[str, str, str]: Session id, turn id, and recognised text.
  """
  session_id = session_id or f"local-voice-{uuid.uuid4().hex[:12]}"
  turn_id = f"stt-{uuid.uuid4().hex[:12]}"
  capture = capture or SoundDeviceAudioCapture.from_config(
    record_seconds=args.record_seconds
  )
  stt_engine = stt_engine or FasterWhisperSttEngine.from_config()
  record_mode = _load_record_mode(args)
  timing_started_at = time.perf_counter()
  record_started_at: float | None = None
  record_finished_at: float | None = None
  transcribe_started_at: float | None = None
  transcribe_finished_at: float | None = None

  if prompt is not None:
    entered = input(prompt)
    if _is_exit_phrase(entered, _load_exit_phrases()):
      raise EOFError
  
  if display_sender:
    _send_display_event(
      display_sender,
      "transcript.turn.clear",
      session_id=session_id,
      turn_id=turn_id,
    )
    display_sender.send_state(
      "listening",
      message="Listening...",
      session_id=session_id,
      turn_id=turn_id
    )

  _emit(
    VoiceSttStarted(
      session_id=session_id,
      turn_id=turn_id,
      record_seconds=(
        capture.record_seconds if record_mode == "fixed" else None
      ),
    )
  )
  try:
    record_started_at = time.perf_counter()
    if record_mode == "vad":
      wav_path = _record_vad_sample(
        capture=capture,
        session_id=session_id,
        turn_id=turn_id,
      )
    else:
      wav_path = capture.record_to_wav(
        session_id=session_id,
        turn_id=turn_id,
        record_seconds=args.record_seconds,
      )
    record_finished_at = time.perf_counter()
    _emit(
      VoiceSttEnded(
        session_id=session_id,
        turn_id=turn_id,
        wav_path=wav_path,
      )
    )

    if display_sender:
      display_sender.send_state(
        "transcribing",
        message="Transcribing...",
        session_id=session_id,
        turn_id=turn_id
      )

    transcribe_started_at = time.perf_counter()
    recognised_text = stt_engine.transcribe_wav(wav_path)
    transcribe_finished_at = time.perf_counter()
    _emit(
      VoiceSttFinal(
        session_id=session_id,
        turn_id=turn_id,
        text=recognised_text,
      )
    )
    logger.info(
      (
        "Voice STT timing: session={} turn={} mode={} record={:.2f}s "
        "transcribe={:.2f}s total={:.2f}s"
      ),
      session_id,
      turn_id,
      record_mode,
      (
        record_finished_at - record_started_at
        if record_started_at is not None and record_finished_at is not None
        else 0.0
      ),
      (
        transcribe_finished_at - transcribe_started_at
        if (
          transcribe_started_at is not None
          and transcribe_finished_at is not None
        )
        else 0.0
      ),
      transcribe_finished_at - timing_started_at,
    )
    _send_display_event(
      display_sender,
      "transcript.user.final",
      session_id=session_id,
      turn_id=turn_id,
      text=recognised_text,
    )
    return session_id, turn_id, recognised_text
  except KeyboardInterrupt:
    capture.cancel()
    raise
  except Exception as exc:
    _emit(
      VoiceSttError(
        session_id=session_id,
        turn_id=turn_id,
        message=str(exc),
      )
    )
    raise


def _record_vad_sample(
  *,
  capture: SoundDeviceAudioCapture,
  session_id: str,
  turn_id: str,
) -> Path:
  """Record one VAD-controlled utterance and return its WAV path."""
  last_status: set[str] = set()

  def _status(label: str) -> None:
    if label == "listening" and label not in last_status:
      last_status.add(label)
      _console_line("Listening...")
      _emit(
        VoiceVadListeningStarted(
          session_id=session_id,
          turn_id=turn_id,
          initial_timeout_seconds=(
            capture.vad_config.initial_timeout_seconds
          ),
        )
      )
    elif label == "speech_started" and label not in last_status:
      last_status.add(label)
      _console_line("Speech detected...")
      _emit(VoiceVadSpeechStarted(session_id=session_id, turn_id=turn_id))
    elif label in {"speech_ended", "max_duration_reached"}:
      _console_line("Speech ended; transcribing...")

  result = capture.record_until_silence_to_wav(
    session_id=session_id,
    turn_id=turn_id,
    status_callback=_status,
  )
  if result.no_speech_timeout:
    _emit(
      VoiceVadTimeout(
        session_id=session_id,
        turn_id=turn_id,
        initial_timeout_seconds=capture.vad_config.initial_timeout_seconds,
      )
    )
    raise NoSpeechDetectedError("No speech detected before timeout")
  if result.wav_path is None:
    raise NoSpeechDetectedError("No usable speech was captured")

  _emit(
    VoiceVadSpeechEnded(
      session_id=session_id,
      turn_id=turn_id,
      duration_seconds=result.duration_seconds,
      max_duration_reached=result.max_duration_reached,
    )
  )
  return result.wav_path


async def _send_orac_prompt(
  *,
  reader: asyncio.StreamReader,
  writer: asyncio.StreamWriter,
  prompt_text: str,
  barge_in_controller: BargeInController | None = None,
  voice_session_id: str | None = None,
  cancel_host: str | None = None,
  cancel_port: int | None = None,
  display_sender: DisplayEventSender | None = None,
) -> int:
  """Send one prompt on an existing Orac TCP connection."""
  from view import slave as slave_client

  if (
    barge_in_controller is not None
    and not getattr(barge_in_controller.config, "enabled", True)
  ):
    barge_in_controller = None

  req_env = slave_client.build_prompt_request(
    prompt_text,
    session_id=voice_session_id,
  )
  req_id = str(req_env.get("id") or "")
  wire = json.dumps(req_env, ensure_ascii=False) + "\n"
  writer.write(wire.encode("utf-8"))
  await writer.drain()
  request_sent_at = time.perf_counter()
  _send_display_event(
    display_sender,
    "transcript.orac.start",
    session_id=voice_session_id,
    turn_id=req_id,
  )
  if display_sender is not None:
    display_sender.send_state(
      "thinking",
      message="Thinking...",
      session_id=voice_session_id,
      turn_id=req_id,
    )

  stream_rendered = False
  stream_finished = False
  stream_error_seen = False
  barge_active = False
  playback_expected = False
  playback_started = False
  playback_started_count = 0
  playback_finished_count = 0
  playback_cancelled = False
  playback_terminal = False
  final_response_status: int | None = None
  orac_transcript_parts: list[str] = []
  stream_start_at: float | None = None
  first_text_delta_at: float | None = None
  first_text_chunk_at: float | None = None
  stream_end_at: float | None = None
  first_tts_started_at: float | None = None
  last_tts_finished_at: float | None = None
  timing_logged = False
  barge_in_min_speech_ms = 0
  last_runtime_identity: tuple[str, str, str, str] | None = None
  if (
    barge_in_controller is not None
    and not isinstance(barge_in_controller, OpenWakeWordBargeInController)
  ):
    barge_in_min_speech_ms = getattr(
      barge_in_controller.config,
      "min_speech_ms",
      0,
    )
  interruption_policy = InterruptionPolicy(
    allow_interruptions=barge_in_controller is not None,
    min_speech_ms=barge_in_min_speech_ms,
  )
  barge_event = asyncio.Event()
  barge_result: BargeInResult | None = None
  loop = asyncio.get_running_loop()

  def _on_barge_in(result: BargeInResult) -> None:
    nonlocal barge_result
    decision = interruption_policy.consider_acoustic_interrupt(
      output_turn_id=req_id,
      speech_ms=result.speech_ms,
    )
    if decision.action is not InterruptionAction.INTERRUPT:
      logger.debug(
        "Ignoring acoustic interruption for turn {}: {}",
        req_id,
        decision.reason,
      )
      return
    barge_result = result
    loop.call_soon_threadsafe(barge_event.set)

  def _start_barge_in_monitor() -> None:
    nonlocal barge_active
    if barge_active or barge_in_controller is None:
      return
    barge_active = True
    barge_event.clear()
    barge_in_controller.reset_for_speech()
    barge_in_controller.start(on_interrupt=_on_barge_in)

  def _stop_barge_in_monitor() -> None:
    nonlocal barge_active
    if not barge_active or barge_in_controller is None:
      return
    barge_active = False
    barge_in_controller.stop()

  def _elapsed_since_request(value: float | None) -> float | None:
    """Return elapsed seconds from the prompt send point."""
    if value is None:
      return None
    return value - request_sent_at

  def _format_timing(value: float | None) -> str:
    """Format an optional elapsed duration for logs."""
    if value is None:
      return "n/a"
    return f"{value:.2f}s"

  def _log_response_timing(reason: str) -> None:
    """Log one compact response timing summary for this turn."""
    nonlocal timing_logged
    if timing_logged:
      return
    timing_logged = True
    logger.info(
      (
        "Voice response timing: session={} turn={} reason={} "
        "stream_start={} first_text={} first_speech_chunk={} "
        "stream_end={} first_audio={} playback_done={} total={} "
        "tts_parts={}"
      ),
      voice_session_id or "",
      req_id,
      reason,
      _format_timing(_elapsed_since_request(stream_start_at)),
      _format_timing(_elapsed_since_request(first_text_delta_at)),
      _format_timing(_elapsed_since_request(first_text_chunk_at)),
      _format_timing(_elapsed_since_request(stream_end_at)),
      _format_timing(_elapsed_since_request(first_tts_started_at)),
      _format_timing(_elapsed_since_request(last_tts_finished_at)),
      _format_timing(time.perf_counter() - request_sent_at),
      playback_started_count,
    )

  def _maybe_finish_turn() -> int | None:
    """Return the final status once the answer and playback are complete."""
    if playback_cancelled:
      interruption_policy.mark_turn_complete(output_turn_id=req_id)
      if display_sender is not None:
        display_sender.send_state(
          "idle",
          message="Listening for wake word",
          session_id=voice_session_id,
          turn_id=req_id,
      )
      _stop_barge_in_monitor()
      _log_response_timing("cancelled")
      return final_response_status if final_response_status is not None else 0
    if final_response_status is None:
      return None
    if not stream_finished:
      return None
    interruption_policy.mark_turn_complete(output_turn_id=req_id)
    if display_sender is not None:
      display_sender.send_state(
        "idle",
        message="Listening for wake word",
        session_id=voice_session_id,
        turn_id=req_id,
      )
    _stop_barge_in_monitor()
    _log_response_timing("response")
    return final_response_status

  async def _cancel_interrupted_voice() -> int:
    logger.info("Barge-in interruption received; cancelling active voice")
    _console_line("[interrupted]")
    if display_sender is not None:
      display_sender.send_state(
        "interrupted",
        message="Interrupted",
        session_id=voice_session_id,
      turn_id=req_id,
      )
    _stop_barge_in_monitor()
    interruption_policy.mark_output_cancelled(output_turn_id=req_id)
    await _send_voice_cancel_request(
      host=cancel_host or DEFAULT_HOST,
      port=cancel_port or DEFAULT_PORT,
      session_id=voice_session_id or "",
      turn_id=req_id,
      reason=(barge_result.reason if barge_result else "barge-in"),
    )
    _log_response_timing("interrupted")
    return 0

  async def _read_response_line():
    line_task = asyncio.create_task(reader.readline())
    wait_tasks = {line_task}
    barge_task = None
    if barge_in_controller is not None:
      barge_task = asyncio.create_task(barge_event.wait())
      wait_tasks.add(barge_task)
    done, pending = await asyncio.wait(
      wait_tasks,
      timeout=(
        60.0
        if final_response_status is not None and playback_expected
        else 5.0
        if final_response_status is not None
        else slave_client.LLM_TIMEOUT
      ),
      return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
      task.cancel()
    if not done:
      return "timeout", None
    if barge_task is not None and barge_task in done and barge_event.is_set():
      if not line_task.done():
        line_task.cancel()
      return "interrupted", None
    if line_task in done:
      return "line", line_task.result()
    return "timeout", None

  try:
    while True:
      read_status, resp_bytes = await _read_response_line()
      if read_status == "timeout":
        _console_line("Orac response timed out.")
        _log_response_timing("timeout")
        if display_sender is not None:
          display_sender.send_state(
            "error",
            message="Orac response timed out",
            session_id=voice_session_id,
            turn_id=req_id,
          )
        return 1
      if read_status == "interrupted":
        return await _cancel_interrupted_voice()

      if not resp_bytes:
        if final_response_status is not None:
          if display_sender is not None:
            display_sender.send_state(
              "idle",
              message="Listening for wake word",
              session_id=voice_session_id,
              turn_id=req_id,
            )
          _stop_barge_in_monitor()
          _log_response_timing("connection-closed")
          return final_response_status
        return 0

      response_text = resp_bytes.decode("utf-8", errors="replace").strip()
      try:
        env = json.loads(response_text)
      except json.JSONDecodeError as exc:
        logger.error("Invalid JSON from Orac: {}", exc)
        _console_line("Invalid protocol frame from Orac.")
        _log_response_timing("invalid-json")
        return 1

      frame_reply_to = env.get("reply_to")
      if frame_reply_to and req_id and str(frame_reply_to) != req_id:
        logger.debug(
          "Skipping stale Orac frame for reply_to={} while awaiting {}",
          frame_reply_to,
          req_id,
        )
        continue

      runtime_identity = _display_runtime_identity_from_frame(env)
      if (
        display_sender is not None
        and runtime_identity is not None
        and runtime_identity != last_runtime_identity
      ):
        model, persona, personality_code, personality_name = runtime_identity
        _send_display_event(
          display_sender,
          "runtime.identity",
          session_id=voice_session_id,
          turn_id=req_id,
          model=model,
          persona=persona,
          personality_code=personality_code,
          personality_name=personality_name,
        )
        last_runtime_identity = runtime_identity

      frame_type = env.get("type")
      if frame_type in slave_client.STREAM_EVENT_TYPES:
        if frame_type == "tts_playback_error":
          if not interruption_policy.accept_output_event(output_turn_id=req_id):
            logger.debug(
              "Ignoring stale playback event {} for turn {}",
              frame_type,
              req_id,
            )
            continue
          err_obj = env.get("error")
          msg = ""
          if isinstance(err_obj, dict):
            msg = str(err_obj.get("message") or "")
          logger.warning("TTS playback error: {}", msg or "unknown")
          interruption_policy.mark_output_cancelled(output_turn_id=req_id)
          if display_sender is not None:
            display_sender.send_state(
              "error",
              message=msg or "TTS playback error",
              session_id=voice_session_id,
              turn_id=req_id,
            )
          _stop_barge_in_monitor()
          continue
        err_obj = env.get("error")
        if isinstance(err_obj, dict) and err_obj:
          stream_error_seen = True
          code = err_obj.get("code", "SERVER_ERROR")
          msg = err_obj.get("message", "Unknown error")
          if stream_rendered:
            print()
          _console_line(f"[stream error] {code}: {msg}")
          continue

        payload = env.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        if frame_type == "stream_start":
          if stream_start_at is None:
            stream_start_at = time.perf_counter()
          _console_start("Orac: ")
          stream_rendered = True
        elif frame_type == "text_delta":
          if first_text_delta_at is None:
            first_text_delta_at = time.perf_counter()
          if not stream_rendered:
            _console_start("Orac: ")
            stream_rendered = True
          delta = payload.get("delta", "")
          delta_text = slave_client.strip_reasoning_tags_from_delta(
            str(delta)
          )
          if delta_text:
            orac_transcript_parts.append(delta_text)
            _send_display_event(
              display_sender,
              "transcript.orac.delta",
              session_id=voice_session_id,
              turn_id=req_id,
              text=delta_text,
            )
          print(
            delta_text,
            end="",
            flush=True,
          )
        elif frame_type == "text_chunk":
          if first_text_chunk_at is None:
            first_text_chunk_at = time.perf_counter()
          logger.debug("Speech text chunk received for existing TTS path")
          playback_expected = True
        elif frame_type in {"stream_end", "stream_cancelled"}:
          stream_end_at = time.perf_counter()
          stream_finished = True
          if stream_rendered:
            print()
          if frame_type == "stream_cancelled":
            _console_line("[stream cancelled]")
        elif frame_type == "tts_playback_started":
          playback_started = True
          playback_started_count += 1
          if first_tts_started_at is None:
            first_tts_started_at = time.perf_counter()
          playback_expected = True
          playback_terminal = False
          interruption_policy.begin_output_turn(output_turn_id=req_id)
          _console_line("TTS playback started.")
          if display_sender is not None:
            display_sender.send_state(
              "speaking",
              message="Speaking",
              session_id=voice_session_id,
              turn_id=req_id,
            )
          if barge_in_controller is not None:
            logger.info("TTS playback started; enabling barge-in monitor")
            _start_barge_in_monitor()
          else:
            logger.debug("TTS playback started")
          continue
        elif frame_type in {
          "tts_playback_finished",
          "tts_playback_cancelled",
          "tts_playback_error",
        }:
          if not interruption_policy.accept_output_event(output_turn_id=req_id):
            logger.debug(
              "Ignoring stale playback event {} for turn {}",
              frame_type,
              req_id,
            )
            continue
          playback_terminal = True
          _console_line(f"{frame_type} received.")
          logger.debug("{} received", frame_type)
          if frame_type == "tts_playback_cancelled":
            playback_cancelled = True
            interruption_policy.mark_output_cancelled(output_turn_id=req_id)
            maybe_status = _maybe_finish_turn()
            _stop_barge_in_monitor()
            if maybe_status is not None:
              return maybe_status
            continue
          if frame_type == "tts_playback_finished":
            playback_finished_count += 1
            last_tts_finished_at = time.perf_counter()
            interruption_policy.mark_output_finished(output_turn_id=req_id)
            continue
        elif frame_type == "voice_turn_complete":
          playback_terminal = True
          interruption_policy.mark_turn_complete(output_turn_id=req_id)
          if last_tts_finished_at is None:
            last_tts_finished_at = time.perf_counter()
          if display_sender is not None:
            display_sender.send_state(
              "idle",
              message="Listening for wake word",
              session_id=voice_session_id,
              turn_id=req_id,
            )
          _stop_barge_in_monitor()
          _log_response_timing("voice-complete")
          return 1 if stream_error_seen else 0
        continue

      if frame_type != "response":
        _console_line("Unexpected protocol frame from Orac.")
        _log_response_timing("unexpected-frame")
        return 1

      err_obj = env.get("error")
      if isinstance(err_obj, dict) and err_obj:
        _log_response_timing("server-error")
        if not stream_error_seen:
          code = err_obj.get("code", "SERVER_ERROR")
          msg = err_obj.get("message", "Unknown error")
          _console_line(f"[server error] {code}: {msg}")
          if display_sender is not None:
            display_sender.send_state(
              "error",
              message=str(msg),
              session_id=voice_session_id,
              turn_id=req_id,
            )
        return 1

      payload = env.get("payload")
      content = payload.get("content") if isinstance(payload, dict) else ""
      final_text = slave_client.strip_reasoning_tags(str(content))
      if not final_text:
        final_text = "".join(orac_transcript_parts).strip()
      if stream_end_at is None and not stream_rendered:
        stream_end_at = time.perf_counter()
      _send_display_event(
        display_sender,
        "transcript.orac.final",
        session_id=voice_session_id,
        turn_id=req_id,
        text=final_text,
      )
      if stream_rendered or stream_finished:
        print()
        final_response_status = 1 if stream_error_seen else 0
        if not stream_finished:
          logger.debug(
            "Final response received; waiting for stream_end event"
          )
          continue
        if playback_expected:
          logger.debug(
            "Final response received; waiting for remaining playback events"
          )
          continue
        maybe_status = _maybe_finish_turn()
        if maybe_status is not None:
          return maybe_status
        continue

      _console_line(f"Orac: {final_text}")
      if display_sender is not None:
        display_sender.send_state(
          "idle",
          message="Listening for wake word",
          session_id=voice_session_id,
          turn_id=req_id,
        )
      _log_response_timing("response")
      return 0
  finally:
    _stop_barge_in_monitor()


async def _send_voice_cancel_request(
  *,
  host: str,
  port: int,
  session_id: str,
  turn_id: str | None,
  reason: str,
) -> None:
  """Send a best-effort voice cancellation request on a fresh connection."""
  if not session_id:
    logger.warning("Cannot send voice cancellation without a session id")
    return
  from view import slave as slave_client

  reader: asyncio.StreamReader | None = None
  writer: asyncio.StreamWriter | None = None
  try:
    reader, writer = await asyncio.open_connection(host, port)
    req_env = slave_client.build_voice_cancel_request(
      session_id=session_id,
      turn_id=turn_id,
      scope="turn" if turn_id else "active",
      reason=reason,
    )
    writer.write((json.dumps(req_env, ensure_ascii=False) + "\n").encode("utf-8"))
    await writer.drain()
    await asyncio.wait_for(reader.readline(), timeout=5.0)
    logger.info(
      "Sent voice cancellation for session={} turn={}",
      session_id,
      turn_id or "-",
    )
  except Exception as exc:
    logger.warning("Voice cancellation request failed: {}", exc)
  finally:
    if writer is not None:
      writer.close()
      await writer.wait_closed()


async def _stream_orac_prompt(*, host: str, port: int, prompt_text: str) -> int:
  """Submit recognised text to Orac using the same TCP prompt route as slave.py."""
  reader, writer = await asyncio.open_connection(host, port)
  try:
    return await _send_orac_prompt(
      reader=reader,
      writer=writer,
      prompt_text=prompt_text,
    )
  finally:
    writer.close()
    await writer.wait_closed()


def _listen_once(args: argparse.Namespace) -> int:
  """Record one microphone sample, transcribe it, and print the text."""
  try:
    _session_id, _turn_id, recognised_text = _transcribe_once(args)
  except NoSpeechDetectedError as exc:
    _console_line(str(exc))
    return 0
  except KeyboardInterrupt:
    _console_line("Speech input cancelled.")
    return 130
  except EOFError:
    _console_line("Speech input closed before recording.")
    return 130
  except Exception as exc:
    logger.error("Local speech input failed: {}", exc)
    _console_line(f"Local speech input failed: {exc}")
    return 1

  _console_line(recognised_text)
  return 0


async def _voice_session_async(args: argparse.Namespace) -> int:
  """Run a repeated local spoken conversation over one Orac connection."""
  session_id = f"local-voice-session-{uuid.uuid4().hex[:12]}"
  exit_phrases = _load_exit_phrases()
  wake_rearm_seconds = _load_wake_rearm_seconds()
  capture = SoundDeviceAudioCapture.from_config(record_seconds=args.record_seconds)
  stt_engine = FasterWhisperSttEngine.from_config()
  barge_in_controller = _create_barge_in_controller()
  display_sender = DisplayEventSender.from_config()
  _send_configured_runtime_identity(
    display_sender,
    session_id=session_id,
  )
  display_sender.send_state(
    "initialising",
    message="Initialising voice session",
    session_id=session_id,
  )
  activation_listener = _create_activation_listener(
    args=args,
    exit_phrases=exit_phrases,
    capture=capture,
    stt_engine=stt_engine,
  )
  reader: asyncio.StreamReader | None = None
  writer: asyncio.StreamWriter | None = None
  capture_next_command = False

  try:
    while True:
      try:
        if not capture_next_command:
          display_sender.send_state(
            "idle",
            message="Listening for wake word",
            session_id=session_id,
          )
          activation = activation_listener.wait_for_activation(
            session_id=session_id
          )
          if activation.exit_requested:
            _console_line("Voice session closed.")
            return 0
          if not activation.activated:
            continue
          
          display_sender.send_state(
            "wake_detected",
            message="Wake word detected",
            session_id=session_id,
          )
          # Brief delay to allow the "wake_detected" animation to play
          time.sleep(0.4)
        else:
          logger.info("Barge-in return mode: command_capture")
          capture_next_command = False

        _session_id, _turn_id, recognised_text = _transcribe_once(
          args,
          capture=capture,
          stt_engine=stt_engine,
          session_id=session_id,
          prompt=None,
          display_sender=display_sender,
        )
      except NoSpeechDetectedError as exc:
        _console_line(str(exc))
        display_sender.send_state(
          "idle",
          message="Listening for wake word",
          session_id=session_id,
        )
        continue
      except EOFError:
        _console_line("Voice session closed.")
        return 0

      if not recognised_text.strip():
        _console_line("No speech recognised.")
        continue

      _console_line(f"You: {recognised_text}")
      if _is_exit_phrase(recognised_text, exit_phrases):
        _console_line("Voice session closed.")
        return 0

      if reader is None or writer is None:
        reader, writer = await asyncio.open_connection(args.host, args.port)
      status = await _send_orac_prompt(
        reader=reader,
        writer=writer,
        prompt_text=recognised_text,
        barge_in_controller=barge_in_controller,
        voice_session_id=session_id,
        cancel_host=args.host,
        cancel_port=args.port,
        display_sender=display_sender,
      )
      if barge_in_controller is not None and barge_in_controller.interrupted:
        if writer is not None:
          writer.close()
          await writer.wait_closed()
        reader = None
        writer = None
        barge_in_controller.clear_interruption()
        if barge_in_controller.config.return_mode == "command_capture":
          capture_next_command = True
        continue
      if status != 0:
        logger.warning(
          "Voice turn ended with status {}; returning to wake listening",
          status,
        )
        _console_line("Voice turn failed; returning to wake listening.")
        if display_sender is not None:
          display_sender.send_state(
            "idle",
            message="Listening for wake word",
            session_id=session_id,
          )
        if writer is not None:
          writer.close()
          await writer.wait_closed()
        reader = None
        writer = None
        continue
      if wake_rearm_seconds > 0:
        logger.debug(
          "Waiting {:.1f}s before re-arming wake-word detection",
          wake_rearm_seconds,
        )
        _console_line(
          f"Re-arming wake word in {wake_rearm_seconds:.1f}s..."
        )
        time.sleep(wake_rearm_seconds)
  finally:
    display_sender.send(
      DisplayEvent(
        event="state_changed",
        state="idle",
        message="Listening for wake word",
        session_id=session_id,
      )
    )
    capture.cancel()
    if barge_in_controller is not None:
      barge_in_controller.stop()
    activation_listener.close()
    if writer is not None:
      writer.close()
      await writer.wait_closed()


def _voice_session(args: argparse.Namespace) -> int:
  """Run repeated local spoken turns until exit."""
  try:
    return asyncio.run(_voice_session_async(args))
  except ConnectionRefusedError:
    _console_line(
      f"Could not connect to Orac at {args.host}:{args.port}. Is it running?"
    )
    return 1
  except VoiceActivationError as exc:
    _console_line(f"Voice activation failed: {exc}")
    return 2
  except KeyboardInterrupt:
    _console_line("Voice session cancelled.")
    return 130
  except EOFError:
    _console_line("Voice session closed.")
    return 0
  except Exception as exc:
    logger.error("Local voice session failed: {}", exc)
    _console_line(f"Local voice session failed: {exc}")
    return 1


def _voice_turn(args: argparse.Namespace) -> int:
  """Record speech, transcribe it, and submit it to Orac."""
  display_sender = DisplayEventSender.from_config()
  _send_configured_runtime_identity(display_sender)
  try:
    _session_id, _turn_id, recognised_text = _transcribe_once(
      args,
      display_sender=display_sender
    )
  except NoSpeechDetectedError as exc:
    _console_line(str(exc))
    display_sender.send_state("idle", message=str(exc))
    return 0
  except KeyboardInterrupt:
    _console_line("Voice turn cancelled.")
    display_sender.send_state("idle", message="Turn cancelled")
    return 130
  except EOFError:
    _console_line("Voice turn closed before recording.")
    return 130
  except Exception as exc:
    logger.error("Local voice turn failed before Orac submission: {}", exc)
    _console_line(f"Local voice turn failed: {exc}")
    display_sender.send_state("error", message=f"Turn failed: {exc}")
    return 1

  if not recognised_text.strip():
    _console_line("No speech recognised.")
    display_sender.send_state("idle", message="No speech recognised")
    return 2

  _console_line(f"You: {recognised_text}")
  try:
    return asyncio.run(
      _stream_orac_prompt(
        host=args.host,
        port=args.port,
        prompt_text=recognised_text,
        display_sender=display_sender,
      )
    )
  except ConnectionRefusedError:
    _console_line(
      f"Could not connect to Orac at {args.host}:{args.port}. Is it running?"
    )
    return 1
  except KeyboardInterrupt:
    _console_line("Voice turn cancelled.")
    return 130
  except Exception as exc:
    logger.error("Local voice turn failed: {}", exc)
    _console_line(f"Local voice turn failed: {exc}")
    return 1


def _start_display_bridge(
  args: argparse.Namespace,
) -> subprocess.Popen[bytes] | None:
  """Start the browser display bridge when browser mode is requested."""
  if not args.browser_mode and not args.display_browser and not args.buttons:
    return None

  node_path = shutil.which("node")
  if node_path is None:
    raise RuntimeError("node is required for --browser-mode display bridge")

  bridge_script = resolve_orac_home() / DEFAULT_DISPLAY_BRIDGE_SCRIPT
  if not bridge_script.is_file():
    raise FileNotFoundError(f"Display bridge not found: {bridge_script}")

  environment = os.environ.copy()
  environment["ORAC_DISPLAY_BUTTONS_VISIBLE"] = (
    "true" if args.buttons else "false"
  )
  environment.setdefault("ORAC_DISPLAY_SHOW_TRANSCRIPT_PANELS", "true")

  process = subprocess.Popen(
    [node_path, str(bridge_script)],
    cwd=str(bridge_script.parent),
    env=environment,
  )
  logger.info("Started Orac display bridge with PID {}", process.pid)
  return process


def _stop_display_bridge(process: subprocess.Popen[bytes] | None) -> None:
  """Stop a browser display bridge process started by this command."""
  if process is None or process.poll() is not None:
    return

  process.terminate()
  try:
    process.wait(timeout=3.0)
  except subprocess.TimeoutExpired:
    process.kill()
    process.wait(timeout=3.0)


def main() -> int:
  """Run the local voice CLI.

  Returns:
    int: Process exit code.
  """
  parser = build_parser()
  args = parser.parse_args()
  display_bridge = None
  try:
    display_bridge = _start_display_bridge(args)
    if args.tts_test is not None:
      return _run_tts_test(args)
    if args.listen_once:
      return _listen_once(args)
    if args.voice_turn:
      return _voice_turn(args)
    if args.voice_session:
      return _voice_session(args)
    parser.print_help()
    return 2
  except Exception as exc:
    logger.error("Unable to start local voice mode: {}", exc)
    _console_line(f"Unable to start local voice mode: {exc}")
    return 1
  finally:
    _stop_display_bridge(display_bridge)


if __name__ == "__main__":
  raise SystemExit(main())
