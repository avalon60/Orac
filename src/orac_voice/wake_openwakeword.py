"""openWakeWord wake-word activation for Orac."""
# Author: Clive Bostock
# Date: 2026-05-07
# Description: Provides openWakeWord wake-word activation for Orac.

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import time
from typing import Callable, Protocol

from loguru import logger
import numpy as np

from orac_voice.activation import VoiceActivationError
from orac_voice.activation import VoiceActivationResult
from orac_voice.audio_capture import _normalise_input_device
from orac_voice.tts_piper import expand_config_path, resolve_orac_home


DEFAULT_OPENWAKEWORD_MODEL_NAMES = ("hey_jarvis",)
DEFAULT_OPENWAKEWORD_THRESHOLD = 0.75
DEFAULT_OPENWAKEWORD_FRAME_MS = 80
DEFAULT_OPENWAKEWORD_REFRACTORY_SECONDS = 2.0
DEFAULT_OPENWAKEWORD_SAMPLE_RATE = 16000
SUPPORTED_OPENWAKEWORD_FRAMEWORKS = {"auto", "tflite", "onnx"}


class OpenWakeWordModel(Protocol):
  """Minimal prediction API used by the openWakeWord listener."""

  def predict(self, audio: np.ndarray) -> dict[str, float]:
    """Predict wake-word scores for one audio frame.

    Args:
      audio (np.ndarray): Mono 16-bit 16 kHz PCM audio frame.

    Returns:
      dict[str, float]: Scores keyed by wake-word model or class label.
    """


class OpenWakeWordAudioSource(Protocol):
  """Minimal streaming microphone API used by the listener."""

  def start(self) -> None:
    """Start audio capture."""

  def read_frame(self) -> np.ndarray:
    """Read one mono int16 PCM frame."""

  def close(self) -> None:
    """Release audio capture resources."""


class SoundDeviceOpenWakeWordAudioSource:
  """Stream openWakeWord-ready PCM frames from ``sounddevice``."""

  def __init__(
    self,
    *,
    sample_rate: int = DEFAULT_OPENWAKEWORD_SAMPLE_RATE,
    frame_ms: int = DEFAULT_OPENWAKEWORD_FRAME_MS,
    input_device: str | None = None,
  ) -> None:
    """Create a sounddevice audio source.

    Args:
      sample_rate (int): Input sample rate. openWakeWord expects 16 kHz.
      frame_ms (int): Frame duration in milliseconds.
      input_device (str | None): Optional sounddevice input device value.
    """
    self.sample_rate = sample_rate
    self.frame_ms = frame_ms
    self.input_device = _normalise_input_device(input_device or "default")
    self.frame_samples = int(sample_rate * frame_ms / 1000)
    self._stream = None

  def start(self) -> None:
    """Open and start the microphone stream."""
    if self._stream is not None:
      return
    try:
      import sounddevice as sd
    except ImportError as exc:
      raise VoiceActivationError(
        "wake_engine=openwakeword requires the sounddevice package for "
        "microphone streaming."
      ) from exc

    try:
      self._stream = sd.InputStream(
        samplerate=self.sample_rate,
        blocksize=self.frame_samples,
        channels=1,
        dtype="int16",
        device=self.input_device,
      )
      self._stream.start()
    except Exception as exc:
      raise VoiceActivationError(
        f"Unable to open microphone for openWakeWord wake detection: {exc}"
      ) from exc

  def read_frame(self) -> np.ndarray:
    """Read one frame as a flattened int16 array."""
    if self._stream is None:
      raise VoiceActivationError(
        "openWakeWord microphone stream was read before it was started."
      )
    try:
      audio, overflowed = self._stream.read(self.frame_samples)
    except Exception as exc:
      raise VoiceActivationError(
        f"Unable to read microphone audio for openWakeWord: {exc}"
      ) from exc
    if overflowed:
      logger.debug("openWakeWord microphone input overflowed")
    return np.asarray(audio, dtype=np.int16).reshape(-1)

  def close(self) -> None:
    """Close the microphone stream."""
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


