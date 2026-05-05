"""Internal voice event objects for Orac.

# Author: Clive Bostock
# Date: 2026-05-04
# Description: Defines serialisable voice event dataclasses.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> datetime:
  """Return the current UTC time.

  Returns:
    datetime: Timezone-aware UTC timestamp.
  """
  return datetime.now(timezone.utc)


@dataclass(frozen=True)
class VoiceEvent:
  """Base event for internal voice processing.

  Args:
    session_id (str): Conversation/session identifier.
    turn_id (str): Turn or request identifier.
    created_on (datetime): Event creation timestamp.
  """

  session_id: str
  turn_id: str
  created_on: datetime = field(default_factory=utc_now)

  @property
  def event_type(self) -> str:
    """Return a stable event type name.

    Returns:
      str: Event type name suitable for future JSON serialisation.
    """
    return self.__class__.__name__

  def to_dict(self) -> dict[str, Any]:
    """Return a JSON-friendly dictionary representation.

    Returns:
      dict[str, Any]: Serialisable event fields.
    """
    data = asdict(self)
    data["event_type"] = self.event_type
    data["created_on"] = self.created_on.isoformat()
    for key, value in list(data.items()):
      if isinstance(value, Path):
        data[key] = str(value)
    return data


@dataclass(frozen=True)
class VoiceTextChunk(VoiceEvent):
  """Text chunk intended for speech synthesis.

  Args:
    text (str): Speech-friendly text chunk.
  """

  text: str = ""


@dataclass(frozen=True)
class VoiceTtsStarted(VoiceEvent):
  """Event emitted when synthesis/playback starts for a chunk."""

  text_length: int = 0


@dataclass(frozen=True)
class VoiceTtsEnded(VoiceEvent):
  """Event emitted when synthesis/playback ends for a chunk."""

  wav_path: Path | None = None


@dataclass(frozen=True)
class VoiceTurnCancelled(VoiceEvent):
  """Event emitted when queued voice work is cancelled."""

  reason: str = "cancelled"


@dataclass(frozen=True)
class VoiceError(VoiceEvent):
  """Event emitted when voice synthesis or playback fails."""

  code: str = "VOICE_ERROR"
  message: str = ""


@dataclass(frozen=True)
class VoiceSttStarted(VoiceEvent):
  """Event emitted when speech capture or recognition starts."""

  record_seconds: float | None = None


@dataclass(frozen=True)
class VoiceSttEnded(VoiceEvent):
  """Event emitted when speech capture or recognition ends."""

  wav_path: Path | None = None


@dataclass(frozen=True)
class VoiceSttFinal(VoiceEvent):
  """Event emitted when final recognised speech text is available."""

  text: str = ""


@dataclass(frozen=True)
class VoiceSttError(VoiceEvent):
  """Event emitted when local speech input fails."""

  code: str = "STT_ERROR"
  message: str = ""
