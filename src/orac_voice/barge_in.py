"""Barge-in monitoring for local Orac voice sessions."""
# Author: Clive Bostock
# Date: 2026-05-07
# Description: Provides configurable user-speech interruption detection.

from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Callable, Protocol

from loguru import logger

from lib.config_mgr import ConfigManager
from orac_voice.audio_capture import _normalise_input_device
from orac_voice.tts_piper import resolve_orac_home
from orac_voice.vad_silero import (
  DEFAULT_VAD_CHUNK_MS,
  DEFAULT_VAD_SAMPLE_RATE,
  DEFAULT_VAD_START_THRESHOLD,
  VadEngine,
  create_vad_engine,
)
from orac_voice.wake_openwakeword import (
  DEFAULT_OPENWAKEWORD_FRAME_MS,
  DEFAULT_OPENWAKEWORD_MODEL_NAMES,
  DEFAULT_OPENWAKEWORD_THRESHOLD,
  OpenWakeWordAudioSource,
  OpenWakeWordModel,
  SoundDeviceOpenWakeWordAudioSource,
  _best_detection,
  _normalise_inference_framework,
  _parse_model_names,
  _parse_model_paths,
  create_openwakeword_model,
)


DEFAULT_BARGE_IN_ENABLED = False
DEFAULT_BARGE_IN_MODE = "openwakeword"
DEFAULT_BARGE_IN_ACKNOWLEDGE_SELF_TRIGGER_RISK = False
DEFAULT_BARGE_IN_MIN_SPEECH_MS = 250
DEFAULT_BARGE_IN_GRACE_MS = 500
DEFAULT_BARGE_IN_COOLDOWN_MS = 1000
DEFAULT_BARGE_IN_RETURN_MODE = "command_capture"
DEFAULT_BARGE_IN_IGNORE_DURING_TTS_START_MS = 300
DEFAULT_BARGE_IN_POST_RESPONSE_MS = 12000
DEFAULT_BARGE_IN_POST_RESPONSE_CANCEL_ENABLED = False
SUPPORTED_BARGE_IN_MODES = {"openwakeword", "wake_word", "vad"}
SUPPORTED_BARGE_IN_RETURN_MODES = {"command_capture", "wake_listening"}
VAD_BARGE_IN_REFUSAL_MESSAGE = (
  "VAD barge-in is disabled because speaker playback can self-trigger "
  "without echo cancellation. Set "
  "barge_in_acknowledge_self_trigger_risk=true to enable experimental "
  "mode."
)
VAD_BARGE_IN_EXPERIMENTAL_WARNING = (
  "Experimental VAD barge-in is enabled; speaker playback may self-trigger "
  "without echo cancellation."
)


@dataclass(frozen=True)
class BargeInConfig:
  """Configuration for barge-in detection."""

  enabled: bool = DEFAULT_BARGE_IN_ENABLED
  mode: str = DEFAULT_BARGE_IN_MODE
  min_speech_ms: int = DEFAULT_BARGE_IN_MIN_SPEECH_MS
  grace_ms: int = DEFAULT_BARGE_IN_GRACE_MS
  cooldown_ms: int = DEFAULT_BARGE_IN_COOLDOWN_MS
  return_mode: str = DEFAULT_BARGE_IN_RETURN_MODE
  barge_in_acknowledge_self_trigger_risk: bool = (
    DEFAULT_BARGE_IN_ACKNOWLEDGE_SELF_TRIGGER_RISK
  )
  ignore_during_tts_start_ms: int = DEFAULT_BARGE_IN_IGNORE_DURING_TTS_START_MS
  post_response_ms: int = DEFAULT_BARGE_IN_POST_RESPONSE_MS
  post_response_cancel_enabled: bool = DEFAULT_BARGE_IN_POST_RESPONSE_CANCEL_ENABLED
  sample_rate: int = DEFAULT_VAD_SAMPLE_RATE
  chunk_ms: int = DEFAULT_VAD_CHUNK_MS
  speech_start_threshold: float = DEFAULT_VAD_START_THRESHOLD
  vad_engine_name: str = "energy"
  input_device: str | None = None
  openwakeword_model_paths: str = ""
  openwakeword_model_names: str = ",".join(DEFAULT_OPENWAKEWORD_MODEL_NAMES)
  openwakeword_threshold: float = DEFAULT_OPENWAKEWORD_THRESHOLD
  openwakeword_inference_framework: str = "auto"
  openwakeword_frame_ms: int = DEFAULT_OPENWAKEWORD_FRAME_MS

  @property
  def chunk_frames(self) -> int:
    """Return microphone frames per barge-in VAD chunk."""
    return max(1, int(self.sample_rate * (self.chunk_ms / 1000.0)))