class OpenWakeWordActivationListener:
  """Wake-word listener backed by openWakeWord."""

  def __init__(
    self,
    *,
    model_paths: list[Path] | None = None,
    model_names: list[str] | None = None,
    threshold: float = DEFAULT_OPENWAKEWORD_THRESHOLD,
    inference_framework: str = "auto",
    audio_source: OpenWakeWordAudioSource | None = None,
    model_factory: Callable[[], OpenWakeWordModel] | None = None,
    status_callback: Callable[[str], None] | None = None,
    input_device: str | None = None,
    frame_ms: int = DEFAULT_OPENWAKEWORD_FRAME_MS,
    refractory_seconds: float = DEFAULT_OPENWAKEWORD_REFRACTORY_SECONDS,
  ) -> None:
    """Create an openWakeWord activation listener.

    Args:
      model_paths (list[Path] | None): User-supplied model files.
      model_names (list[str] | None): Built-in pre-trained model names.
      threshold (float): Score threshold for activation.
      inference_framework (str): ``auto``, ``tflite``, or ``onnx``.
      audio_source (OpenWakeWordAudioSource | None): Test audio source.
      model_factory (Callable[[], OpenWakeWordModel] | None): Test factory.
      status_callback (Callable[[str], None] | None): Optional console
        status callback.
      input_device (str | None): Optional sounddevice input device.
      frame_ms (int): Microphone frame duration in milliseconds.
      refractory_seconds (float): Seconds to ignore detections after the
        listener starts. This avoids immediate re-triggering on Orac output.
    """
    self.model_paths = model_paths or []
    self.model_names = model_names or []
    self.threshold = float(threshold)
    self.inference_framework = _normalise_inference_framework(
      inference_framework
    )
    self.audio_source = audio_source or SoundDeviceOpenWakeWordAudioSource(
      input_device=input_device,
      frame_ms=frame_ms,
    )
    self.refractory_seconds = max(0.0, float(refractory_seconds))
    self.model_factory = model_factory
    self.status_callback = status_callback or _default_status_callback
    self._model: OpenWakeWordModel | None = None
    self._closed = False

  @classmethod
  def from_config(
    cls,
    *,
    model_paths: str = "",
    model_names: str = ",".join(DEFAULT_OPENWAKEWORD_MODEL_NAMES),
    threshold: float = DEFAULT_OPENWAKEWORD_THRESHOLD,
    inference_framework: str = "auto",
    status_callback: Callable[[str], None] | None = None,
    input_device: str | None = None,
    frame_ms: int = DEFAULT_OPENWAKEWORD_FRAME_MS,
    refractory_seconds: float = DEFAULT_OPENWAKEWORD_REFRACTORY_SECONDS,
  ) -> "OpenWakeWordActivationListener":
    """Build a listener from raw config values."""
    resolved_paths = _parse_model_paths(model_paths)
    parsed_names = _parse_model_names(model_names)
    return cls(
      model_paths=resolved_paths,
      model_names=parsed_names,
      threshold=threshold,
      inference_framework=inference_framework,
      status_callback=status_callback,
      input_device=input_device,
      frame_ms=frame_ms,
      refractory_seconds=refractory_seconds,
    )

  def wait_for_activation(self, *, session_id: str) -> VoiceActivationResult:
    """Listen continuously until openWakeWord detects a wake word."""
    del session_id
    if self._closed:
      return VoiceActivationResult(
        activated=False,
        exit_requested=True,
        reason="openWakeWord listener closed",
        wake_engine="openwakeword",
        backend="openwakeword",
      )

    model = self._get_model()
    self.status_callback("Listening for wake word: openWakeWord")
    try:
      self.audio_source.start()
      started_at = time.monotonic()
      while not self._closed:
        frame = self.audio_source.read_frame()
        predictions = model.predict(frame)
        fired_model, score = _best_detection(predictions, self.threshold)
        if fired_model is not None:
          elapsed = time.monotonic() - started_at
          if elapsed < self.refractory_seconds:
            logger.debug(
              "Ignoring openWakeWord detection during {:.2f}s re-arm guard: "
              "{} score {:.3f}",
              self.refractory_seconds,
              fired_model,
              score,
            )
            continue
          logger.info(
            "openWakeWord detected {} with score {:.3f}",
            fired_model,
            score,
          )
          self.status_callback("Wake word detected.")
          return VoiceActivationResult(
            activated=True,
            reason="openWakeWord wake word detected",
            wake_engine="openwakeword",
            backend="openwakeword",
            wake_phrase=fired_model,
            wake_word=fired_model,
            model=fired_model,
            score=score,
            timestamp=datetime.now(UTC).isoformat(),
          )
    except KeyboardInterrupt:
      self.close()
      raise
    except VoiceActivationError:
      raise
    except Exception as exc:
      raise VoiceActivationError(
        f"openWakeWord wake-word listener failed: {exc}"
      ) from exc
    finally:
      self.audio_source.close()

    return VoiceActivationResult(
      activated=False,
      exit_requested=True,
      reason="openWakeWord listener stopped",
      wake_engine="openwakeword",
      backend="openwakeword",
    )

  def close(self) -> None:
    """Release openWakeWord microphone resources."""
    self._closed = True
    self.audio_source.close()

  def _get_model(self) -> OpenWakeWordModel:
    """Create or return the cached openWakeWord model."""
    if self._model is not None:
      return self._model
    if self.model_factory is not None:
      self._model = self.model_factory()
      return self._model
    self._model = create_openwakeword_model(
      model_paths=self.model_paths,
      model_names=self.model_names,
      inference_framework=self.inference_framework,
      error_context="wake_engine=openwakeword",
    )
    return self._model


