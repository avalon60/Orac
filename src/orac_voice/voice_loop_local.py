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
from pathlib import Path
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
from orac_voice.barge_in import load_barge_in_config
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


DEFAULT_WAIT_SECONDS = 180.0
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_SESSION_EXIT_PHRASES = ("exit", "quit", "stop listening", "goodbye")
DEFAULT_RECORD_MODE = "fixed"
DEFAULT_WAKE_REARM_SECONDS = 1.0
DEFAULT_CONSOLE_TIMESTAMPS = True


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


def _create_barge_in_controller() -> BargeInController | None:
  """Create the configured barge-in controller, if enabled."""
  config_mgr = _voice_config_manager()
  config = load_barge_in_config(config_mgr)
  if not config.enabled:
    return None
  if config.mode == "openwakeword":
    return OpenWakeWordBargeInController(config=config)
  return BargeInController(config=config)


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
) -> tuple[str, str, str]:
  """Capture and transcribe one local microphone sample.

  Args:
    args (argparse.Namespace): Parsed CLI arguments.
    capture (SoundDeviceAudioCapture | None): Optional reusable capture layer.
    stt_engine (FasterWhisperSttEngine | None): Optional reusable STT engine.
    session_id (str | None): Optional stable voice session id.
    prompt (str): Prompt shown before recording.

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

  if prompt is not None:
    entered = input(prompt)
    if _is_exit_phrase(entered, _load_exit_phrases()):
      raise EOFError
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
    _emit(
      VoiceSttEnded(
        session_id=session_id,
        turn_id=turn_id,
        wav_path=wav_path,
      )
    )
    recognised_text = stt_engine.transcribe_wav(wav_path)
    _emit(
      VoiceSttFinal(
        session_id=session_id,
        turn_id=turn_id,
        text=recognised_text,
      )
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

  stream_rendered = False
  stream_finished = False
  stream_error_seen = False
  barge_active = False
  playback_expected = False
  playback_terminal = False
  final_response_status: int | None = None
  barge_event = asyncio.Event()
  barge_result: BargeInResult | None = None
  loop = asyncio.get_running_loop()

  def _on_barge_in(result: BargeInResult) -> None:
    nonlocal barge_result
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

  async def _cancel_interrupted_voice() -> int:
    logger.info("Barge-in interruption received; cancelling active voice")
    _console_line("[interrupted]")
    await _send_voice_cancel_request(
      host=cancel_host or DEFAULT_HOST,
      port=cancel_port or DEFAULT_PORT,
      session_id=voice_session_id or "",
      turn_id=req_id,
      reason=(barge_result.reason if barge_result else "barge-in"),
    )
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
      timeout=(5.0 if final_response_status is not None else slave_client.LLM_TIMEOUT),
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
        return 1
      if read_status == "interrupted":
        return await _cancel_interrupted_voice()

      if not resp_bytes:
        if final_response_status is not None:
          return final_response_status
        return 0

      response_text = resp_bytes.decode("utf-8", errors="replace").strip()
      try:
        env = json.loads(response_text)
      except json.JSONDecodeError as exc:
        logger.error("Invalid JSON from Orac: {}", exc)
        _console_line("Invalid protocol frame from Orac.")
        return 1

      frame_reply_to = env.get("reply_to")
      if frame_reply_to and req_id and str(frame_reply_to) != req_id:
        logger.debug(
          "Skipping stale Orac frame for reply_to={} while awaiting {}",
          frame_reply_to,
          req_id,
        )
        continue

      frame_type = env.get("type")
      if frame_type in slave_client.STREAM_EVENT_TYPES:
        if frame_type == "tts_playback_error":
          err_obj = env.get("error")
          msg = ""
          if isinstance(err_obj, dict):
            msg = str(err_obj.get("message") or "")
          logger.warning("TTS playback error: {}", msg or "unknown")
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
          _console_start("Orac: ")
          stream_rendered = True
        elif frame_type == "text_delta":
          if not stream_rendered:
            _console_start("Orac: ")
            stream_rendered = True
          delta = payload.get("delta", "")
          print(
            slave_client.strip_reasoning_tags_from_delta(str(delta)),
            end="",
            flush=True,
          )
        elif frame_type == "text_chunk":
          logger.debug("Speech text chunk received for existing TTS path")
        elif frame_type in {"stream_end", "stream_cancelled"}:
          stream_finished = True
          if stream_rendered:
            print()
          if frame_type == "stream_cancelled":
            _console_line("[stream cancelled]")
        elif frame_type == "tts_playback_started":
          playback_expected = True
          playback_terminal = False
          _console_line("TTS playback started.")
          if barge_in_controller is not None:
            logger.info("TTS playback started; enabling barge-in monitor")
            _start_barge_in_monitor()
          else:
            logger.debug("TTS playback started")
        elif frame_type in {
          "tts_playback_finished",
          "tts_playback_cancelled",
          "tts_playback_error",
        }:
          playback_terminal = True
          _console_line(f"{frame_type} received.")
          logger.debug("{} received", frame_type)
          _stop_barge_in_monitor()
          if final_response_status is not None:
            return final_response_status
        continue

      if frame_type != "response":
        _console_line("Unexpected protocol frame from Orac.")
        return 1

      err_obj = env.get("error")
      if isinstance(err_obj, dict) and err_obj:
        if not stream_error_seen:
          code = err_obj.get("code", "SERVER_ERROR")
          msg = err_obj.get("message", "Unknown error")
          _console_line(f"[server error] {code}: {msg}")
        return 1

      if stream_rendered or stream_finished:
        print()
        final_response_status = 1 if stream_error_seen else 0
        if playback_expected and not playback_terminal:
          logger.debug(
            "Final response received; waiting for TTS playback terminal event"
          )
          continue
        return final_response_status

      payload = env.get("payload")
      content = payload.get("content") if isinstance(payload, dict) else ""
      _console_line(f"Orac: {slave_client.strip_reasoning_tags(str(content))}")
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
          activation = activation_listener.wait_for_activation(
            session_id=session_id
          )
          if activation.exit_requested:
            _console_line("Voice session closed.")
            return 0
          if not activation.activated:
            continue
        else:
          logger.info("Barge-in return mode: command_capture")
          capture_next_command = False
        _session_id, _turn_id, recognised_text = _transcribe_once(
          args,
          capture=capture,
          stt_engine=stt_engine,
          session_id=session_id,
          prompt=None,
        )
      except NoSpeechDetectedError as exc:
        _console_line(str(exc))
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
        return status
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
  try:
    _session_id, _turn_id, recognised_text = _transcribe_once(args)
  except NoSpeechDetectedError as exc:
    _console_line(str(exc))
    return 0
  except KeyboardInterrupt:
    _console_line("Voice turn cancelled.")
    return 130
  except EOFError:
    _console_line("Voice turn closed before recording.")
    return 130
  except Exception as exc:
    logger.error("Local voice turn failed before Orac submission: {}", exc)
    _console_line(f"Local voice turn failed: {exc}")
    return 1

  if not recognised_text.strip():
    _console_line("No speech recognised.")
    return 2

  _console_line(f"You: {recognised_text}")
  try:
    return asyncio.run(
      _stream_orac_prompt(
        host=args.host,
        port=args.port,
        prompt_text=recognised_text,
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


def main() -> int:
  """Run the local voice CLI.

  Returns:
    int: Process exit code.
  """
  parser = build_parser()
  args = parser.parse_args()

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


if __name__ == "__main__":
  raise SystemExit(main())
