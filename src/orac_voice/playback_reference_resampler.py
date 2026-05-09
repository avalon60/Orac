"""Playback reference resampling for future Orac AEC wiring.

# Author: Clive Bostock
# Date: 2026-05-09
# Description: Converts local playback PCM into exact 16 kHz reference frames.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from loguru import logger


DEFAULT_REFERENCE_OUTPUT_SAMPLE_RATE = 16000
DEFAULT_REFERENCE_OUTPUT_FRAME_MS = 10
DEFAULT_REFERENCE_CHANNELS = 1
DEFAULT_REFERENCE_SAMPLE_WIDTH = 2
PCM16_MIN = -32768
PCM16_MAX = 32767

PlaybackReferenceFrameHandler = Callable[[bytes, int, int, int], None]


class PlaybackReferenceResampler:
  """Convert playback PCM into fixed-rate mono int16 reference frames.

  The resampler is intentionally narrow. It accepts mono little-endian
  16-bit PCM, converts it to a fixed output sample rate, and emits exact
  10 ms frames suitable for a future AEC reverse stream.
  """

  def __init__(
    self,
    *,
    output_sample_rate: int = DEFAULT_REFERENCE_OUTPUT_SAMPLE_RATE,
    output_frame_ms: int = DEFAULT_REFERENCE_OUTPUT_FRAME_MS,
    on_reference_frame: PlaybackReferenceFrameHandler | None = None,
  ) -> None:
    """Initialise the playback reference resampler.

    Args:
      output_sample_rate (int): Exact output sample rate in hertz.
      output_frame_ms (int): Exact output frame duration in milliseconds.
      on_reference_frame (PlaybackReferenceFrameHandler | None): Optional
        callback for each emitted reference frame.

    Raises:
      RuntimeError: If the output frame size is not an exact number of
        samples.
    """
    if output_sample_rate <= 0:
      raise RuntimeError(
        f"Invalid playback reference sample rate: {output_sample_rate}"
      )
    if output_frame_ms <= 0:
      raise RuntimeError(f"Invalid playback reference frame size: {output_frame_ms}")

    exact_output_samples = output_sample_rate * output_frame_ms
    if exact_output_samples % 1000 != 0:
      raise RuntimeError(
        "Playback reference output frame must resolve to an exact sample count"
      )

    self.output_sample_rate = output_sample_rate
    self.output_frame_ms = output_frame_ms
    self.output_frame_samples = exact_output_samples // 1000
    self.output_channels = DEFAULT_REFERENCE_CHANNELS
    self.output_sample_width = DEFAULT_REFERENCE_SAMPLE_WIDTH
    self.output_frame_bytes = (
      self.output_frame_samples
      * self.output_channels
      * self.output_sample_width
    )
    self.on_reference_frame = on_reference_frame

    self._input_sample_rate: int | None = None
    self._input_buffer = np.empty(0, dtype=np.int16)
    self._input_buffer_start_index = 0
    self._next_output_sample_index = 0
    self._output_buffer = bytearray()
    self._total_input_samples_seen = 0
    self._input_frames_seen = 0
    self._frames_emitted = 0

    logger.info(
      (
        "Playback reference resampler initialised: output_sample_rate={} "
        "output_frame_ms={} output_frame_samples={} output_frame_bytes={}"
      ),
      self.output_sample_rate,
      self.output_frame_ms,
      self.output_frame_samples,
      self.output_frame_bytes,
    )

  def handle_playback_frame(
    self,
    frame_bytes: bytes,
    sample_rate: int,
    channels: int,
    sample_width: int,
  ) -> int:
    """Resample one playback PCM chunk and emit complete reference frames.

    Args:
      frame_bytes (bytes): Raw little-endian PCM data.
      sample_rate (int): Input sample rate in hertz.
      channels (int): Input channel count.
      sample_width (int): Input sample width in bytes.

    Returns:
      int: Number of complete reference frames emitted.

    Raises:
      RuntimeError: If the input format is unsupported or changes mid-stream.
    """
    if not frame_bytes:
      return 0

    self._validate_input_format(
      sample_rate=sample_rate,
      channels=channels,
      sample_width=sample_width,
    )
    if self._input_sample_rate is None:
      self._input_sample_rate = sample_rate
      logger.info(
        (
          "Playback reference input established: sample_rate={} channels={} "
          "sample_width={} output_sample_rate={} output_frame_samples={}"
        ),
        sample_rate,
        channels,
        sample_width,
        self.output_sample_rate,
        self.output_frame_samples,
      )
    elif sample_rate != self._input_sample_rate:
      raise RuntimeError(
        "Playback reference sample rate changed mid-stream: "
        f"{self._input_sample_rate} -> {sample_rate}"
      )

    input_samples = np.frombuffer(frame_bytes, dtype="<i2")
    if input_samples.size == 0:
      return 0

    self._input_buffer = np.concatenate((self._input_buffer, input_samples))
    self._total_input_samples_seen += input_samples.size
    self._input_frames_seen += 1
    logger.debug(
      (
        "Playback reference chunk received: sample_rate={} channels={} "
        "sample_width={} input_samples={} input_frames_seen={}"
      ),
      sample_rate,
      channels,
      sample_width,
      input_samples.size,
      self._input_frames_seen,
    )

    emitted = self._emit_complete_reference_frames()
    logger.debug(
      (
        "Playback reference chunk processed: output_sample_rate={} "
        "output_frame_samples={} emitted_frames={} total_emitted={} "
        "pending_output_bytes={}"
      ),
      self.output_sample_rate,
      self.output_frame_samples,
      emitted,
      self._frames_emitted,
      len(self._output_buffer),
    )
    return emitted

  def flush(self, *, pad_final: bool = True) -> int:
    """Drain any buffered reference audio.

    Args:
      pad_final (bool): Whether to zero-pad a final short output frame.

    Returns:
      int: Number of reference frames emitted by the flush.
    """
    emitted = self._emit_reference_frames_from_output_buffer()
    if self._output_buffer:
      if pad_final:
        padded = bytes(self._output_buffer)
        padding = self.output_frame_bytes - len(padded)
        if padding > 0:
          padded += b"\x00" * padding
        emitted += self._emit_reference_frame(padded)
        logger.debug(
          "Playback reference flush emitted padded frame: frame_bytes={}",
          len(padded),
        )
      else:
        logger.debug(
          "Playback reference flush discarded pending output bytes: {}",
          len(self._output_buffer),
        )
      self._output_buffer.clear()

    self._input_buffer = np.empty(0, dtype=np.int16)
    self._input_buffer_start_index = 0
    self._next_output_sample_index = 0
    self._input_sample_rate = None
    self._total_input_samples_seen = 0
    self._input_frames_seen = 0
    self._frames_emitted = 0
    return emitted

  def reset(self) -> None:
    """Discard buffered playback reference state without emitting audio."""
    if self._input_buffer.size or self._output_buffer:
      logger.debug(
        (
          "Playback reference resampler reset: discarded_input_samples={} "
          "discarded_output_bytes={}"
        ),
        self._input_buffer.size,
        len(self._output_buffer),
      )
    self._input_buffer = np.empty(0, dtype=np.int16)
    self._input_buffer_start_index = 0
    self._next_output_sample_index = 0
    self._input_sample_rate = None
    self._output_buffer.clear()
    self._total_input_samples_seen = 0
    self._input_frames_seen = 0
    self._frames_emitted = 0

  def _validate_input_format(
    self,
    *,
    sample_rate: int,
    channels: int,
    sample_width: int,
  ) -> None:
    """Validate the playback PCM format.

    Args:
      sample_rate (int): Input sample rate in hertz.
      channels (int): Input channel count.
      sample_width (int): Input sample width in bytes.

    Raises:
      RuntimeError: If the format is not mono int16 PCM.
    """
    if channels != DEFAULT_REFERENCE_CHANNELS:
      raise RuntimeError(
        "Playback reference resampler only accepts mono playback PCM; "
        f"got channels={channels}"
      )
    if sample_width != DEFAULT_REFERENCE_SAMPLE_WIDTH:
      raise RuntimeError(
        "Playback reference resampler only accepts 16-bit PCM; "
        f"got sample_width={sample_width}"
      )
    if sample_rate <= 0:
      raise RuntimeError(
        f"Invalid playback reference input sample rate: {sample_rate}"
      )

  def _emit_complete_reference_frames(self) -> int:
    """Resample buffered input and emit complete reference frames."""
    if self._input_sample_rate is None:
      return 0
    if self._input_buffer.size == 0:
      return 0

    input_rate = self._input_sample_rate
    output_rate = self.output_sample_rate
    target_output_sample_count = (
      self._total_input_samples_seen * output_rate
    ) // input_rate
    if target_output_sample_count <= self._next_output_sample_index:
      return 0

    output_sample_indices = np.arange(
      self._next_output_sample_index,
      target_output_sample_count,
      dtype=np.float64,
    )
    input_positions = output_sample_indices * (
      float(input_rate) / float(output_rate)
    )
    source_positions = np.arange(
      self._input_buffer.size,
      dtype=np.float64,
    )
    relative_positions = input_positions - self._input_buffer_start_index
    resampled = np.interp(
      relative_positions,
      source_positions,
      self._input_buffer.astype(np.float64, copy=False),
    )
    resampled = np.rint(np.clip(resampled, PCM16_MIN, PCM16_MAX)).astype(
      np.int16
    )
    self._output_buffer.extend(resampled.tobytes())

    self._next_output_sample_index = target_output_sample_count
    consumed_before = (
      self._next_output_sample_index * input_rate
    ) // output_rate
    if consumed_before > self._input_buffer_start_index:
      consumed_samples = consumed_before - self._input_buffer_start_index
      self._input_buffer = self._input_buffer[consumed_samples:]
      self._input_buffer_start_index = consumed_before

    emitted = self._emit_reference_frames_from_output_buffer()
    return emitted

  def _emit_reference_frames_from_output_buffer(self) -> int:
    """Emit complete reference frames from the buffered PCM output."""
    emitted = 0
    while len(self._output_buffer) >= self.output_frame_bytes:
      frame = bytes(self._output_buffer[: self.output_frame_bytes])
      del self._output_buffer[: self.output_frame_bytes]
      emitted += self._emit_reference_frame(frame)

    if emitted:
      logger.debug(
        (
          "Playback reference frames emitted: count={} total={} "
          "output_sample_rate={} output_frame_samples={} pending_output_bytes={}"
        ),
        emitted,
        self._frames_emitted,
        self.output_sample_rate,
        self.output_frame_samples,
        len(self._output_buffer),
      )
    return emitted

  def _emit_reference_frame(self, frame: bytes) -> int:
    """Emit one complete reference frame to the configured callback."""
    self._frames_emitted += 1
    if self.on_reference_frame is not None:
      self.on_reference_frame(
        frame,
        self.output_sample_rate,
        DEFAULT_REFERENCE_CHANNELS,
        DEFAULT_REFERENCE_SAMPLE_WIDTH,
      )
    return 1
