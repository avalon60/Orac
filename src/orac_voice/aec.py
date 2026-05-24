"""Acoustic echo cancellation interfaces for Orac voice."""
# Author: Clive Bostock
# Date: 2026-05-23
# Description: Defines Orac-owned AEC frame contracts and adapters.

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from loguru import logger

from lib.config_mgr import ConfigManager


AEC_SAMPLE_RATE = 16000
AEC_FRAME_DURATION_MS = 10
AEC_CHANNELS = 1
AEC_SAMPLE_WIDTH_BYTES = 2
AEC_SAMPLES_PER_FRAME = 160
AEC_BYTES_PER_FRAME = 320
DEFAULT_AEC_BACKEND = "null"
DEFAULT_AEC_STREAM_DELAY_MS = 0
LIVEKIT_AEC_BACKEND = "livekit"
SUPPORTED_AEC_BACKENDS = frozenset({DEFAULT_AEC_BACKEND, LIVEKIT_AEC_BACKEND})
_LIVEKIT_IMPORT_ERROR = (
  "LiveKit AEC backend requires the livekit Python SDK with "
  "livekit.rtc.AudioProcessingModule and livekit.rtc.AudioFrame. "
  "Install Orac with the voice-aec-livekit extra or install livekit>=1.1.8."
)

LiveKitApmFactory = Callable[[], Any]
LiveKitAudioFrameFactory = Callable[
  [bytearray, int, int, int],
  Any,
]


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


class LiveKitAcousticEchoCanceller:
  """AEC adapter backed by LiveKit's WebRTC AudioProcessingModule.

  The adapter maps Orac's fixed 10 ms mono int16 PCM frame contract onto
  LiveKit's Python-side APM API. LiveKit mutates ``AudioFrame`` instances
  in place, so capture processing returns a copy of the processed frame.
  """

  def __init__(
    self,
    *,
    stream_delay_ms: int = DEFAULT_AEC_STREAM_DELAY_MS,
    apm_factory: LiveKitApmFactory | None = None,
    audio_frame_factory: LiveKitAudioFrameFactory | None = None,
  ) -> None:
    """Initialise the LiveKit AEC adapter.

    Args:
      stream_delay_ms (int): Delay between reverse and capture streams.
      apm_factory (LiveKitApmFactory | None): Optional factory used by
        tests to supply a LiveKit-compatible APM.
      audio_frame_factory (LiveKitAudioFrameFactory | None): Optional
        factory used by tests to supply LiveKit-compatible frames.

    Raises:
      RuntimeError: If LiveKit is unavailable or lacks the required API.
      ValueError: If ``stream_delay_ms`` is negative.
    """
    if stream_delay_ms < 0:
      raise ValueError("voice.aec_stream_delay_ms must be zero or greater")

    self.stream_delay_ms = stream_delay_ms
    self._apm_factory = apm_factory or _load_livekit_apm_factory()
    self._audio_frame_factory = (
      audio_frame_factory or _load_livekit_audio_frame_factory()
    )
    self._apm = self._create_apm()

  def process_reverse_frame(self, frame: bytes) -> None:
    """Feed one playback reference frame into LiveKit APM.

    Args:
      frame (bytes): Exact 10 ms mono int16 16 kHz PCM frame.
    """
    validate_aec_frame(frame, label="AEC reverse frame")
    audio_frame = self._create_audio_frame(frame)
    self._apm.process_reverse_stream(audio_frame)

  def process_capture_frame(self, frame: bytes) -> bytes:
    """Process one microphone capture frame through LiveKit APM.

    Args:
      frame (bytes): Exact 10 ms mono int16 16 kHz PCM frame.

    Returns:
      bytes: Echo-processed capture frame in Orac's AEC format.
    """
    validate_aec_frame(frame, label="AEC capture frame")
    audio_frame = self._create_audio_frame(frame)
    self._apm.process_stream(audio_frame)
    processed = _audio_frame_bytes(audio_frame)
    validate_aec_frame(processed, label="AEC processed capture frame")
    return processed

  def reset(self) -> None:
    """Reset LiveKit APM state by recreating the underlying module."""
    self._apm = self._create_apm()

  def _create_apm(self) -> Any:
    """Create and configure a LiveKit APM instance."""
    apm = self._apm_factory()
    apm.set_stream_delay_ms(self.stream_delay_ms)
    return apm

  def _create_audio_frame(self, frame: bytes) -> Any:
    """Create one mutable LiveKit ``AudioFrame`` from Orac PCM bytes."""
    return self._audio_frame_factory(
      bytearray(frame),
      AEC_SAMPLE_RATE,
      AEC_CHANNELS,
      AEC_SAMPLES_PER_FRAME,
    )