@dataclass(frozen=True)
class BargeInResult:
  """Result emitted when user speech interrupts local voice output."""

  reason: str = "user speech detected"
  speech_ms: int = 0
  return_mode: str = DEFAULT_BARGE_IN_RETURN_MODE


class BargeInAudioSource(Protocol):
  """Minimal microphone source used by the barge-in monitor."""

  def start(self) -> None:
    """Start microphone capture."""

  def read_chunk(self):
    """Read one mono floating-point audio chunk."""

  def close(self) -> None:
    """Release microphone resources."""


class SoundDeviceBargeInAudioSource:
  """Read microphone chunks for VAD-based interruption detection."""

  def __init__(
    self,
    *,
    sample_rate: int,
    chunk_frames: int,
    input_device: str | None,
  ) -> None:
    """Initialise the sounddevice audio source."""
    self.sample_rate = sample_rate
    self.chunk_frames = chunk_frames
    self.input_device = _normalise_input_device(input_device or "default")
    self._stream = None

  def start(self) -> None:
    """Open and start the input stream."""
    if self._stream is not None:
      return
    try:
      import sounddevice as sd
    except ImportError as exc:
      raise RuntimeError(
        "sounddevice is required for VAD barge-in monitoring"
      ) from exc

    self._stream = sd.InputStream(
      samplerate=self.sample_rate,
      blocksize=self.chunk_frames,
      channels=1,
      dtype="float32",
      device=self.input_device,
    )
    self._stream.start()

  def read_chunk(self):
    """Read one flattened microphone chunk."""
    if self._stream is None:
      raise RuntimeError("barge-in microphone stream was read before start")
    import numpy as np

    audio, overflowed = self._stream.read(self.chunk_frames)
    if overflowed:
      logger.debug("Barge-in microphone input overflowed")
    return np.asarray(audio, dtype=np.float32).reshape(-1)

  def close(self) -> None:
    """Close the input stream."""
    if self._stream is None:
      return
    try:
      self._stream.stop()
    except Exception:
      pass
    try:
      self._stream.close()
    finally:
      self._stream = None


