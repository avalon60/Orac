"""Queue-based text-to-speech worker for Orac.

# Author: Clive Bostock
# Date: 2026-05-09
# Description: Provides non-blocking queued local TTS processing.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import queue
import re
import threading
import uuid

from loguru import logger

from orac_voice.aec import AcousticEchoCanceller
from orac_voice.aec import NullAcousticEchoCanceller
from orac_voice.aec import create_aec_adapter_from_config
from orac_voice.aec import validate_aec_frame
from orac_voice.aec import validate_aec_frame_format
from orac_voice.audio_playback import AudioPlayback
from orac_voice.audio_playback import LocalAudioPlayback
from orac_voice.audio_playback import NativeAudioPlayback
from orac_voice.audio_playback import PlaybackFrameHandler
from orac_voice.playback_reference_resampler import PlaybackReferenceResampler
from orac_voice.tts_kokoro import KokoroTtsEngine
from orac_voice.tts_voice_catalog import KOKORO_PROVIDER
from orac_voice.tts_voice_catalog import PIPER_PROVIDER
from orac_voice.tts_piper import TtsEngine
from orac_voice.tts_piper import PiperTtsEngine
from orac_voice.tts_piper import resolve_orac_home
from orac_voice.voice_events import (
  VoiceError,
  VoiceEvent,
  VoiceTextChunk,
  VoiceTtsEnded,
  VoiceTtsPlaybackCancelled,
  VoiceTtsPlaybackError,
  VoiceTtsPlaybackFinished,
  VoiceTtsPlaybackStarted,
  VoiceTtsStarted,
  VoiceTurnCancelled,
  VoiceTurnComplete,
)
from lib.config_mgr import ConfigManager


EventHandler = Callable[[VoiceEvent], None]
VoiceEngineFactory = Callable[[dict[str, object] | None], TtsEngine]

_MONTH_NAMES = (
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
)
_SPOKEN_DATE_RE = re.compile(
  r"\b([0-3]?\d)(?:st|nd|rd|th)?\s+("
  + "|".join(_MONTH_NAMES)
  + r")(\s+\d{4})?\b",
  re.I,
)


@dataclass
class _TurnLifecycle:
  """Playback lifecycle counters for one session turn."""

  queued: int = 0
  terminal: int = 0
  input_complete: bool = False
  complete_emitted: bool = False


class FallbackTtsEngine:
  """TTS engine wrapper that falls back when the primary engine fails."""

  def __init__(
    self,
    *,
    primary: TtsEngine,
    fallback: TtsEngine,
    primary_name: str,
    fallback_name: str,
  ) -> None:
    """Initialise fallback synthesis.

    Args:
      primary (TtsEngine): Preferred synthesis backend.
      fallback (TtsEngine): Backup synthesis backend.
      primary_name (str): Human-readable primary backend name.
      fallback_name (str): Human-readable fallback backend name.
    """
    self.primary = primary
    self.fallback = fallback
    self.primary_name = primary_name
    self.fallback_name = fallback_name

  def synthesise_to_wav(
    self,
    text: str,
    *,
    session_id: str,
    turn_id: str,
  ) -> Path:
    """Synthesise with the primary engine, then fallback on failure."""
    try:
      return self.primary.synthesise_to_wav(
        text,
        session_id=session_id,
        turn_id=turn_id,
      )
    except Exception as exc:
      logger.warning(
        "TTS backend '{}' failed; falling back to '{}': {}",
        self.primary_name,
        self.fallback_name,
        exc,
      )
      return self.fallback.synthesise_to_wav(
        text,
        session_id=session_id,
        turn_id=turn_id,
      )

  def cancel(self) -> None:
    """Cancel active synthesis in both engines where supported."""
    for engine in (self.primary, self.fallback):
      cancel = getattr(engine, "cancel", None)
      if callable(cancel):
        cancel()


class _PlaybackReferenceBridge:
  """Turn-scoped playback reference state for native local playback.

  The bridge keeps the resampler isolated from stale playback turns and
  records simple per-turn counters for future AEC wiring and diagnostics.
  """

  def __init__(
    self,
    *,
    aec_adapter: AcousticEchoCanceller | None = None,
  ) -> None:
    """Initialise the playback reference bridge."""
    self._aec_adapter = aec_adapter or NullAcousticEchoCanceller()
    self._resampler = PlaybackReferenceResampler(
      on_reference_frame=self._handle_reference_frame,
    )
    self.current_session_id: str | None = None
    self.current_turn_id: str | None = None
    self.current_turn_frames_emitted = 0
    self.last_completed_session_id: str | None = None
    self.last_completed_turn_id: str | None = None
    self.last_completed_frames_emitted = 0
    self.last_completed_reason: str | None = None
    self.last_cancelled_session_id: str | None = None
    self.last_cancelled_turn_id: str | None = None
    self.last_cancelled_frames_emitted = 0
    self.last_cancelled_reason: str | None = None

  def _handle_reference_frame(
    self,
    frame: bytes,
    sample_rate: int,
    channels: int,
    sample_width: int,
  ) -> None:
    """Forward one validated playback reference frame to the AEC adapter.

    Args:
      frame (bytes): Playback reference frame bytes.
      sample_rate (int): Reference sample rate in hertz.
      channels (int): Reference channel count.
      sample_width (int): Reference sample width in bytes.
    """
    validate_aec_frame_format(
      sample_rate=sample_rate,
      channels=channels,
      sample_width=sample_width,
      label="Playback reference AEC frame",
    )
    validate_aec_frame(frame, label="Playback reference AEC frame")
    self._aec_adapter.process_reverse_frame(frame)

  def begin_turn(self, *, session_id: str, turn_id: str) -> None:
    """Start or switch to a new playback turn.

    Args:
      session_id (str): Session identifier.
      turn_id (str): Turn identifier.
    """
    if not session_id or not turn_id:
      return
    if (
      self.current_session_id == session_id
      and self.current_turn_id == turn_id
    ):
      return
    if self.current_turn_id is not None:
      logger.warning(
        (
          "Resetting stale playback reference turn: session={} turn={} "
          "next_session={} next_turn={}"
        ),
        self.current_session_id,
        self.current_turn_id,
        session_id,
        turn_id,
      )
    self._resampler.reset()
    self._aec_adapter.reset()
    self.current_session_id = session_id
    self.current_turn_id = turn_id
    self.current_turn_frames_emitted = 0
    logger.debug(
      "Playback reference turn started: session={} turn={}",
      session_id,
      turn_id,
    )

  def handle_playback_frame(
    self,
    frame_bytes: bytes,
    sample_rate: int,
    channels: int,
    sample_width: int,
  ) -> int:
    """Resample one playback chunk for the active turn.

    Args:
      frame_bytes (bytes): Raw PCM bytes from native playback.
      sample_rate (int): Input sample rate in hertz.
      channels (int): Input channel count.
      sample_width (int): Input sample width in bytes.

    Returns:
      int: Number of reference frames emitted.
    """
    if self.current_turn_id is None:
      logger.debug(
        (
          "Discarding playback reference chunk without an active turn: "
          "sample_rate={} channels={} sample_width={} frame_bytes={}"
        ),
        sample_rate,
        channels,
        sample_width,
        len(frame_bytes),
      )
      return 0

    emitted = self._resampler.handle_playback_frame(
      frame_bytes,
      sample_rate,
      channels,
      sample_width,
    )
    if emitted:
      self.current_turn_frames_emitted += emitted
      logger.debug(
        (
          "Playback reference frames emitted: session={} turn={} "
          "emitted={} total={}"
        ),
        self.current_session_id,
        self.current_turn_id,
        emitted,
        self.current_turn_frames_emitted,
      )
    return emitted

  def complete_turn(
    self,
    *,
    session_id: str,
    turn_id: str,
    reason: str = "completed",
  ) -> int:
    """Finish the active playback turn and emit any pending tail frame.

    Args:
      session_id (str): Session identifier.
      turn_id (str): Turn identifier.
      reason (str): Completion reason.

    Returns:
      int: Number of reference frames emitted during finalisation.
    """
    if not self._matches_active_turn(session_id=session_id, turn_id=turn_id):
      return 0
    emitted = self._resampler.flush(pad_final=True)
    total = self.current_turn_frames_emitted + emitted
    self.last_completed_session_id = session_id
    self.last_completed_turn_id = turn_id
    self.last_completed_frames_emitted = total
    self.last_completed_reason = reason
    logger.info(
      (
        "Playback reference turn completed: session={} turn={} "
        "frames_emitted={} reason={}"
      ),
      session_id,
      turn_id,
      total,
      reason,
    )
    self._aec_adapter.reset()
    self._clear_active_turn()
    return emitted

  def cancel_turn(
    self,
    *,
    session_id: str,
    turn_id: str,
    reason: str = "cancelled",
  ) -> int:
    """Cancel the active playback turn and discard buffered reference PCM.

    Args:
      session_id (str): Session identifier.
      turn_id (str): Turn identifier.
      reason (str): Cancellation reason.

    Returns:
      int: Number of discarded reference frames.
    """
    if not self._matches_active_turn(session_id=session_id, turn_id=turn_id):
      return 0
    discarded = self.current_turn_frames_emitted
    self.last_cancelled_session_id = session_id
    self.last_cancelled_turn_id = turn_id
    self.last_cancelled_frames_emitted = discarded
    self.last_cancelled_reason = reason
    logger.info(
      (
        "Playback reference turn cancelled: session={} turn={} "
        "frames_emitted={} reason={}"
      ),
      session_id,
      turn_id,
      discarded,
      reason,
    )
    self._resampler.reset()
    self._aec_adapter.reset()
    self._clear_active_turn()
    return discarded

  def reset(self, *, reason: str = "reset") -> None:
    """Discard any active playback turn without finalising it."""
    if self.current_turn_id is None:
      return
    logger.debug(
      "Playback reference turn reset: session={} turn={} reason={}",
      self.current_session_id,
      self.current_turn_id,
      reason,
    )
    self._resampler.reset()
    self._aec_adapter.reset()
    self._clear_active_turn()

  def _matches_active_turn(self, *, session_id: str, turn_id: str) -> bool:
    """Return whether the supplied turn matches the active playback turn."""
    return (
      self.current_session_id == session_id
      and self.current_turn_id == turn_id
    )

  def _clear_active_turn(self) -> None:
    """Clear the active turn bookkeeping."""
    self.current_session_id = None
    self.current_turn_id = None
    self.current_turn_frames_emitted = 0


def speech_safe_text(text: str) -> str:
  """Return text with lightweight Markdown markers removed for TTS.

  Args:
    text (str): Text intended for speech synthesis.

  Returns:
    str: Text cleaned for audible playback.
  """
  clean_text = str(text or "").strip()
  if not clean_text:
    return ""

  clean_text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean_text)
  clean_text = clean_text.replace("`", "")
  clean_text = re.sub(r"(?<!\w)[*_]{1,3}([^*_]+)[*_]{1,3}(?!\w)", r"\1", clean_text)
  clean_text = re.sub(r"[*_]{2,}", "", clean_text)
  clean_text = _normalise_spoken_dates(clean_text)
  clean_text = re.sub(r"\s+", " ", clean_text)
  return clean_text.strip()


def _normalise_spoken_dates(text: str) -> str:
  """Return dates in a form that TTS engines pronounce more naturally."""

  def _replace(match: re.Match[str]) -> str:
    day = int(match.group(1))
    if day < 1 or day > 31:
      return match.group(0)

    month = match.group(2)
    year = match.group(3) or ""
    return f"{day}{_ordinal_suffix(day)} of {month}{year}"

  return _SPOKEN_DATE_RE.sub(_replace, text)


def _ordinal_suffix(value: int) -> str:
  """Return an English ordinal suffix for a positive integer."""
  if 10 <= value % 100 <= 20:
    return "th"
  return {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")


def _has_speakable_content(text: str) -> bool:
  """Return whether text contains content worth sending to TTS.

  Args:
    text (str): Candidate speech text.

  Returns:
    bool: True when the text contains at least one letter or digit.
  """
  return any(char.isalnum() for char in text)


def _create_piper_engine(
  *,
  config_path,
  voice_name: str | None,
  voice_dir: str | None,
  voice_model_path: str | None = None,
) -> PiperTtsEngine:
  """Create the configured Piper engine."""
  return PiperTtsEngine.from_config(
    config_file_path=config_path,
    voice_name=voice_name,
    voice_dir=voice_dir,
    voice_model_path=voice_model_path,
  )


def _create_kokoro_engine(
  *,
  config_path,
  voice_name: str | None,
) -> KokoroTtsEngine:
  """Create the configured Kokoro engine."""
  return KokoroTtsEngine.from_config(
    config_file_path=config_path,
    voice_name=voice_name,
  )


def _create_tts_engine_from_config(
  *,
  engine: str,
  config_mgr: ConfigManager,
  config_path,
  voice_name: str | None,
  voice_dir: str | None,
) -> TtsEngine:
  """Create a TTS engine from Orac voice configuration."""
  if engine == "piper":
    logger.info("Local TTS backend selected: piper")
    return _create_piper_engine(
      config_path=config_path,
      voice_name=voice_name,
      voice_dir=voice_dir,
    )

  if engine == "kokoro":
    primary = _create_kokoro_engine(
      config_path=config_path,
      voice_name=voice_name,
    )
    fallback_name = config_mgr.config_value(
      "voice",
      "tts_fallback_engine",
      default="piper",
    ).strip().lower()
    if fallback_name in {"", "none", "disabled"}:
      logger.info("Local TTS backend selected: kokoro")
      return primary
    if fallback_name != "piper":
      raise RuntimeError(
        f"Unsupported voice.tts_fallback_engine: {fallback_name}"
      )

    try:
      fallback = _create_piper_engine(
        config_path=config_path,
        voice_name=None,
        voice_dir=voice_dir,
      )
    except Exception as exc:
      logger.warning(
        "Kokoro selected but Piper fallback could not be initialised: {}",
        exc,
      )
      logger.info("Local TTS backend selected: kokoro")
      return primary

    logger.info("Local TTS backend selected: kokoro with piper fallback")
    return FallbackTtsEngine(
      primary=primary,
      fallback=fallback,
      primary_name="kokoro",
      fallback_name="piper",
    )

  raise RuntimeError(f"Unsupported voice TTS engine: {engine}")


def _create_tts_engine_for_voice_selection(
  *,
  selection: dict[str, object] | None,
  config_mgr: ConfigManager,
  config_path,
  voice_dir: str | None,
) -> TtsEngine:
  """Create a provider-specific TTS engine for a selected catalogue row."""
  if not selection:
    engine = config_mgr.config_value(
      "voice",
      "tts_engine",
      default=PIPER_PROVIDER,
    ).strip().lower()
    return _create_tts_engine_from_config(
      engine=engine,
      config_mgr=config_mgr,
      config_path=config_path,
      voice_name=None,
      voice_dir=voice_dir,
    )

  provider = str(selection.get("provider_code") or "").strip().lower()
  voice_id = str(selection.get("provider_voice_id") or "").strip()
  if provider == PIPER_PROVIDER:
    logger.info("Local TTS backend selected from preference: piper {}", voice_id)
    return _create_piper_engine(
      config_path=config_path,
      voice_name=voice_id,
      voice_dir=voice_dir,
      voice_model_path=str(selection.get("model_path") or "") or None,
    )
  if provider == KOKORO_PROVIDER:
    primary = _create_kokoro_engine(
      config_path=config_path,
      voice_name=voice_id,
    )
    fallback_name = config_mgr.config_value(
      "voice",
      "tts_fallback_engine",
      default=PIPER_PROVIDER,
    ).strip().lower()
    if fallback_name in {"", "none", "disabled"}:
      logger.info(
        "Local TTS backend selected from preference: kokoro {}",
        voice_id,
      )
      return primary
    if fallback_name != PIPER_PROVIDER:
      raise RuntimeError(
        f"Unsupported voice.tts_fallback_engine: {fallback_name}"
      )
    try:
      fallback = _create_piper_engine(
        config_path=config_path,
        voice_name=None,
        voice_dir=voice_dir,
      )
    except Exception as exc:
      logger.warning(
        "Kokoro selected from preference but Piper fallback failed: {}",
        exc,
      )
      return primary
    logger.info("Local TTS backend selected from preference: kokoro {}", voice_id)
    return FallbackTtsEngine(
      primary=primary,
      fallback=fallback,
      primary_name=KOKORO_PROVIDER,
      fallback_name=PIPER_PROVIDER,
    )

  raise RuntimeError(f"Unsupported selected TTS provider: {provider}")


def create_local_tts_worker_from_config(
  *,
  event_handler: EventHandler | None = None,
  voice_name: str | None = None,
  voice_dir: str | None = None,
  playback_frame_handler: PlaybackFrameHandler | None = None,
) -> TtsWorker | None:
  """Create a local TTS worker from the existing Orac voice config.

  Args:
    event_handler (EventHandler | None): Optional voice event callback.
    voice_name (str | None): Optional voice override.
    voice_dir (str | None): Optional voice directory override.
    playback_frame_handler (PlaybackFrameHandler | None): Optional PCM hook.

  Returns:
    TtsWorker | None: Worker when voice is enabled, otherwise None.

  Raises:
    RuntimeError: If voice config requests an unsupported mode or engine.
  """
  orac_home = resolve_orac_home()
  config_path = orac_home / "resources" / "config" / "orac.ini"
  config_mgr = ConfigManager(config_file_path=config_path)
  enabled = config_mgr.bool_config_value("voice", "enabled", default=False)
  if not enabled:
    logger.info("Local voice output disabled by [voice] enabled=false")
    return None

  mode = config_mgr.config_value("voice", "mode", default="local").strip().lower()
  if mode != "local":
    raise RuntimeError(f"Unsupported voice mode for local worker: {mode}")

  engine = config_mgr.config_value(
    "voice",
    "tts_engine",
    default="piper",
  ).strip().lower()

  playback_backend = config_mgr.config_value(
    "voice",
    "playback_backend",
    default="shell",
  ).strip().lower()
  audio_playback = _create_audio_playback(
    playback_backend=playback_backend,
    playback_frame_handler=playback_frame_handler,
    config_mgr=config_mgr,
  )
  logger.info("Local playback backend selected: {}", playback_backend)
  aec_adapter = create_aec_adapter_from_config(config_mgr)

  worker = TtsWorker(
    tts_engine=_create_tts_engine_from_config(
      engine=engine,
      config_mgr=config_mgr,
      config_path=config_path,
      voice_name=voice_name,
      voice_dir=voice_dir,
    ),
    voice_engine_factory=lambda selection: _create_tts_engine_for_voice_selection(
      selection=selection,
      config_mgr=config_mgr,
      config_path=config_path,
      voice_dir=voice_dir,
    ),
    audio_playback=audio_playback,
    event_handler=event_handler,
    aec_adapter=aec_adapter,
  )
  if playback_backend == "native":
    worker.enable_playback_reference_resampling(aec_adapter=aec_adapter)
  return worker


def _create_audio_playback(
  *,
  playback_backend: str,
  playback_frame_handler: PlaybackFrameHandler | None,
  config_mgr: ConfigManager,
) -> AudioPlayback:
  """Create the configured local playback backend.

  Args:
    playback_backend (str): Playback backend name.
    playback_frame_handler (PlaybackFrameHandler | None): Optional PCM hook.
    config_mgr (ConfigManager): Orac config manager.

  Returns:
    AudioPlayback: Configured playback implementation.

  Raises:
    RuntimeError: If the backend is unsupported.
  """
  cleaned = playback_backend.strip().lower()
  if cleaned == "shell":
    return LocalAudioPlayback()
  if cleaned == "native":
    frame_ms = int(
      config_mgr.int_config_value(
        "voice",
        "playback_frame_ms",
        default=10,
      )
    )
    return NativeAudioPlayback(
      on_playback_frame=playback_frame_handler,
      frame_ms=frame_ms,
    )
  raise RuntimeError(f"Unsupported voice.playback_backend: {playback_backend}")


class TtsWorker:
  """Background worker that synthesises and plays queued text chunks."""

  def __init__(
    self,
    *,
    tts_engine: TtsEngine,
    voice_engine_factory: VoiceEngineFactory | None = None,
    audio_playback: AudioPlayback,
    event_handler: EventHandler | None = None,
    aec_adapter: AcousticEchoCanceller | None = None,
  ) -> None:
    """Initialise the worker.

    Args:
      tts_engine (TtsEngine): TTS engine implementation.
      voice_engine_factory (VoiceEngineFactory | None): Optional factory for
        provider-specific engines selected from catalogue rows.
      audio_playback (AudioPlayback): Audio playback implementation.
      event_handler (EventHandler | None): Optional event callback.
      aec_adapter (AcousticEchoCanceller | None): Optional AEC adapter for
        playback reference frames.
    """
    self.tts_engine = tts_engine
    self.voice_engine_factory = voice_engine_factory
    self.audio_playback = audio_playback
    self.event_handler = event_handler
    self._queue: queue.Queue[VoiceTextChunk | None] = queue.Queue()
    self._thread: threading.Thread | None = None
    self._stop_requested = threading.Event()
    self._state_lock = threading.Lock()
    self._cancelled_sessions: set[str] = set()
    self._cancelled_turns: set[tuple[str, str]] = set()
    self._active_chunk: VoiceTextChunk | None = None
    self._voice_engine_cache: dict[str, TtsEngine] = {}
    self._turn_states: dict[tuple[str, str], _TurnLifecycle] = {}
    self._playback_reference_bridge: _PlaybackReferenceBridge | None = None
    self._aec_adapter = aec_adapter
    self.error_count = 0
    self.last_error: VoiceError | None = None

  @property
  def is_running(self) -> bool:
    """Return whether the worker thread is alive.

    Returns:
      bool: True when running.
    """
    return self._thread is not None and self._thread.is_alive()

  def start(self) -> None:
    """Start the background worker thread."""
    if self.is_running:
      return

    self._stop_requested.clear()
    self._thread = threading.Thread(
      target=self._run,
      name="orac-tts-worker",
      daemon=True,
    )
    self._thread.start()

  def stop(self, *, drain: bool = True, timeout: float | None = 10.0) -> None:
    """Stop the background worker.

    Args:
      drain (bool): Whether to process queued chunks before stopping.
      timeout (float | None): Maximum seconds to wait for the thread.
    """
    if not self.is_running:
      return

    if not drain:
      self.cancel_all(reason="worker stopped")
    self._stop_requested.set()
    self._queue.put(None)
    if self._thread is not None:
      self._thread.join(timeout=timeout)
    logger.info("TTS worker stopped cleanly")

  def enqueue_text(
    self,
    *,
    session_id: str,
    turn_id: str,
    text: str,
    tts_voice: dict[str, object] | None = None,
  ) -> bool:
    """Queue a text chunk for speech without blocking the caller.

    Args:
      session_id (str): Session identifier.
      turn_id (str): Turn identifier.
      text (str): Speech-friendly text chunk.
      tts_voice (dict[str, object] | None): Optional selected voice row.

    Returns:
      bool: True when a non-empty chunk was queued.
    """
    clean_text = speech_safe_text(text)
    if not clean_text:
      return False
    if not _has_speakable_content(clean_text):
      logger.debug("Skipping punctuation-only TTS chunk: {!r}", clean_text)
      return False
    if self._is_cancelled(session_id=session_id, turn_id=turn_id):
      logger.debug(
        "Discarding late TTS chunk for cancelled session={} turn={}",
        session_id,
        turn_id,
      )
      return False
    self._queue.put(
      VoiceTextChunk(
        session_id=session_id,
        turn_id=turn_id,
        utterance_id=f"utt-{uuid.uuid4().hex[:12]}",
        text=clean_text,
        tts_voice=tts_voice,
      )
    )
    self._mark_turn_queued(session_id=session_id, turn_id=turn_id)
    return True

  def mark_turn_input_complete(self, *, session_id: str, turn_id: str) -> None:
    """Mark that no more speech chunks will be queued for this turn."""
    with self._state_lock:
      state = self._turn_states.setdefault(
        (session_id, turn_id),
        _TurnLifecycle(),
      )
      state.input_complete = True
    self._maybe_emit_turn_complete(session_id=session_id, turn_id=turn_id)

  def cancel_turn(self, *, session_id: str, turn_id: str) -> int:
    """Cancel queued and active speech for a specific turn."""
    logger.info(
      "TTS cancellation requested for session={} turn={}",
      session_id,
      turn_id,
    )
    with self._state_lock:
      self._cancelled_turns.add((session_id, turn_id))
      state = self._turn_states.setdefault(
        (session_id, turn_id),
        _TurnLifecycle(),
      )
      state.input_complete = True
    removed = self._discard_queued(
      session_id=session_id,
      turn_id=turn_id,
      reason="turn cancelled",
    )
    self._cancel_active_if_matches(session_id=session_id, turn_id=turn_id)
    logger.info("Discarded {} queued TTS chunk(s) for cancelled turn", removed)
    return removed

  def clear_cancelled_turn(self, *, session_id: str, turn_id: str) -> None:
    """Clear remembered cancellation state for a completed turn.

    Args:
      session_id (str): Session identifier.
      turn_id (str): Turn identifier.
    """
    with self._state_lock:
      self._cancelled_turns.discard((session_id, turn_id))

  def cancel_session(self, *, session_id: str) -> int:
    """Cancel queued and active speech for a session."""
    logger.info("TTS cancellation requested for session={}", session_id)
    with self._state_lock:
      self._cancelled_sessions.add(session_id)
      for (state_session_id, _turn_id), state in self._turn_states.items():
        if state_session_id == session_id:
          state.input_complete = True
    removed = self._discard_queued(
      session_id=session_id,
      turn_id=None,
      reason="session cancelled",
    )
    self._cancel_active_if_matches(session_id=session_id, turn_id=None)
    logger.info("Discarded {} queued TTS chunk(s) for cancelled session", removed)
    return removed

  def cancel_active_turn(self, *, session_id: str) -> int:
    """Cancel the currently active turn for a session, if any."""
    with self._state_lock:
      active = self._active_chunk
    if active is None or active.session_id != session_id:
      return 0
    return self.cancel_turn(session_id=session_id, turn_id=active.turn_id)

  def cancel_all(self, *, reason: str = "cancelled") -> int:
    """Cancel all queued and active speech immediately."""
    logger.info("TTS cancellation requested for all sessions: {}", reason)
    self._reset_playback_reference_turn(reason=reason)
    removed = self.clear(reason=reason)
    self._cancel_active_processes()
    return removed

  def enable_playback_reference_resampling(
    self,
    *,
    aec_adapter: AcousticEchoCanceller | None = None,
  ) -> None:
    """Attach the playback reference resampler to native playback.

    The resampler is used only for the experimental native playback path.

    Args:
      aec_adapter (AcousticEchoCanceller | None): Optional AEC adapter for
        reverse playback reference frames.
    """
    if self._playback_reference_bridge is None:
      self._playback_reference_bridge = _PlaybackReferenceBridge(
        aec_adapter=aec_adapter or self._aec_adapter,
      )
      if isinstance(self.audio_playback, NativeAudioPlayback):
        self.audio_playback.set_playback_frame_handler(
          self._playback_reference_bridge.handle_playback_frame,
        )
      logger.info(
        "Playback reference resampling enabled for native playback"
      )

  def _begin_playback_reference_turn(
    self,
    *,
    session_id: str,
    turn_id: str,
  ) -> None:
    """Begin or reuse the playback reference turn for one chunk."""
    if self._playback_reference_bridge is None:
      return
    self._playback_reference_bridge.begin_turn(
      session_id=session_id,
      turn_id=turn_id,
    )

  def _complete_playback_reference_turn(
    self,
    *,
    session_id: str,
    turn_id: str,
    reason: str = "completed",
  ) -> None:
    """Complete the active playback reference turn."""
    if self._playback_reference_bridge is None:
      return
    self._playback_reference_bridge.complete_turn(
      session_id=session_id,
      turn_id=turn_id,
      reason=reason,
    )

  def _cancel_playback_reference_turn(
    self,
    *,
    session_id: str,
    turn_id: str,
    reason: str = "cancelled",
  ) -> None:
    """Cancel the active playback reference turn."""
    if self._playback_reference_bridge is None:
      return
    self._playback_reference_bridge.cancel_turn(
      session_id=session_id,
      turn_id=turn_id,
      reason=reason,
    )

  def _reset_playback_reference_turn(self, *, reason: str = "reset") -> None:
    """Reset the active playback reference turn without finalising it."""
    if self._playback_reference_bridge is None:
      return
    self._playback_reference_bridge.reset(reason=reason)

  def clear(self, *, reason: str = "cancelled") -> int:
    """Clear queued chunks as a placeholder for future barge-in support.

    Args:
      reason (str): Cancellation reason.

    Returns:
      int: Number of queued chunks removed.
    """
    removed = 0
    while True:
      try:
        item = self._queue.get_nowait()
      except queue.Empty:
        break
      if item is not None:
        removed += 1
        self._emit(
          VoiceTurnCancelled(
            session_id=item.session_id,
            turn_id=item.turn_id,
            reason=reason,
          )
        )
        self._mark_turn_terminal(
          session_id=item.session_id,
          turn_id=item.turn_id,
          reason=reason,
        )
      self._queue.task_done()
    return removed

  def _discard_queued(
    self,
    *,
    session_id: str,
    turn_id: str | None,
    reason: str,
  ) -> int:
    """Discard queued chunks matching a session/turn."""
    removed = 0
    kept: list[VoiceTextChunk | None] = []
    while True:
      try:
        item = self._queue.get_nowait()
      except queue.Empty:
        break

      if item is None:
        kept.append(item)
        self._queue.task_done()
        continue

      matches_session = item.session_id == session_id
      matches_turn = turn_id is None or item.turn_id == turn_id
      if matches_session and matches_turn:
        removed += 1
        self._emit(
          VoiceTurnCancelled(
            session_id=item.session_id,
            turn_id=item.turn_id,
            reason=reason,
          )
        )
        self._mark_turn_terminal(
          session_id=item.session_id,
          turn_id=item.turn_id,
          reason=reason,
        )
        self._queue.task_done()
      else:
        kept.append(item)
        self._queue.task_done()

    for item in kept:
      self._queue.put(item)
    return removed

  def _is_cancelled(self, *, session_id: str, turn_id: str) -> bool:
    """Return whether a chunk should be rejected for cancellation."""
    with self._state_lock:
      return (
        session_id in self._cancelled_sessions
        or (session_id, turn_id) in self._cancelled_turns
      )

  def _cancel_active_if_matches(
    self,
    *,
    session_id: str,
    turn_id: str | None,
  ) -> None:
    """Interrupt active work if it belongs to the cancelled scope."""
    with self._state_lock:
      active = self._active_chunk
    if active is None:
      return
    if active.session_id != session_id:
      return
    if turn_id is not None and active.turn_id != turn_id:
      return
    self._emit(
      VoiceTurnCancelled(
        session_id=active.session_id,
        turn_id=active.turn_id,
        reason="active speech cancelled",
      )
    )
    self._cancel_playback_reference_turn(
      session_id=active.session_id,
      turn_id=active.turn_id,
      reason="active speech cancelled",
    )
    self._emit(
      VoiceTtsPlaybackCancelled(
        session_id=active.session_id,
        turn_id=active.turn_id,
        utterance_id=active.utterance_id,
        reason="active speech cancelled",
      )
    )
    self._mark_turn_terminal(
      session_id=active.session_id,
      turn_id=active.turn_id,
      reason="cancelled",
    )
    self._cancel_active_processes()

  def _cancel_active_processes(self) -> None:
    """Interrupt active synthesis and playback processes."""
    for engine in self._all_tts_engines():
      tts_cancel = getattr(engine, "cancel", None)
      if callable(tts_cancel):
        tts_cancel()
    playback_cancel = getattr(self.audio_playback, "cancel", None)
    if callable(playback_cancel):
      playback_cancel()

  def _all_tts_engines(self) -> list[TtsEngine]:
    """Return every engine that may currently own synthesis work."""
    engines = [self.tts_engine]
    engines.extend(self._voice_engine_cache.values())
    return list(dict.fromkeys(engines))

  def _tts_engine_for_chunk(self, chunk: VoiceTextChunk) -> TtsEngine:
    """Return the selected TTS engine for a queued chunk."""
    selection = chunk.tts_voice
    if not selection or self.voice_engine_factory is None:
      return self.tts_engine

    voice_key = str(selection.get("tts_voice_key") or "").strip()
    if not voice_key:
      return self.tts_engine

    cached = self._voice_engine_cache.get(voice_key)
    if cached is not None:
      return cached

    engine = self.voice_engine_factory(selection)
    self._voice_engine_cache[voice_key] = engine
    return engine

  def wait_until_idle(self, *, timeout: float | None = None) -> bool:
    """Wait until all currently queued chunks have been processed.

    Args:
      timeout (float | None): Optional maximum wait time.

    Returns:
      bool: True when the queue drained before timeout.
    """
    finished = threading.Event()

    def waiter() -> None:
      self._queue.join()
      finished.set()

    thread = threading.Thread(target=waiter, daemon=True)
    thread.start()
    return finished.wait(timeout=timeout)

  def _emit(self, event: VoiceEvent) -> None:
    """Emit a worker event to the optional callback."""
    if self.event_handler is None:
      return
    self.event_handler(event)

  def _mark_turn_queued(self, *, session_id: str, turn_id: str) -> None:
    """Record that one more utterance was accepted for a turn."""
    with self._state_lock:
      state = self._turn_states.setdefault(
        (session_id, turn_id),
        _TurnLifecycle(),
      )
      state.queued += 1

  def _mark_turn_terminal(
    self,
    *,
    session_id: str,
    turn_id: str,
    reason: str = "completed",
  ) -> bool:
    """Record that one utterance for the turn is terminal."""
    should_emit = False
    with self._state_lock:
      state = self._turn_states.setdefault(
        (session_id, turn_id),
        _TurnLifecycle(),
      )
      state.terminal += 1
      if (
        state.input_complete
        and not state.complete_emitted
        and state.terminal >= state.queued
      ):
        state.complete_emitted = True
        should_emit = True
        self._turn_states.pop((session_id, turn_id), None)
    if should_emit:
      self._emit(
        VoiceTurnComplete(
          session_id=session_id,
          turn_id=turn_id,
          reason=reason,
        )
      )
    return should_emit

  def _maybe_emit_turn_complete(
    self,
    *,
    session_id: str,
    turn_id: str,
  ) -> bool:
    """Emit turn completion when the accepted chunks have all finished."""
    should_emit = False
    with self._state_lock:
      state = self._turn_states.get((session_id, turn_id))
      if (
        state is not None
        and state.input_complete
        and not state.complete_emitted
        and state.terminal >= state.queued
      ):
        state.complete_emitted = True
        should_emit = True
        self._turn_states.pop((session_id, turn_id), None)
    if should_emit:
      self._emit(
        VoiceTurnComplete(
          session_id=session_id,
          turn_id=turn_id,
        )
      )
    return should_emit

  def _run(self) -> None:
    """Process queued speech chunks until stopped."""
    while True:
      item = self._queue.get()
      try:
        if item is None:
          return
        if self._is_cancelled(session_id=item.session_id, turn_id=item.turn_id):
          logger.debug(
            "Skipping cancelled TTS chunk for session={} turn={}",
            item.session_id,
            item.turn_id,
          )
          continue
        self._process_chunk(item)
      finally:
        self._queue.task_done()

  def _process_chunk(self, chunk: VoiceTextChunk) -> None:
    """Synthesise and play one text chunk."""
    self._begin_playback_reference_turn(
      session_id=chunk.session_id,
      turn_id=chunk.turn_id,
    )
    self._emit(
      VoiceTtsStarted(
        session_id=chunk.session_id,
        turn_id=chunk.turn_id,
        text_length=len(chunk.text),
      )
    )
    with self._state_lock:
      self._active_chunk = chunk
    try:
      if self._is_cancelled(session_id=chunk.session_id, turn_id=chunk.turn_id):
        return
      tts_engine = self._tts_engine_for_chunk(chunk)
      wav_path = tts_engine.synthesise_to_wav(
        chunk.text,
        session_id=chunk.session_id,
        turn_id=chunk.turn_id,
      )
      if self._is_cancelled(session_id=chunk.session_id, turn_id=chunk.turn_id):
        self._cancel_playback_reference_turn(
          session_id=chunk.session_id,
          turn_id=chunk.turn_id,
          reason="cancelled",
        )
        return
      self._emit(
        VoiceTtsPlaybackStarted(
          session_id=chunk.session_id,
          turn_id=chunk.turn_id,
          utterance_id=chunk.utterance_id,
          wav_path=wav_path,
        )
      )
      self.audio_playback.play_wav(wav_path)
      if self._is_cancelled(session_id=chunk.session_id, turn_id=chunk.turn_id):
        self._cancel_playback_reference_turn(
          session_id=chunk.session_id,
          turn_id=chunk.turn_id,
          reason="cancelled",
        )
        return
      self._emit(
        VoiceTtsPlaybackFinished(
          session_id=chunk.session_id,
          turn_id=chunk.turn_id,
          utterance_id=chunk.utterance_id,
          wav_path=wav_path,
        )
      )
      turn_complete = self._mark_turn_terminal(
        session_id=chunk.session_id,
        turn_id=chunk.turn_id,
      )
      if turn_complete:
        self._complete_playback_reference_turn(
          session_id=chunk.session_id,
          turn_id=chunk.turn_id,
          reason="completed",
        )
      self._emit(
        VoiceTtsEnded(
          session_id=chunk.session_id,
          turn_id=chunk.turn_id,
          wav_path=wav_path,
        )
      )
    except Exception as exc:
      if self._is_cancelled(session_id=chunk.session_id, turn_id=chunk.turn_id):
        self._emit(
          VoiceTtsPlaybackCancelled(
            session_id=chunk.session_id,
            turn_id=chunk.turn_id,
            utterance_id=chunk.utterance_id,
            reason="cancelled",
          )
        )
        self._cancel_playback_reference_turn(
          session_id=chunk.session_id,
          turn_id=chunk.turn_id,
          reason="cancelled",
        )
        logger.info(
          "Voice chunk stopped after cancellation for session={} turn={}",
          chunk.session_id,
          chunk.turn_id,
        )
        return
      logger.warning("Voice chunk failed: {}", exc)
      self.error_count += 1
      self._emit(
        VoiceTtsPlaybackError(
          session_id=chunk.session_id,
          turn_id=chunk.turn_id,
          utterance_id=chunk.utterance_id,
          message=str(exc),
        )
      )
      self._mark_turn_terminal(
        session_id=chunk.session_id,
        turn_id=chunk.turn_id,
        reason="error",
      )
      self._cancel_playback_reference_turn(
        session_id=chunk.session_id,
        turn_id=chunk.turn_id,
        reason="error",
      )
      self.last_error = VoiceError(
        session_id=chunk.session_id,
        turn_id=chunk.turn_id,
        message=str(exc),
      )
      self._emit(self.last_error)
    finally:
      with self._state_lock:
        if self._active_chunk is chunk:
          self._active_chunk = None
