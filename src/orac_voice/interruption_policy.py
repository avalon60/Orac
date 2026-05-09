"""Local interruption policy for Orac voice sessions.

This module separates acoustic interruption signals from semantic policy.
"""

# Author: Clive Bostock
# Date: 2026-05-09
# Description: Separates acoustic interruption signals from semantic policy.

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re


class InterruptionAction(str, Enum):
  """Semantic outcome of one interruption evaluation."""

  IGNORE = "ignore"
  PAUSE = "pause"
  RESUME = "resume"
  INTERRUPT = "interrupt"


class InterruptionState(str, Enum):
  """Current semantic interruption state for one output turn."""

  IDLE = "idle"
  SPEAKING = "speaking"
  PAUSED = "paused"
  INTERRUPTED = "interrupted"


@dataclass(frozen=True)
class InterruptionDecision:
  """Result of evaluating one acoustic interruption event."""

  action: InterruptionAction
  reason: str = ""
  output_turn_id: str = ""
  speech_ms: int = 0
  recognised_words: int = 0
  is_stale: bool = False
  is_duplicate: bool = False


@dataclass
class InterruptionPolicy:
  """Turn-level interruption policy for local Orac voice playback."""

  allow_interruptions: bool = True
  min_speech_ms: int = 250
  min_recognised_words: int = 0
  resume_false_interruption_enabled: bool = True
  state: InterruptionState = InterruptionState.IDLE
  output_turn_id: str | None = None
  _paused_output_turn_id: str | None = None
  _closed_output_turn_ids: set[str] = field(default_factory=set)
  _interrupted_output_turn_ids: set[str] = field(default_factory=set)

  def begin_output_turn(self, *, output_turn_id: str) -> bool:
    """Mark a new output turn as actively speaking.

    Args:
      output_turn_id (str): Turn identifier for the active output.

    Returns:
      bool: True when the turn became the active speaking turn.
    """
    if not output_turn_id:
      return False
    if output_turn_id in self._closed_output_turn_ids:
      return False
    self.output_turn_id = output_turn_id
    self._paused_output_turn_id = None
    self.state = InterruptionState.SPEAKING
    return True

  def accept_output_event(self, *, output_turn_id: str) -> bool:
    """Return whether a playback event still belongs to the active turn."""
    if not output_turn_id:
      return False
    if output_turn_id in self._closed_output_turn_ids:
      return False
    return output_turn_id == self.output_turn_id

  def consider_acoustic_interrupt(
    self,
    *,
    output_turn_id: str,
    speech_ms: int,
    recognised_text: str | None = None,
  ) -> InterruptionDecision:
    """Evaluate one acoustic interruption event.

    Args:
      output_turn_id (str): Turn currently producing audio.
      speech_ms (int): Sustained speech duration in milliseconds.
      recognised_text (str | None): Optional recognised transcript.

    Returns:
      InterruptionDecision: Semantic outcome of the event.
    """
    if not self.allow_interruptions:
      return InterruptionDecision(
        action=InterruptionAction.IGNORE,
        reason="interruptions disabled",
        output_turn_id=output_turn_id,
        speech_ms=speech_ms,
      )
    if output_turn_id in self._interrupted_output_turn_ids:
      return InterruptionDecision(
        action=InterruptionAction.IGNORE,
        reason="duplicate interruption",
        output_turn_id=output_turn_id,
        speech_ms=speech_ms,
        is_duplicate=True,
      )
    if not self.accept_output_event(output_turn_id=output_turn_id):
      return InterruptionDecision(
        action=InterruptionAction.IGNORE,
        reason="stale output turn",
        output_turn_id=output_turn_id,
        speech_ms=speech_ms,
        is_stale=True,
      )
    if speech_ms < self.min_speech_ms:
      return InterruptionDecision(
        action=InterruptionAction.IGNORE,
        reason="speech below interruption threshold",
        output_turn_id=output_turn_id,
        speech_ms=speech_ms,
      )

    recognised_words = _count_words(recognised_text)
    if (
      recognised_text is not None
      and self.min_recognised_words > 0
      and recognised_words < self.min_recognised_words
    ):
      if self.resume_false_interruption_enabled:
        self.state = InterruptionState.PAUSED
        self._paused_output_turn_id = output_turn_id
        return InterruptionDecision(
          action=InterruptionAction.PAUSE,
          reason="false interruption; waiting to resume",
          output_turn_id=output_turn_id,
          speech_ms=speech_ms,
          recognised_words=recognised_words,
        )
      return InterruptionDecision(
        action=InterruptionAction.IGNORE,
        reason="recognised words below minimum",
        output_turn_id=output_turn_id,
        speech_ms=speech_ms,
        recognised_words=recognised_words,
      )

    self.state = InterruptionState.INTERRUPTED
    self._interrupted_output_turn_ids.add(output_turn_id)
    self._closed_output_turn_ids.add(output_turn_id)
    self.output_turn_id = None
    self._paused_output_turn_id = None
    return InterruptionDecision(
      action=InterruptionAction.INTERRUPT,
      reason="confirmed interruption",
      output_turn_id=output_turn_id,
      speech_ms=speech_ms,
      recognised_words=recognised_words,
    )

  def resume_false_interruption(
    self,
    *,
    output_turn_id: str,
  ) -> InterruptionDecision:
    """Resume a false interruption when no real interrupt was confirmed."""
    if (
      self.state != InterruptionState.PAUSED
      or self._paused_output_turn_id != output_turn_id
      or output_turn_id in self._closed_output_turn_ids
    ):
      return InterruptionDecision(
        action=InterruptionAction.IGNORE,
        reason="no paused interruption to resume",
        output_turn_id=output_turn_id,
        is_stale=output_turn_id in self._closed_output_turn_ids,
      )

    self.state = InterruptionState.SPEAKING
    self.output_turn_id = output_turn_id
    self._paused_output_turn_id = None
    return InterruptionDecision(
      action=InterruptionAction.RESUME,
      reason="false interruption resumed",
      output_turn_id=output_turn_id,
    )

  def mark_output_finished(self, *, output_turn_id: str) -> bool:
    """Record a playback completion event without changing semantic state."""
    return self.accept_output_event(output_turn_id=output_turn_id)

  def mark_output_cancelled(self, *, output_turn_id: str) -> bool:
    """Invalidate an interrupted output turn so stale events are ignored."""
    if not output_turn_id:
      return False
    self._closed_output_turn_ids.add(output_turn_id)
    if self.output_turn_id == output_turn_id:
      self.output_turn_id = None
    if self._paused_output_turn_id == output_turn_id:
      self._paused_output_turn_id = None
    self.state = InterruptionState.INTERRUPTED
    return True

  def mark_turn_complete(self, *, output_turn_id: str) -> bool:
    """Close a turn after the authoritative completion signal arrives."""
    if not self.accept_output_event(output_turn_id=output_turn_id):
      if output_turn_id in self._closed_output_turn_ids:
        self.state = InterruptionState.IDLE
        return True
      return False

    self._closed_output_turn_ids.add(output_turn_id)
    if self.output_turn_id == output_turn_id:
      self.output_turn_id = None
    if self._paused_output_turn_id == output_turn_id:
      self._paused_output_turn_id = None
    self.state = InterruptionState.IDLE
    return True


def _count_words(text: str | None) -> int:
  """Count recognised words in a transcript-like string."""
  if not text:
    return 0
  return len(re.findall(r"\b[\w']+\b", text))
