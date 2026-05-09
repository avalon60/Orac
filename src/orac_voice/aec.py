"""Acoustic echo cancellation interfaces for Orac voice."""
# Author: Clive Bostock
# Date: 2026-05-09
# Description: Defines Orac-owned AEC frame contracts and a null adapter.

from __future__ import annotations

from typing import Protocol


AEC_SAMPLE_RATE = 16000
AEC_FRAME_DURATION_MS = 10
AEC_CHANNELS = 1
AEC_SAMPLE_WIDTH_BYTES = 2
AEC_SAMPLES_PER_FRAME = 160
AEC_BYTES_PER_FRAME = 320


class AcousticEchoCanceller(Protocol):
  """Protocol for Orac-owned acoustic echo cancellation adapters."""

  def process_reverse_frame(self, frame: bytes) -> None:
    """Accept one playback reference frame.

    Args:
      frame (bytes): Exact 10 ms mono int16 16 kHz PCM frame.
    """

  def process_capture_frame(self, frame: bytes) -> bytes:
    """Process one microphone capture frame.

    Args:
      frame (bytes): Exact 10 ms mono int16 16 kHz PCM frame.

    Returns:
      bytes: Processed capture frame in the same format.
    """

  def reset(self) -> None:
    """Reset turn-scoped AEC state."""


def validate_aec_frame(frame: bytes, *, label: str = "AEC frame") -> None:
  """Validate that a frame matches the Orac AEC PCM contract.

  Args:
    frame (bytes): Raw PCM frame to validate.
    label (str): Human-readable frame label for error messages.

  Raises:
    TypeError: If the frame is not bytes-like.
    ValueError: If the frame size does not match the AEC contract.
  """
  if not isinstance(frame, bytes):
    raise TypeError(f"{label} must be bytes")
  if len(frame) != AEC_BYTES_PER_FRAME:
    raise ValueError(
      (
        f"{label} must be {AEC_BYTES_PER_FRAME} bytes "
        f"({AEC_SAMPLE_RATE} Hz, {AEC_FRAME_DURATION_MS} ms, "
        f"{AEC_CHANNELS} channel, {AEC_SAMPLE_WIDTH_BYTES} bytes/sample)"
      )
    )


def validate_aec_frame_format(
  *,
  sample_rate: int,
  channels: int,
  sample_width: int,
  label: str = "AEC frame",
) -> None:
  """Validate non-size metadata for the Orac AEC PCM contract.

  Args:
    sample_rate (int): Frame sample rate in hertz.
    channels (int): Frame channel count.
    sample_width (int): Frame sample width in bytes.
    label (str): Human-readable frame label for error messages.

  Raises:
    ValueError: If the format does not match the AEC contract.
  """
  if sample_rate != AEC_SAMPLE_RATE:
    raise ValueError(f"{label} sample rate must be {AEC_SAMPLE_RATE} Hz")
  if channels != AEC_CHANNELS:
    raise ValueError(f"{label} channel count must be {AEC_CHANNELS}")
  if sample_width != AEC_SAMPLE_WIDTH_BYTES:
    raise ValueError(
      f"{label} sample width must be {AEC_SAMPLE_WIDTH_BYTES} bytes"
    )


class NullAcousticEchoCanceller:
  """No-op AEC adapter used until a real backend is introduced."""

  def process_reverse_frame(self, frame: bytes) -> None:
    """Accept a playback reference frame without side effects.

    Args:
      frame (bytes): Exact 10 ms mono int16 16 kHz PCM frame.
    """
    validate_aec_frame(frame, label="AEC reverse frame")

  def process_capture_frame(self, frame: bytes) -> bytes:
    """Return a microphone capture frame unchanged.

    Args:
      frame (bytes): Exact 10 ms mono int16 16 kHz PCM frame.

    Returns:
      bytes: The original capture frame.
    """
    validate_aec_frame(frame, label="AEC capture frame")
    return frame

  def reset(self) -> None:
    """Reset the no-op adapter state."""