class BargeInController:
  """Monitor microphone VAD and signal when the user interrupts speech."""

  def __init__(
    self,
    *,
    config: BargeInConfig,
    audio_source: BargeInAudioSource | None = None,
    vad_engine: VadEngine | None = None,
  ) -> None:
    """Initialise the controller."""
    self.config = config
    self.audio_source = audio_source or SoundDeviceBargeInAudioSource(
      sample_rate=config.sample_rate,
      chunk_frames=config.chunk_frames,
      input_device=config.input_device,
    )
    self.vad_engine = vad_engine or create_vad_engine(
      engine_name=config.vad_engine_name,
      sample_rate=config.sample_rate,
    )
    self._stop_requested = threading.Event()
    self._interrupted = threading.Event()
    self._thread: threading.Thread | None = None
    self._started_at = 0.0
    self._speech_ms = 0
    self._last_interrupt_at = 0.0
    self._callback: Callable[[BargeInResult], None] | None = None

  @classmethod
  def from_config(
    cls,
    *,
    config_file_path=None,
  ) -> "BargeInController":
    """Create a controller from ``resources/config/orac.ini``."""
    config_path = config_file_path or (
      resolve_orac_home() / "resources" / "config" / "orac.ini"
    )
    config_mgr = ConfigManager(config_file_path=config_path)
    config = load_barge_in_config(config_mgr)
    return cls(config=config)

  @property
  def interrupted(self) -> bool:
    """Return whether this controller has detected interruption."""
    return self._interrupted.is_set()

  def start(
    self,
    *,
    on_interrupt: Callable[[BargeInResult], None] | None = None,
  ) -> None:
    """Start background barge-in monitoring."""
    if not self.config.enabled:
      logger.debug("Barge-in disabled; not starting monitor")
      return
    if self.config.mode != "vad":
      raise RuntimeError(f"Unsupported barge-in mode: {self.config.mode}")
    if not self.config.barge_in_acknowledge_self_trigger_risk:
      logger.warning(VAD_BARGE_IN_REFUSAL_MESSAGE)
      return
    if self._thread is not None and self._thread.is_alive():
      return

    self._callback = on_interrupt
    self._stop_requested.clear()
    self._interrupted.clear()
    self._speech_ms = 0
    self._started_at = time.monotonic()
    self._thread = threading.Thread(
      target=self._run,
      name="orac-barge-in-monitor",
      daemon=True,
    )
    self._thread.start()

  def stop(self, *, timeout: float | None = 1.0) -> None:
    """Stop monitoring and release audio resources."""
    self._stop_requested.set()
    if self._thread is not None:
      self._thread.join(timeout=timeout)
      if self._thread.is_alive():
        logger.debug("Barge-in monitor did not stop before timeout; closing stream")
      else:
        self._thread = None
        return
    try:
      self.audio_source.close()
    except Exception as exc:
      logger.debug("Barge-in audio source close failed: {}", exc)
    self._thread = None

  def reset_for_speech(self, *, now: float | None = None) -> None:
    """Reset timing state for a newly speaking Orac response."""
    self._started_at = now if now is not None else time.monotonic()
    self._speech_ms = 0
    self._interrupted.clear()

  def clear_interruption(self) -> None:
    """Clear an ignored interruption without resetting cooldown state."""
    self._speech_ms = 0
    self._interrupted.clear()

  def process_probability(
    self,
    probability: float,
    *,
    now: float | None = None,
  ) -> BargeInResult | None:
    """Process one VAD probability and return an interrupt if triggered."""
    current = now if now is not None else time.monotonic()
    ignored_ms = max(
      int(self.config.grace_ms),
      int(self.config.ignore_during_tts_start_ms),
    )
    if (current - self._started_at) * 1000.0 < ignored_ms:
      self._speech_ms = 0
      return None
    if (
      self._last_interrupt_at
      and (current - self._last_interrupt_at) * 1000.0
      < self.config.cooldown_ms
    ):
      self._speech_ms = 0
      return None

    if probability >= self.config.speech_start_threshold:
      self._speech_ms += self.config.chunk_ms
    else:
      self._speech_ms = 0

    if self._speech_ms < self.config.min_speech_ms:
      return None

    self._last_interrupt_at = current
    self._interrupted.set()
    return BargeInResult(
      speech_ms=self._speech_ms,
      return_mode=self.config.return_mode,
    )

  def _run(self) -> None:
    """Background microphone/VAD monitoring loop."""
    try:
      self.audio_source.start()
      logger.info(
        "Barge-in monitor started: mode={} min_speech_ms={} grace_ms={} "
        "cooldown_ms={} return_mode={}",
        self.config.mode,
        self.config.min_speech_ms,
        self.config.grace_ms,
        self.config.cooldown_ms,
        self.config.return_mode,
      )
      while not self._stop_requested.is_set():
        samples = self.audio_source.read_chunk()
        probability = self.vad_engine.speech_probability(samples)
        result = self.process_probability(probability)
        if result is None:
          continue
        logger.info(
          "Barge-in detected after {} ms of speech; return_mode={}",
          result.speech_ms,
          result.return_mode,
        )
        if self._callback is not None:
          self._callback(result)
        return
    except Exception as exc:
      if not self._stop_requested.is_set():
        logger.warning("Barge-in monitor stopped after error: {}", exc)
    finally:
      try:
        self.audio_source.close()
      except Exception:
        pass