def _load_livekit_apm_factory() -> LiveKitApmFactory:
  """Load LiveKit's APM constructor if the required API is present.

  Returns:
    LiveKitApmFactory: Factory creating an echo-cancelling APM.

  Raises:
    RuntimeError: If the LiveKit package or required API is unavailable.
  """
  try:
    from livekit.rtc import AudioProcessingModule
  except (ImportError, AttributeError) as exc:
    raise RuntimeError(_LIVEKIT_IMPORT_ERROR) from exc

  def _factory() -> Any:
    return AudioProcessingModule(echo_cancellation=True)

  return _factory


def _load_livekit_audio_frame_factory() -> LiveKitAudioFrameFactory:
  """Load LiveKit's ``AudioFrame`` constructor.

  Returns:
    LiveKitAudioFrameFactory: Factory creating LiveKit audio frames.

  Raises:
    RuntimeError: If the LiveKit package or required API is unavailable.
  """
  try:
    from livekit.rtc import AudioFrame
  except (ImportError, AttributeError) as exc:
    raise RuntimeError(_LIVEKIT_IMPORT_ERROR) from exc
  return AudioFrame


def _audio_frame_bytes(audio_frame: Any) -> bytes:
  """Extract raw int16 bytes from a LiveKit-compatible audio frame.

  Args:
    audio_frame (Any): LiveKit ``AudioFrame`` or test double.

  Returns:
    bytes: Raw PCM bytes.

  Raises:
    RuntimeError: If the frame does not expose readable audio bytes.
  """
  data = getattr(audio_frame, "data", None)
  if data is not None:
    try:
      return memoryview(data).cast("B").tobytes()
    except TypeError:
      return bytes(data)

  raw_data = getattr(audio_frame, "_data", None)
  if raw_data is not None:
    return bytes(raw_data)

  raise RuntimeError("LiveKit AudioFrame did not expose processed audio data")


def create_aec_backend(
  *,
  backend_name: str = DEFAULT_AEC_BACKEND,
  stream_delay_ms: int = DEFAULT_AEC_STREAM_DELAY_MS,
) -> AcousticEchoCanceller:
  """Create an Orac AEC backend by name.

  Args:
    backend_name (str): Configured backend name.
    stream_delay_ms (int): Delay between playback reference and capture.

  Returns:
    AcousticEchoCanceller: Configured AEC adapter.

  Raises:
    ValueError: If the backend name is unsupported.
  """
  cleaned = backend_name.strip().lower()
  if cleaned == DEFAULT_AEC_BACKEND:
    return NullAcousticEchoCanceller()
  if cleaned == LIVEKIT_AEC_BACKEND:
    return LiveKitAcousticEchoCanceller(stream_delay_ms=stream_delay_ms)
  raise ValueError(
    "Unsupported voice.aec_backend: "
    f"{backend_name}. Supported values: "
    f"{', '.join(sorted(SUPPORTED_AEC_BACKENDS))}"
  )


def create_aec_adapter_from_config(
  config_mgr: ConfigManager,
) -> AcousticEchoCanceller:
  """Create the configured backend-neutral AEC adapter.

  Args:
    config_mgr (ConfigManager): Orac configuration manager.

  Returns:
    AcousticEchoCanceller: Configured AEC adapter.

  Raises:
    ValueError: If the backend config is unsupported.
  """
  backend_name = config_mgr.config_value(
    "voice",
    "aec_backend",
    default=DEFAULT_AEC_BACKEND,
  ).strip().lower()
  stream_delay_ms = config_mgr.int_config_value(
    "voice",
    "aec_stream_delay_ms",
    default=DEFAULT_AEC_STREAM_DELAY_MS,
  )
  backend = create_aec_backend(
    backend_name=backend_name,
    stream_delay_ms=stream_delay_ms,
  )
  logger.info(
    "AEC backend selected: {} stream_delay_ms={}",
    backend_name,
    stream_delay_ms,
  )
  return backend
