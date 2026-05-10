"""Voice activity detection helpers for local Orac speech input."""
# Author: Clive Bostock
# Date: 2026-05-04
# Description: Provides VAD endpoint detection for local Orac voice input.

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from loguru import logger


DEFAULT_VAD_SAMPLE_RATE = 16000
DEFAULT_VAD_CHUNK_MS = 30
DEFAULT_VAD_START_THRESHOLD = 0.55
DEFAULT_VAD_END_THRESHOLD = 0.35
DEFAULT_VAD_MIN_SPEECH_MS = 250
DEFAULT_VAD_MIN_SILENCE_MS = 900
DEFAULT_VAD_PRE_SPEECH_PADDING_MS = 900
DEFAULT_VAD_INITIAL_TIMEOUT_SECONDS = 10.0
DEFAULT_STT_MAX_RECORD_SECONDS = 20.0
DEFAULT_STT_MIN_RECORD_SECONDS = 0.8


class VadEngine(Protocol):
  """Interface for converting audio chunks into speech probabilities."""

  def speech_probability(self, samples) -> float:
    """Return speech probability for one mono PCM audio chunk.

    Args:
      samples: Mono floating point samples in the range -1.0 to 1.0.

    Returns:
      float: Speech probability from 0.0 to 1.0.
    """


@dataclass(frozen=True)
class VadEndpointConfig:
  """Configuration for endpoint detection.

  Args:
    sample_rate (int): Audio sample rate in Hz.
    chunk_ms (int): VAD chunk duration in milliseconds.
    speech_start_threshold (float): Probability needed for speech start.
    speech_end_threshold (float): Probability below which silence accrues.
    min_speech_ms (int): Continuous speech needed before start fires.
    min_silence_ms (int): Silence needed before endpoint fires.
    pre_speech_padding_ms (int): Audio retained before detected speech.
    initial_timeout_seconds (float): Timeout before speech starts.
    max_record_seconds (float): Hard maximum recording duration.
    min_record_seconds (float): Minimum duration before endpoint may fire.
  """

  sample_rate: int = DEFAULT_VAD_SAMPLE_RATE
  chunk_ms: int = DEFAULT_VAD_CHUNK_MS
  speech_start_threshold: float = DEFAULT_VAD_START_THRESHOLD
  speech_end_threshold: float = DEFAULT_VAD_END_THRESHOLD
  min_speech_ms: int = DEFAULT_VAD_MIN_SPEECH_MS
  min_silence_ms: int = DEFAULT_VAD_MIN_SILENCE_MS
  pre_speech_padding_ms: int = DEFAULT_VAD_PRE_SPEECH_PADDING_MS
  initial_timeout_seconds: float = DEFAULT_VAD_INITIAL_TIMEOUT_SECONDS
  max_record_seconds: float = DEFAULT_STT_MAX_RECORD_SECONDS
  min_record_seconds: float = DEFAULT_STT_MIN_RECORD_SECONDS

  @property
  def chunk_seconds(self) -> float:
    """Return chunk duration in seconds."""
    return self.chunk_ms / 1000.0

  @property
  def chunk_frames(self) -> int:
    """Return the number of frames per VAD chunk."""
    return max(1, int(self.sample_rate * self.chunk_seconds))

  @property
  def pre_speech_chunks(self) -> int:
    """Return the number of chunks to retain before speech starts."""
    chunk_ms = max(1, self.chunk_ms)
    return max(1, int(round(self.pre_speech_padding_ms / chunk_ms)))


@dataclass(frozen=True)
class VadFrameResult:
  """Result of processing one VAD probability frame."""

  speech_started: bool = False
  speech_ended: bool = False
  no_speech_timeout: bool = False
  max_duration_reached: bool = False
  speech_active: bool = False


