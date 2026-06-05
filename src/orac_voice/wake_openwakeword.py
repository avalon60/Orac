"""openWakeWord wake-word activation for Orac."""
# Author: Clive Bostock
# Date: 2026-05-07
# Description: Provides openWakeWord wake-word activation for Orac.

from __future__ import annotations

from datetime import UTC, datetime
import os
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
DEFAULT_OPENWAKEWORD_REFRACTORY_SECONDS = 0.2
DEFAULT_OPENWAKEWORD_SAMPLE_RATE = 16000
OPENWAKEWORD_SCORE_LOG_INTERVAL_SECONDS = 5.0
OPENWAKEWORD_SCORE_LOG_MINIMUM = 0.2
SUPPORTED_OPENWAKEWORD_FRAMEWORKS = {"auto", "tflite", "onnx"}
LOCAL_OPENWAKEWORD_MODEL_SUFFIXES = (".onnx", ".tflite")
OPENWAKEWORD_EXTERNAL_DATA_ERROR_MARKERS = (
  "external data path validation failed",
  "external data path does not exist",
  "external data",
)


class ResolvedOpenWakeWordModel:
  """Resolved openWakeWord model metadata."""

  def __init__(
    self,
    *,
    token: str,
    resolution_type: str,
    resolved_path: Path,
    search_dirs: list[Path],
    sidecar_path: Path | None = None,
    sidecar_present: bool | None = None,
  ) -> None:
    """Store model resolution details for diagnostics."""
    self.token = token
    self.resolution_type = resolution_type
    self.resolved_path = resolved_path
    self.search_dirs = search_dirs
    self.sidecar_path = sidecar_path
    self.sidecar_present = sidecar_present


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
      logger.info(
        "Opening openWakeWord microphone stream at {} Hz "
        "input_device={} pulse_source={}",
        self.sample_rate,
        self.input_device if self.input_device is not None else "default",
        os.environ.get("PULSE_SOURCE") or "default",
      )
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
    model_dirs: list[Path] | None = None,
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
      model_dirs (list[Path] | None): Optional local model directories.
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
    self.model_dirs = model_dirs or []
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
    model_dirs: str = "",
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
    parsed_dirs = _parse_model_dirs(model_dirs)
    return cls(
      model_paths=resolved_paths,
      model_names=parsed_names,
      model_dirs=parsed_dirs,
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
      next_score_log_at = started_at + OPENWAKEWORD_SCORE_LOG_INTERVAL_SECONDS
      best_recent_model = ""
      best_recent_score = 0.0
      while not self._closed:
        frame = self.audio_source.read_frame()
        predictions = model.predict(frame)
        predicted_model, predicted_score = _best_prediction(predictions)
        if (
          predicted_model is not None
          and predicted_score is not None
          and predicted_score > best_recent_score
        ):
          best_recent_model = predicted_model
          best_recent_score = predicted_score
        now = time.monotonic()
        if now >= next_score_log_at:
          if best_recent_score >= OPENWAKEWORD_SCORE_LOG_MINIMUM:
            logger.debug(
              "openWakeWord best recent score {} {:.3f} threshold {:.3f}",
              best_recent_model,
              best_recent_score,
              self.threshold,
            )
          next_score_log_at = now + OPENWAKEWORD_SCORE_LOG_INTERVAL_SECONDS
          best_recent_model = ""
          best_recent_score = 0.0
        fired_model, score = _best_detection(predictions, self.threshold)
        if fired_model is not None:
          elapsed = now - started_at
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
      model_dirs=self.model_dirs,
      inference_framework=self.inference_framework,
      error_context="wake_engine=openwakeword",
    )
    return self._model


