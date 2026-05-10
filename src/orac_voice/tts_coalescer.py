"""Text chunk coalescing for local Orac voice output.

# Author: Clive Bostock
# Date: 2026-05-05
# Description: Coalesces speech chunks before local TTS playback.
"""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_TTS_COALESCE_MAX_CHARS = 220
DEFAULT_TTS_COALESCE_MIN_CHUNKS = 2


@dataclass
class _PendingSpeech:
  """Pending speech fragments for one session turn."""

  chunks: list[str]

  @property
  def text(self) -> str:
    """Return pending chunks joined with normal spacing."""
    return " ".join(chunk for chunk in self.chunks if chunk).strip()


class TtsChunkCoalescer:
  """Merge short TTS chunks without splitting complete sentences."""

  def __init__(
    self,
    *,
    enabled: bool = True,
    max_chars: int = DEFAULT_TTS_COALESCE_MAX_CHARS,
    min_chunks: int = DEFAULT_TTS_COALESCE_MIN_CHUNKS,
  ) -> None:
    """Initialise the coalescer.

    Args:
      enabled (bool): Whether coalescing is enabled.
      max_chars (int): Maximum preferred coalesced text length. This is
        a flush threshold only; chunks are never split to satisfy it.
      min_chunks (int): Minimum complete chunks to merge before emitting.
    """
    self.enabled = enabled
    self.max_chars = max(40, int(max_chars))
    self.min_chunks = max(1, int(min_chunks))
    self._pending: dict[tuple[str, str], _PendingSpeech] = {}

  def add_chunk(
    self,
    *,
    session_id: str,
    turn_id: str,
    text: str,
  ) -> list[str]:
    """Add a complete speech chunk and return chunks ready for TTS.

    Args:
      session_id (str): Voice session identifier.
      turn_id (str): Voice turn identifier.
      text (str): Complete speech chunk from the stream.

    Returns:
      list[str]: Zero or more complete chunks ready to enqueue.
    """
    clean_text = text.strip()
    if not clean_text:
      return []
    if not self.enabled:
      return [clean_text]

    key = (session_id, turn_id)
    pending = self._pending.get(key)
    if pending is None:
      if len(clean_text) >= self.max_chars:
        return [clean_text]
      self._pending[key] = _PendingSpeech(chunks=[clean_text])
      return []

    existing_text = pending.text
    combined_text = f"{existing_text} {clean_text}".strip()
    ready: list[str] = []
    if existing_text and len(combined_text) > self.max_chars:
      ready.append(existing_text)
      pending.chunks = [clean_text]
      if len(clean_text) >= self.max_chars:
        ready.append(clean_text)
        self._pending.pop(key, None)
      return ready

    pending.chunks.append(clean_text)
    if len(pending.chunks) >= self.min_chunks:
      ready.append(pending.text)
      self._pending.pop(key, None)
    return ready

  def flush(self, *, session_id: str, turn_id: str) -> str | None:
    """Flush pending speech for a turn.

    Args:
      session_id (str): Voice session identifier.
      turn_id (str): Voice turn identifier.

    Returns:
      str | None: Pending text, if any.
    """
    pending = self._pending.pop((session_id, turn_id), None)
    if pending is None:
      return None
    return pending.text or None

  def cancel_turn(self, *, session_id: str, turn_id: str) -> None:
    """Discard pending speech for one turn."""
    self._pending.pop((session_id, turn_id), None)

  def cancel_session(self, *, session_id: str) -> None:
    """Discard pending speech for every turn in a session."""
    for key in list(self._pending):
      if key[0] == session_id:
        self._pending.pop(key, None)

  def clear(self) -> None:
    """Discard all pending speech."""
    self._pending.clear()