class VadEndpointDetector:
  """Small endpoint state machine driven by speech probabilities."""

  def __init__(self, config: VadEndpointConfig) -> None:
    """Initialise endpoint detection state.

    Args:
      config (VadEndpointConfig): Endpoint detection configuration.
    """
    self.config = config
    self.elapsed_ms = 0
    self._speech_ms = 0
    self._silence_ms = 0
    self._started = False
    self._ended = False

  @property
  def speech_started(self) -> bool:
    """Return whether speech has been confirmed."""
    return self._started

  def process_probability(self, probability: float) -> VadFrameResult:
    """Process one VAD probability and update endpoint state.

    Args:
      probability (float): Speech probability for the current chunk.

    Returns:
      VadFrameResult: State transition flags for the chunk.
    """
    if self._ended:
      return VadFrameResult(speech_ended=True, speech_active=self._started)

    self.elapsed_ms += self.config.chunk_ms
    max_ms = int(self.config.max_record_seconds * 1000.0)
    initial_timeout_ms = int(self.config.initial_timeout_seconds * 1000.0)

    if self.elapsed_ms >= max_ms:
      self._ended = True
      return VadFrameResult(
        max_duration_reached=True,
        speech_active=self._started,
      )

    if not self._started:
      if probability >= self.config.speech_start_threshold:
        self._speech_ms += self.config.chunk_ms
      else:
        self._speech_ms = 0

      if self._speech_ms >= self.config.min_speech_ms:
        self._started = True
        self._silence_ms = 0
        return VadFrameResult(speech_started=True, speech_active=True)

      if self.elapsed_ms >= initial_timeout_ms:
        self._ended = True
        return VadFrameResult(no_speech_timeout=True)

      return VadFrameResult()

    if probability <= self.config.speech_end_threshold:
      self._silence_ms += self.config.chunk_ms
    else:
      self._silence_ms = 0

    min_record_ms = int(self.config.min_record_seconds * 1000.0)
    if (
      self.elapsed_ms >= min_record_ms
      and self._silence_ms >= self.config.min_silence_ms
    ):
      self._ended = True
      return VadFrameResult(speech_ended=True, speech_active=True)

    return VadFrameResult(speech_active=True)


class EnergyVadEngine:
  """Lightweight local VAD based on microphone energy.

  This is intentionally explicit as an ``energy`` engine, not a hidden
  replacement for Silero. It keeps VAD mode usable without introducing
  Torch/CUDA dependencies into the project.
  """

  def __init__(self) -> None:
    """Initialise the energy VAD engine."""
    self._noise_floor = 0.004

  def speech_probability(self, samples) -> float:
    """Estimate speech probability from RMS energy."""
    try:
      import numpy as np
    except ImportError as exc:
      raise RuntimeError("numpy is required for energy VAD") from exc

    chunk = np.asarray(samples, dtype=np.float32).reshape(-1)
    if chunk.size == 0:
      return 0.0

    rms = float(np.sqrt(np.mean(np.square(chunk))))
    if rms < self._noise_floor * 2.0:
      self._noise_floor = (self._noise_floor * 0.98) + (rms * 0.02)

    lower = max(0.006, self._noise_floor * 2.5)
    upper = max(0.035, lower * 4.0)
    probability = (rms - lower) / (upper - lower)
    return max(0.0, min(1.0, probability))


class SileroVadEngine:
  """Silero VAD adapter hidden behind the Orac VAD interface."""

  def __init__(self, *, sample_rate: int = DEFAULT_VAD_SAMPLE_RATE) -> None:
    """Initialise Silero VAD lazily.

    Args:
      sample_rate (int): Audio sample rate expected by the VAD model.
    """
    self.sample_rate = sample_rate
    self._model = None

  def speech_probability(self, samples) -> float:
    """Return Silero speech probability for one audio chunk."""
    model = self._load_model()
    try:
      import numpy as np
      import torch
    except ImportError as exc:
      raise RuntimeError(
        "Silero VAD requires silero-vad and torch. "
        "Use vad_engine = energy to avoid the Torch dependency."
      ) from exc

    chunk = np.asarray(samples, dtype=np.float32).reshape(-1)
    tensor = torch.from_numpy(chunk)
    with torch.no_grad():
      probability = model(tensor, self.sample_rate)
    return float(probability.item())

  def _load_model(self):
    """Load and cache the Silero model."""
    if self._model is not None:
      return self._model
    try:
      from silero_vad import load_silero_vad
    except ImportError as exc:
      raise RuntimeError(
        "Silero VAD is not installed. Install silero-vad, or set "
        "voice.vad_engine = energy in orac.ini."
      ) from exc

    logger.info("Loading Silero VAD model")
    self._model = load_silero_vad()
    return self._model


def create_vad_engine(*, engine_name: str, sample_rate: int) -> VadEngine:
  """Create a configured VAD probability engine.

  Args:
    engine_name (str): Configured VAD engine name.
    sample_rate (int): Audio sample rate in Hz.

  Returns:
    VadEngine: Configured VAD engine.

  Raises:
    ValueError: If the VAD engine is unsupported.
  """
  cleaned = engine_name.strip().lower()
  if cleaned == "energy":
    return EnergyVadEngine()
  if cleaned == "silero":
    return SileroVadEngine(sample_rate=sample_rate)
  raise ValueError(f"Unsupported VAD engine: {engine_name}")