def create_openwakeword_model(
  *,
  model_paths: list[Path],
  model_names: list[str],
  model_dirs: list[Path] | None = None,
  inference_framework: str,
  error_context: str = "openWakeWord",
) -> OpenWakeWordModel:
  """Create an openWakeWord model from explicit paths or built-in names.

  Args:
    model_paths (list[Path]): User-supplied model files.
    model_names (list[str]): Built-in openWakeWord model names.
    model_dirs (list[Path] | None): Optional local model directories.
    inference_framework (str): ``auto``, ``tflite``, or ``onnx``.
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

  orac_home = resolve_orac_home()
  configured_model_dirs = list(model_dirs or [])
  search_dirs = _resolve_openwakeword_model_dirs(
    configured_model_dirs,
    orac_home=orac_home,
  )
  resolved_models: list[ResolvedOpenWakeWordModel] = []
  for path in model_paths:
    sidecar_path = _onnx_sidecar_path(path)
    if path.suffix.lower() == ".onnx" and not sidecar_path.exists():
      logger.warning(
        "openWakeWord explicit ONNX model {} is missing sidecar {}",
        path,
        sidecar_path,
      )
    resolved_models.append(
      ResolvedOpenWakeWordModel(
        token=path.name,
        resolution_type="explicit path",
        resolved_path=path,
        search_dirs=[],
        sidecar_path=sidecar_path if path.suffix.lower() == ".onnx" else None,
        sidecar_present=sidecar_path.exists()
        if path.suffix.lower() == ".onnx"
        else None,
      )
    )
    _log_openwakeword_resolution(resolved_models[-1])

  wakeword_models = [str(path) for path in model_paths]
  local_model_paths: list[Path] = list(model_paths)
  builtin_model_names: list[str] = []

  for model_name in model_names:
    if model_name in getattr(openwakeword, "MODELS", {}):
      builtin_model_names.append(model_name)
      wakeword_models.append(model_name)
      resolved_models.append(
        ResolvedOpenWakeWordModel(
          token=model_name,
          resolution_type="built-in",
          resolved_path=Path(f"built-in:{model_name}"),
          search_dirs=[],
        )
      )
      _log_openwakeword_resolution(resolved_models[-1])
      continue

    if any(sep in model_name for sep in ("/", "\\")):
      explicit_path = expand_config_path(model_name, orac_home=orac_home)
      if explicit_path.exists():
        sidecar_path = _onnx_sidecar_path(explicit_path)
        if explicit_path.suffix.lower() == ".onnx" and not sidecar_path.exists():
          logger.warning(
            "openWakeWord explicit ONNX model {} is missing sidecar {}",
            explicit_path,
            sidecar_path,
          )
        wakeword_models.append(str(explicit_path))
        local_model_paths.append(explicit_path)
        resolved_models.append(
          ResolvedOpenWakeWordModel(
            token=model_name,
            resolution_type="explicit path",
            resolved_path=explicit_path,
            search_dirs=[],
            sidecar_path=sidecar_path
            if explicit_path.suffix.lower() == ".onnx"
            else None,
            sidecar_present=sidecar_path.exists()
            if explicit_path.suffix.lower() == ".onnx"
            else None,
          )
        )
        _log_openwakeword_resolution(resolved_models[-1])
        continue

    resolved_model = _resolve_local_openwakeword_model_path(
      model_name=model_name,
      search_dirs=search_dirs,
      orac_home=orac_home,
      available_builtin_models=sorted(
        getattr(openwakeword, "MODELS", {}).keys()
      ),
      explicit_model_paths=model_paths,
    )
    wakeword_models.append(str(resolved_model.resolved_path))
    local_model_paths.append(resolved_model.resolved_path)
    resolved_models.append(resolved_model)
    _log_openwakeword_resolution(resolved_model)

  if builtin_model_names:
    logger.info(
      "Ensuring openWakeWord pre-trained model(s) are available: {}",
      ", ".join(builtin_model_names),
    )
    try:
      download_models(model_names=builtin_model_names)
    except Exception as exc:
      raise VoiceActivationError(
        "Unable to prepare openWakeWord pre-trained model(s). Check "
        "network access or configure openwakeword_model_paths with local "
        f"model files. Details: {exc}"
      ) from exc

  wakeword_models = list(dict.fromkeys(wakeword_models))
  effective_framework = _resolve_openwakeword_inference_framework(
    inference_framework=inference_framework,
    local_model_paths=local_model_paths,
  )
  logger.info(
    "openWakeWord inference framework resolved to {}",
    effective_framework,
  )

  try:
    return Model(
      wakeword_models=wakeword_models,
      inference_framework=effective_framework,
    )
  except Exception as exc:
    external_data_error = _format_openwakeword_external_data_error(
      exc,
      resolved_models=resolved_models,
      search_dirs=search_dirs,
    )
    if external_data_error is not None:
      raise VoiceActivationError(external_data_error) from exc
    available = ", ".join(sorted(getattr(openwakeword, "MODELS", {}).keys()))
    suffix = f" Available built-in models: {available}." if available else ""
    raise VoiceActivationError(
      "Unable to initialise openWakeWord wake-word engine. Check model "
      f"names, model paths, and inference framework.{suffix}"
    ) from exc


def _normalise_inference_framework(value: str) -> str:
  """Validate and normalise the configured openWakeWord framework name."""
  cleaned = value.strip().lower() or "auto"
  if cleaned not in SUPPORTED_OPENWAKEWORD_FRAMEWORKS:
    raise VoiceActivationError(
      "openwakeword_inference_framework must be auto, tflite, or onnx."
    )
  return cleaned


def _parse_model_names(value: str) -> list[str]:
  """Parse comma-separated openWakeWord built-in model names."""
  return [name.strip() for name in value.split(",") if name.strip()]


def _parse_model_dirs(value: str) -> list[Path]:
  """Parse comma-separated openWakeWord model directories."""
  dirs: list[Path] = []
  orac_home = resolve_orac_home()
  for raw_dir in value.split(","):
    cleaned = raw_dir.strip()
    if not cleaned:
      continue
    dirs.append(expand_config_path(cleaned, orac_home=orac_home))
  return dirs


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


def _resolve_openwakeword_model_dirs(
  configured_model_dirs: list[Path],
  *,
  orac_home: Path,
) -> list[Path]:
  """Return the ordered set of directories to search for local models."""
  resolved_dirs: list[Path] = []

  def add_directory(directory: Path) -> None:
    resolved = directory.resolve()
    if resolved not in resolved_dirs:
      resolved_dirs.append(resolved)

  for directory in configured_model_dirs:
    add_directory(directory)

  # Runtime model directories take precedence over packaged resources.
  add_directory(orac_home / "var" / "models" / "wakeword" / "openwakeword")
  add_directory(orac_home / "resources" / "models" / "wakeword" / "openwakeword")

  # Legacy paths retained for existing local installations.
  add_directory(orac_home / "var" / "models" / "wake")
  add_directory(orac_home / "resources" / "models" / "openwakeword")
  add_directory(orac_home / "resources" / "wakewords")
  add_directory(Path.home() / ".Orac" / "wakewords")

  return resolved_dirs


def _resolve_local_openwakeword_model_path(
  *,
  model_name: str,
  search_dirs: list[Path],
  orac_home: Path,
  available_builtin_models: list[str],
  explicit_model_paths: list[Path],
) -> ResolvedOpenWakeWordModel:
  """Resolve a bare model token to a local ONNX or TFLite file."""
  basename = Path(model_name.strip()).name
  if not basename:
    raise VoiceActivationError(
      "openWakeWord model names must not be empty."
    )

  for suffix in LOCAL_OPENWAKEWORD_MODEL_SUFFIXES:
    if basename.lower().endswith(suffix):
      basename = basename[: -len(suffix)]
      break

  suffix_candidates = list(LOCAL_OPENWAKEWORD_MODEL_SUFFIXES)
  resolved_candidates: list[Path] = []
  for search_dir in search_dirs:
    directory_candidates: list[Path] = []
    for suffix in suffix_candidates:
      candidate = (search_dir / f"{basename}{suffix}").resolve()
      if candidate.exists():
        directory_candidates.append(candidate)
    for candidate in directory_candidates:
      if candidate not in resolved_candidates:
        resolved_candidates.append(candidate)
    if resolved_candidates:
      break

  if len(resolved_candidates) == 1:
    resolved_path = resolved_candidates[0]
    sidecar_path = _onnx_sidecar_path(resolved_path)
    sidecar_present = (
      sidecar_path.exists() if resolved_path.suffix.lower() == ".onnx" else None
    )
    if resolved_path.suffix.lower() == ".onnx" and not sidecar_present:
      logger.warning(
        "openWakeWord local ONNX model {} is missing sidecar {}. "
        "Copy both files into the same directory or use a self-contained "
        "model.",
        resolved_path,
        sidecar_path,
      )
    return ResolvedOpenWakeWordModel(
      token=basename,
      resolution_type="local basename",
      resolved_path=resolved_path,
      search_dirs=search_dirs,
      sidecar_path=sidecar_path
      if resolved_path.suffix.lower() == ".onnx"
      else None,
      sidecar_present=sidecar_present,
    )

  explicit_paths_text = (
    ", ".join(str(path) for path in explicit_model_paths)
    if explicit_model_paths
    else "none"
  )
  searched_dirs_text = ", ".join(str(path) for path in search_dirs)
  suffixes_text = ", ".join(suffix_candidates)
  builtins_text = ", ".join(available_builtin_models)

  if not resolved_candidates:
    raise VoiceActivationError(
      "Unable to resolve openWakeWord model token "
      f"'{basename}'. Available built-in models: {builtins_text or 'none'}. "
      f"Explicit model paths configured: {explicit_paths_text}. "
      f"Local directories searched: {searched_dirs_text or 'none'}. "
      f"Suffixes tried: {suffixes_text}. "
      "Example fix: openwakeword_model_paths = /full/path/to/hey_orac.onnx"
    )

  raise VoiceActivationError(
    "Unable to resolve openWakeWord model token "
    f"'{basename}' because multiple local files matched: "
    f"{', '.join(str(path) for path in resolved_candidates)}. "
    "Set openwakeword_model_paths to the exact file you want."
  )


def _onnx_sidecar_path(path: Path) -> Path:
  """Return the sidecar path used by ONNX external-data models."""
  return Path(f"{path}.data")


def _format_openwakeword_external_data_error(
  exc: Exception,
  *,
  resolved_models: list[ResolvedOpenWakeWordModel],
  search_dirs: list[Path],
) -> str | None:
  """Build a clearer error message for ONNX external-data failures."""
  message = str(exc).lower()
  if not any(marker in message for marker in OPENWAKEWORD_EXTERNAL_DATA_ERROR_MARKERS):
    return None

  for resolved_model in resolved_models:
    if resolved_model.resolved_path.suffix.lower() != ".onnx":
      continue
    sidecar_path = resolved_model.sidecar_path or _onnx_sidecar_path(
      resolved_model.resolved_path
    )
    if resolved_model.sidecar_present:
      continue

    searched_dirs = ", ".join(str(path) for path in search_dirs) or "none"
    return (
      "openWakeWord resolved an external-data ONNX model but the matching "
      f"sidecar file was not found: {sidecar_path}. Copy both "
      f"{resolved_model.resolved_path.name} and "
      f"{sidecar_path.name} into the same local model directory, or use a "
      "self-contained .onnx or .tflite model. "
      f"Requested token: {resolved_model.token}. "
      f"Resolution type: {resolved_model.resolution_type}. "
      f"Resolved path: {resolved_model.resolved_path}. "
      f"Directories searched: {searched_dirs}."
    )

  return (
    "openWakeWord initialisation failed with an ONNX external-data error. "
    "If the selected model uses external tensors, copy both the .onnx file "
    "and the matching .onnx.data sidecar into the same local directory, or "
    "use a self-contained .onnx or .tflite model."
  )


def _log_openwakeword_resolution(resolved_model: ResolvedOpenWakeWordModel) -> None:
  """Log a compact, uniform openWakeWord resolution summary."""
  if resolved_model.resolution_type == "built-in":
    sidecar_text = "n/a"
  elif resolved_model.sidecar_present is True:
    sidecar_text = "found"
  elif resolved_model.sidecar_present is False:
    sidecar_text = "missing"
  else:
    sidecar_text = "n/a"

  logger.info(
    "openWakeWord model resolution: token='{}' type={} path={} sidecar={}",
    resolved_model.token,
    resolved_model.resolution_type,
    resolved_model.resolved_path,
    sidecar_text,
  )


def _resolve_openwakeword_inference_framework(
  *,
  inference_framework: str,
  local_model_paths: list[Path],
) -> str:
  """Resolve the concrete openWakeWord runtime framework for the models."""
  cleaned = _normalise_inference_framework(inference_framework)
  if not local_model_paths:
    return "tflite" if cleaned == "auto" else cleaned

  suffixes = {path.suffix.lower() for path in local_model_paths}
  if len(suffixes) != 1:
    raise VoiceActivationError(
      "Resolved openWakeWord model files use mixed formats. "
      f"Framework inference requires a single file type, but found: "
      f"{', '.join(sorted(suffixes))}. Set openwakeword_model_paths or "
      "openwakeword_model_dirs to a single .onnx or .tflite family."
    )

  suffix = next(iter(suffixes))
  if suffix == ".onnx":
    resolved_framework = "onnx"
  elif suffix == ".tflite":
    resolved_framework = "tflite"
  else:
    raise VoiceActivationError(
      "Resolved openWakeWord model files must use .onnx or .tflite."
    )

  if cleaned not in {"auto", resolved_framework}:
    raise VoiceActivationError(
      "openwakeword_inference_framework={configured} does not match the "
      "resolved local model format {resolved}. Set "
      "openwakeword_inference_framework={resolved} or use an explicit path "
      "with a matching file type.".format(
        configured=cleaned,
        resolved=resolved_framework,
      )
    )

  return resolved_framework


def _best_detection(
  predictions: dict[str, float],
  threshold: float,
) -> tuple[str | None, float | None]:
  """Return the highest scoring wake word above threshold."""
  model_name, score = _best_prediction(predictions)
  if score is not None and score >= threshold:
    return model_name, score
  return None, None


def _best_prediction(
  predictions: dict[str, float],
) -> tuple[str | None, float | None]:
  """Return the highest scoring wake word prediction."""
  if not predictions:
    return None, None
  model_name, score = max(predictions.items(), key=lambda item: float(item[1]))
  return model_name, float(score)


def _default_status_callback(message: str) -> None:
  """Print one wake-word status line."""
  print(message, flush=True)