def create_openwakeword_model(
  *,
  model_paths: list[Path],
  model_names: list[str],
  inference_framework: str,
  error_context: str = "openWakeWord",
) -> OpenWakeWordModel:
  """Create an openWakeWord model from explicit paths or built-in names.

  Args:
    model_paths (list[Path]): User-supplied model files.
    model_names (list[str]): Built-in openWakeWord model names.
    inference_framework (str): ``tflite`` or ``onnx``.
    error_context (str): Prefix used in dependency and model errors.

  Returns:
    OpenWakeWordModel: Initialised openWakeWord model.

  Raises:
    VoiceActivationError: If dependencies or configured models are not usable.
  """
  if not model_paths and not model_names:
    raise VoiceActivationError(
      f"{error_context} requires openwakeword_model_paths or "
      "openwakeword_model_names. Configure a pre-trained model such as "
      "hey_jarvis or a custom .tflite/.onnx model path."
    )

  try:
    import openwakeword
    from openwakeword.model import Model
    from openwakeword.utils import download_models
  except ImportError as exc:
    raise VoiceActivationError(
      f"{error_context} requires the openwakeword package. Install the "
      "openWakeWord voice dependencies, then retry."
    ) from exc

  wakeword_models = [str(path) for path in model_paths]
  if model_names:
    logger.info(
      "Ensuring openWakeWord pre-trained model(s) are available: {}",
      ", ".join(model_names),
    )
    try:
      download_models(model_names=model_names)
    except Exception as exc:
      raise VoiceActivationError(
        "Unable to prepare openWakeWord pre-trained model(s). Check "
        "network access or configure openwakeword_model_paths with local "
        f"model files. Details: {exc}"
      ) from exc
    wakeword_models.extend(model_names)

  try:
    return Model(
      wakeword_models=wakeword_models,
      inference_framework=inference_framework,
    )
  except Exception as exc:
    available = ", ".join(sorted(getattr(openwakeword, "MODELS", {}).keys()))
    suffix = f" Available built-in models: {available}." if available else ""
    raise VoiceActivationError(
      "Unable to initialise openWakeWord wake-word engine. Check model "
      f"names, model paths, and inference framework.{suffix}"
    ) from exc


def _normalise_inference_framework(value: str) -> str:
  """Normalise the configured openWakeWord inference framework."""
  cleaned = value.strip().lower() or "auto"
  if cleaned not in SUPPORTED_OPENWAKEWORD_FRAMEWORKS:
    raise VoiceActivationError(
      "openwakeword_inference_framework must be auto, tflite, or onnx."
    )
  if cleaned == "auto":
    return "tflite"
  return cleaned


def _parse_model_names(value: str) -> list[str]:
  """Parse comma-separated openWakeWord built-in model names."""
  return [name.strip() for name in value.split(",") if name.strip()]


def _parse_model_paths(value: str) -> list[Path]:
  """Parse and validate comma-separated openWakeWord model paths."""
  paths: list[Path] = []
  orac_home = resolve_orac_home()
  for raw_path in value.split(","):
    cleaned = raw_path.strip()
    if not cleaned:
      continue
    path = expand_config_path(cleaned, orac_home=orac_home)
    if not path.exists():
      raise VoiceActivationError(
        f"openWakeWord model file does not exist: {path}"
      )
    paths.append(path)
  return paths


def _best_detection(
  predictions: dict[str, float],
  threshold: float,
) -> tuple[str | None, float | None]:
  """Return the highest scoring wake word above threshold."""
  if not predictions:
    return None, None
  model_name, score = max(predictions.items(), key=lambda item: float(item[1]))
  score = float(score)
  if score >= threshold:
    return model_name, score
  return None, None


def _default_status_callback(message: str) -> None:
  """Print one wake-word status line."""
  print(message, flush=True)