class OpenWakeWordBargeInController:
  """Monitor playback for a wake-word-confirmed interruption."""

  def __init__(
    self,
    *,
    config: BargeInConfig,
    audio_source: OpenWakeWordAudioSource | None = None,
    model_factory: Callable[[], OpenWakeWordModel] | None = None,
  ) -> None:
    """Initialise the openWakeWord barge-in controller.

    Args:
      config (BargeInConfig): Barge-in configuration.
      audio_source (OpenWakeWordAudioSource | None): Optional test source.
      model_factory (Callable[[], OpenWakeWordModel] | None): Optional test
        model factory.
    """
    self.config = config
    self.audio_source = audio_source or SoundDeviceOpenWakeWordAudioSource(
      input_device=config.input_device,
      frame_ms=config.openwakeword_frame_ms,
    )
    self.model_factory = model_factory
    self._model: OpenWakeWordModel | None = None
    self._stop_requested = threading.Event()
    self._interrupted = threading.Event()
    self._thread: threading.Thread | None = None
    self._started_at = 0.0
    self._last_interrupt_at = 0.0
    self._callback: Callable[[BargeInResult], None] | None = None

  @property
  def interrupted(self) -> bool:
    """Return whether this controller has detected interruption."""
    return self._interrupted.is_set()

  def start(
    self,
    *,
    on_interrupt: Callable[[BargeInResult], None] | None = None,
  ) -> None:
    """Start wake-word-confirmed barge-in monitoring."""
    if not self.config.enabled:
      logger.debug("Barge-in disabled; not starting monitor")
      return
    if self.config.mode != "openwakeword":
      raise RuntimeError(f"Unsupported openWakeWord barge-in mode: {self.config.mode}")
    if self._thread is not None and self._thread.is_alive():
      return

    self._callback = on_interrupt
    self._stop_requested.clear()
    self._interrupted.clear()
    self._started_at = time.monotonic()
    self._thread = threading.Thread(
      target=self._run,
      name="orac-openwakeword-barge-in-monitor",
      daemon=True,
    )
    self._thread.start()

  def stop(self, *, timeout: float | None = 1.0) -> None:
    """Stop monitoring and release audio resources."""
    self._stop_requested.set()
    if self._thread is not None:
      self._thread.join(timeout=timeout)
      if self._thread.is_alive():
        logger.debug(
          "openWakeWord barge-in monitor did not stop before timeout; "
          "closing stream"
        )
      else:
        self._thread = None
        return
    try:
      self.audio_source.close()
    except Exception as exc:
      logger.debug("openWakeWord barge-in audio source close failed: {}", exc)
    self._thread = None

  def reset_for_speech(self, *, now: float | None = None) -> None:
    """Reset timing state for a newly speaking Orac response."""
    self._started_at = now if now is not None else time.monotonic()
    self._interrupted.clear()

  def clear_interruption(self) -> None:
    """Clear an ignored interruption without resetting cooldown state."""
    self._interrupted.clear()

  def process_predictions(
    self,
    predictions: dict[str, float],
    *,
    now: float | None = None,
  ) -> BargeInResult | None:
    """Process one openWakeWord prediction frame.

    Args:
      predictions (dict[str, float]): Scores keyed by model name.
      now (float | None): Optional monotonic timestamp for tests.

    Returns:
      BargeInResult | None: Interruption result when wake word fired.
    """
    current = now if now is not None else time.monotonic()
    ignored_ms = max(
      int(self.config.grace_ms),
      int(self.config.ignore_during_tts_start_ms),
    )
    if (current - self._started_at) * 1000.0 < ignored_ms:
      return None
    if (
      self._last_interrupt_at
      and (current - self._last_interrupt_at) * 1000.0
      < self.config.cooldown_ms
    ):
      return None

    model_name, score = _best_detection(
      predictions,
      self.config.openwakeword_threshold,
    )
    if model_name is None or score is None:
      return None

    self._last_interrupt_at = current
    self._interrupted.set()
    return BargeInResult(
      reason=f"wake word {model_name} detected during playback",
      speech_ms=0,
      return_mode=self.config.return_mode,
    )

  def _get_model(self) -> OpenWakeWordModel:
    """Create or return the cached openWakeWord model."""
    if self._model is not None:
      return self._model
    if self.model_factory is not None:
      self._model = self.model_factory()
      return self._model

    model_paths = _parse_model_paths(self.config.openwakeword_model_paths)
    model_names = _parse_model_names(self.config.openwakeword_model_names)
    inference_framework = _normalise_inference_framework(
      self.config.openwakeword_inference_framework
    )
    self._model = create_openwakeword_model(
      model_paths=model_paths,
      model_names=model_names,
      inference_framework=inference_framework,
      error_context="barge_in_mode=openwakeword",
    )
    return self._model

  def _run(self) -> None:
    """Background microphone/openWakeWord monitoring loop."""
    try:
      model = self._get_model()
      self.audio_source.start()
      logger.info(
        "Barge-in monitor started: mode={} threshold={} grace_ms={} "
        "cooldown_ms={} return_mode={}",
        self.config.mode,
        self.config.openwakeword_threshold,
        self.config.grace_ms,
        self.config.cooldown_ms,
        self.config.return_mode,
      )
      while not self._stop_requested.is_set():
        frame = self.audio_source.read_frame()
        result = self.process_predictions(model.predict(frame))
        if result is None:
          continue
        logger.info("openWakeWord barge-in detected: {}", result.reason)
        if self._callback is not None:
          self._callback(result)
        return
    except Exception as exc:
      if not self._stop_requested.is_set():
        logger.warning("openWakeWord barge-in monitor stopped after error: {}", exc)
    finally:
      try:
        self.audio_source.close()
      except Exception:
        pass


