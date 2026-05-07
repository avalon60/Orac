"""Voice activation interfaces for local Orac voice sessions."""
# Author: Clive Bostock
# Date: 2026-05-05
# Description: Provides local voice activation support for Orac.

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


DEFAULT_ACTIVATION_MODE = "openwakeword"
DEFAULT_WAKE_ENGINE = "openwakeword"
DEFAULT_WAKE_PHRASE = "orac"


class VoiceActivationError(RuntimeError):
  """Raised when a configured voice activation mode cannot run."""


@dataclass(frozen=True)
class VoiceActivationResult:
  """Result returned by a voice activation listener.

  Attributes:
    activated (bool): Whether utterance recording should begin.
    exit_requested (bool): Whether the voice session should end.
    reason (str): Human-readable reason for the result.
    wake_phrase (str | None): Wake phrase that triggered activation.
    wake_engine (str | None): Wake engine used for activation.
    backend (str | None): Backend identifier for status publishing.
    wake_word (str | None): Wake-word model or label that fired.
    model (str | None): Model path or model name that fired.
    score (float | None): Detection confidence score when available.
    timestamp (str | None): UTC activation timestamp in ISO-8601 format.
  """

  activated: bool
  exit_requested: bool = False
  reason: str = ""
  wake_phrase: str | None = None
  wake_engine: str | None = None
  backend: str | None = None
  wake_word: str | None = None
  model: str | None = None
  score: float | None = None
  timestamp: str | None = None


class VoiceActivationListener(Protocol):
  """Interface for local voice activation listeners."""

  def wait_for_activation(self, *, session_id: str) -> VoiceActivationResult:
    """Wait until the user activates a voice turn.

    Args:
      session_id (str): Current local voice session id.

    Returns:
      VoiceActivationResult: Activation result.
    """

  def close(self) -> None:
    """Release activation resources."""


class EnterActivationListener:
  """Activation listener that waits for Enter or typed exit text."""

  def __init__(
    self,
    *,
    exit_phrases: set[str],
    prompt: str = "Press Enter to speak, or type exit to quit: ",
  ) -> None:
    """Create an Enter-to-speak activation listener.

    Args:
      exit_phrases (set[str]): Normalised phrases that end the session.
      prompt (str): Console prompt shown before each turn.
    """
    self.exit_phrases = exit_phrases
    self.prompt = prompt

  def wait_for_activation(self, *, session_id: str) -> VoiceActivationResult:
    """Wait for the user to press Enter or type an exit phrase."""
    entered = input(self.prompt)
    if _is_exit_phrase(entered, self.exit_phrases):
      return VoiceActivationResult(
        activated=False,
        exit_requested=True,
        reason="typed exit phrase",
      )
    return VoiceActivationResult(
      activated=True,
      reason="enter key pressed",
    )

  def close(self) -> None:
    """Release activation resources."""


class WakeWordActivationListener:
  """Placeholder activation listener for future wake-word engines."""

  def __init__(
    self,
    *,
    wake_engine: str,
    wake_phrase: str,
    wake_model: str,
    wake_threshold: float,
  ) -> None:
    """Create a wake-word activation listener.

    Args:
      wake_engine (str): Configured wake-word engine name.
      wake_phrase (str): Wake phrase to detect.
      wake_model (str): Optional model path or model name.
      wake_threshold (float): Detection threshold.
    """
    self.wake_engine = wake_engine.strip().lower()
    self.wake_phrase = wake_phrase.strip() or DEFAULT_WAKE_PHRASE
    self.wake_model = wake_model.strip()
    self.wake_threshold = wake_threshold

  def wait_for_activation(self, *, session_id: str) -> VoiceActivationResult:
    """Fail clearly until a supported wake-word engine is installed."""
    if self.wake_engine in {"", "none"}:
      raise VoiceActivationError(
        "activation_mode=wake_word requires a supported wake_engine. "
        "No wake-word engine is currently configured."
      )
    raise VoiceActivationError(
      f"Unsupported wake_engine '{self.wake_engine}'. Wake-word support is "
      "not installed in this build; add a supported listener such as "
      "openWakeWord behind orac_voice.activation before enabling it."
    )

  def close(self) -> None:
    """Release activation resources."""


def _is_exit_phrase(text: str, exit_phrases: set[str]) -> bool:
  """Return whether typed activation text should end the session."""
  cleaned = text.strip().lower().strip(".!?;:")
  return cleaned in exit_phrases
