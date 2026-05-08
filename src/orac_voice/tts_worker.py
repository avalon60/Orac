"""Queue-based text-to-speech worker for Orac.

# Author: Clive Bostock
# Date: 2026-05-04
# Description: Provides non-blocking queued local TTS processing.
"""

from __future__ import annotations

from collections.abc import Callable
import queue
import re
import threading
import uuid

from loguru import logger

from orac_voice.audio_playback import AudioPlayback
from orac_voice.audio_playback import LocalAudioPlayback
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
)
from lib.config_mgr import ConfigManager


EventHandler = Callable[[VoiceEvent], None]


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
  clean_text = re.sub(r"\s+", " ", clean_text)
  return clean_text.strip()


def _has_speakable_content(text: str) -> bool:
  """Return whether text contains content worth sending to TTS.

  Args:
    text (str): Candidate speech text.

  Returns:
    bool: True when the text contains at least one letter or digit.
  """
  return any(char.isalnum() for char in text)


def create_local_tts_worker_from_config(
  *,
  event_handler: EventHandler | None = None,
  voice_name: str | None = None,
  voice_dir: str | None = None,
) -> TtsWorker | None:
  """Create a local TTS worker from the existing Orac voice config.

  Args:
    event_handler (EventHandler | None): Optional voice event callback.
    voice_name (str | None): Optional voice override.
    voice_dir (str | None): Optional voice directory override.

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
  if engine != "piper":
    raise RuntimeError(f"Unsupported voice TTS engine: {engine}")

  return TtsWorker(
    tts_engine=PiperTtsEngine.from_config(
      config_file_path=config_path,
      voice_name=voice_name,
      voice_dir=voice_dir,
    ),
    audio_playback=LocalAudioPlayback(),
    event_handler=event_handler,
  )


class TtsWorker:
  """Background worker that synthesises and plays queued text chunks."""

  def __init__(
    self,
    *,
    tts_engine: TtsEngine,
    audio_playback: AudioPlayback,
    event_handler: EventHandler | None = None,
  ) -> None:
    """Initialise the worker.

    Args:
      tts_engine (TtsEngine): TTS engine implementation.
      audio_playback (AudioPlayback): Audio playback implementation.
      event_handler (EventHandler | None): Optional event callback.
    """
    self.tts_engine = tts_engine
    self.audio_playback = audio_playback
    self.event_handler = event_handler
    self._queue: queue.Queue[VoiceTextChunk | None] = queue.Queue()
    self._thread: threading.Thread | None = None
    self._stop_requested = threading.Event()
    self._state_lock = threading.Lock()
    self._cancelled_sessions: set[str] = set()
    self._cancelled_turns: set[tuple[str, str]] = set()
    self._active_chunk: VoiceTextChunk | None = None
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

  def enqueue_text(self, *, session_id: str, turn_id: str, text: str) -> bool:
    """Queue a text chunk for speech without blocking the caller.

    Args:
      session_id (str): Session identifier.
      turn_id (str): Turn identifier.
      text (str): Speech-friendly text chunk.

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
      )
    )
    return True

  def cancel_turn(self, *, session_id: str, turn_id: str) -> int:
    """Cancel queued and active speech for a specific turn."""
    logger.info(
      "TTS cancellation requested for session={} turn={}",
      session_id,
      turn_id,
    )
    with self._state_lock:
      self._cancelled_turns.add((session_id, turn_id))
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
    removed = self.clear(reason=reason)
    self._cancel_active_processes()
    return removed

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
    self._emit(
      VoiceTtsPlaybackCancelled(
        session_id=active.session_id,
        turn_id=active.turn_id,
        utterance_id=active.utterance_id,
        reason="active speech cancelled",
      )
    )
    self._cancel_active_processes()

  def _cancel_active_processes(self) -> None:
    """Interrupt active synthesis and playback processes."""
    tts_cancel = getattr(self.tts_engine, "cancel", None)
    if callable(tts_cancel):
      tts_cancel()
    playback_cancel = getattr(self.audio_playback, "cancel", None)
    if callable(playback_cancel):
      playback_cancel()

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
      wav_path = self.tts_engine.synthesise_to_wav(
        chunk.text,
        session_id=chunk.session_id,
        turn_id=chunk.turn_id,
      )
      if self._is_cancelled(session_id=chunk.session_id, turn_id=chunk.turn_id):
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
        return
      self._emit(
        VoiceTtsPlaybackFinished(
          session_id=chunk.session_id,
          turn_id=chunk.turn_id,
          utterance_id=chunk.utterance_id,
          wav_path=wav_path,
        )
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