def load_barge_in_config(config_mgr: ConfigManager) -> BargeInConfig:
  """Load and validate barge-in configuration from ``[voice]``."""
  mode = config_mgr.config_value(
    "voice",
    "barge_in_mode",
    default=DEFAULT_BARGE_IN_MODE,
  ).strip().lower()
  if mode == "wake_word":
    mode = "openwakeword"
  if mode not in SUPPORTED_BARGE_IN_MODES:
    raise ValueError(f"Unsupported voice.barge_in_mode: {mode}")

  return_mode = config_mgr.config_value(
    "voice",
    "barge_in_return_mode",
    default=DEFAULT_BARGE_IN_RETURN_MODE,
  ).strip().lower()
  if return_mode not in SUPPORTED_BARGE_IN_RETURN_MODES:
    raise ValueError(f"Unsupported voice.barge_in_return_mode: {return_mode}")

  return BargeInConfig(
    enabled=config_mgr.bool_config_value(
      "voice",
      "barge_in_enabled",
      default=DEFAULT_BARGE_IN_ENABLED,
    ),
    mode=mode,
    barge_in_acknowledge_self_trigger_risk=config_mgr.bool_config_value(
      "voice",
      "barge_in_acknowledge_self_trigger_risk",
      default=DEFAULT_BARGE_IN_ACKNOWLEDGE_SELF_TRIGGER_RISK,
    ),
    min_speech_ms=config_mgr.int_config_value(
      "voice",
      "barge_in_min_speech_ms",
      default=DEFAULT_BARGE_IN_MIN_SPEECH_MS,
    ),
    grace_ms=config_mgr.int_config_value(
      "voice",
      "barge_in_grace_ms",
      default=DEFAULT_BARGE_IN_GRACE_MS,
    ),
    cooldown_ms=config_mgr.int_config_value(
      "voice",
      "barge_in_cooldown_ms",
      default=DEFAULT_BARGE_IN_COOLDOWN_MS,
    ),
    return_mode=return_mode,
    ignore_during_tts_start_ms=config_mgr.int_config_value(
      "voice",
      "barge_in_ignore_during_tts_start_ms",
      default=DEFAULT_BARGE_IN_IGNORE_DURING_TTS_START_MS,
    ),
    post_response_ms=config_mgr.int_config_value(
      "voice",
      "barge_in_post_response_ms",
      default=DEFAULT_BARGE_IN_POST_RESPONSE_MS,
    ),
    post_response_cancel_enabled=config_mgr.bool_config_value(
      "voice",
      "barge_in_post_response_cancel_enabled",
      default=DEFAULT_BARGE_IN_POST_RESPONSE_CANCEL_ENABLED,
    ),
    sample_rate=config_mgr.int_config_value(
      "voice",
      "vad_sample_rate",
      default=DEFAULT_VAD_SAMPLE_RATE,
    ),
    chunk_ms=config_mgr.int_config_value(
      "voice",
      "vad_chunk_ms",
      default=DEFAULT_VAD_CHUNK_MS,
    ),
    speech_start_threshold=config_mgr.float_config_value(
      "voice",
      "vad_speech_start_threshold",
      default=DEFAULT_VAD_START_THRESHOLD,
    ),
    vad_engine_name=config_mgr.config_value(
      "voice",
      "vad_engine",
      default="energy",
    ),
    input_device=config_mgr.config_value(
      "voice",
      "stt_input_device",
      default="default",
    ),
    openwakeword_model_paths=config_mgr.config_value(
      "voice",
      "openwakeword_model_paths",
      default="",
    ),
    openwakeword_model_names=config_mgr.config_value(
      "voice",
      "openwakeword_model_names",
      default=",".join(DEFAULT_OPENWAKEWORD_MODEL_NAMES),
    ),
    openwakeword_threshold=config_mgr.float_config_value(
      "voice",
      "openwakeword_threshold",
      default=DEFAULT_OPENWAKEWORD_THRESHOLD,
    ),
    openwakeword_inference_framework=config_mgr.config_value(
      "voice",
      "openwakeword_inference_framework",
      default="auto",
    ),
    openwakeword_frame_ms=config_mgr.int_config_value(
      "voice",
      "openwakeword_frame_ms",
      default=DEFAULT_OPENWAKEWORD_FRAME_MS,
    ),
  )
