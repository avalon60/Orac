"""Faster-Whisper speech-to-text wrapper for Orac.

# Author: Clive Bostock
# Date: 2026-05-04
# Description: Provides local faster-whisper transcription for Orac.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from loguru import logger

from lib.config_mgr import ConfigManager
from orac_voice.tts_piper import resolve_orac_home


DEFAULT_STT_MODEL = "base.en"
DEFAULT_STT_DEVICE = "cpu"
DEFAULT_STT_COMPUTE_TYPE = "int8"


class SttEngine(Protocol):
  """Interface for speech-to-text engines."""

  def transcribe_wav(self, wav_path: Path) -> str:
    """Transcribe a WAV file to text.

    Args:
      wav_path (Path): WAV file path.

    Returns:
      str: Recognised text.
    """


def _normalise_compute_type(value: str) -> str:
  """Normalise configured faster-whisper compute type."""
  cleaned = value.strip().lower()
  if not cleaned or cleaned == "auto":
    return DEFAULT_STT_COMPUTE_TYPE
  return cleaned


def _normalise_device(value: str) -> str:
  """Normalise configured faster-whisper device.

  The CTranslate2 ``auto`` device may select CUDA on systems with partial GPU
  libraries installed, which then fails at runtime if CUDA is incomplete. Orac's
  local speech input defaults to CPU for predictable Linux desktop behaviour.
  """
  cleaned = value.strip().lower()
  if not cleaned or cleaned == "auto":
    return DEFAULT_STT_DEVICE
  return cleaned


class FasterWhisperSttEngine:
  """Local STT engine backed by faster-whisper."""

  def __init__(
    self,
    *,
    config_file_path: Path | None = None,
    model_name: str | None = None,
    device: str | None = None,
    compute_type: str | None = None,
  ) -> None:
    """Initialise faster-whisper STT.

    Args:
      config_file_path (Path | None): Optional Orac config path.
      model_name (str | None): Optional model override.
      device (str | None): Optional device override.
      compute_type (str | None): Optional compute type override.
    """
    self.orac_home = resolve_orac_home()
    config_path = config_file_path or (
      self.orac_home / "resources" / "config" / "orac.ini"
    )
    self.config_mgr = ConfigManager(config_file_path=config_path)
    self.model_name = model_name or self.config_mgr.config_value(
      "voice",
      "stt_model",
      default=DEFAULT_STT_MODEL,
    )
    self.device = _normalise_device(
      device
      or self.config_mgr.config_value(
        "voice",
        "stt_device",
        default=DEFAULT_STT_DEVICE,
      )
    )
    self.compute_type = _normalise_compute_type(
      compute_type
      or self.config_mgr.config_value(
        "voice",
        "stt_compute_type",
        default=DEFAULT_STT_COMPUTE_TYPE,
      )
    )
    self._model = None

  @classmethod
  def from_config(
    cls,
    *,
    config_file_path: Path | None = None,
  ) -> "FasterWhisperSttEngine":
    """Create an STT engine from Orac configuration."""
    return cls(config_file_path=config_file_path)

  def _load_model(self):
    """Load and cache the faster-whisper model."""
    if self._model is not None:
      return self._model
    try:
      from faster_whisper import WhisperModel
    except ImportError as exc:
      raise RuntimeError(
        "faster-whisper is required for local speech recognition"
      ) from exc

    logger.info(
      "Loading faster-whisper model {} on {} ({})",
      self.model_name,
      self.device,
      self.compute_type,
    )
    self._model = WhisperModel(
      self.model_name,
      device=self.device,
      compute_type=self.compute_type,
    )
    return self._model

  def transcribe_wav(self, wav_path: Path) -> str:
    """Transcribe one WAV file with faster-whisper.

    Args:
      wav_path (Path): WAV file path.

    Returns:
      str: Recognised text.

    Raises:
      FileNotFoundError: If the WAV file does not exist.
      RuntimeError: If transcription fails.
    """
    if not wav_path.exists():
      raise FileNotFoundError(f"Audio file does not exist: {wav_path}")

    model = self._load_model()
    try:
      segments, _info = model.transcribe(
        str(wav_path),
        beam_size=5,
        vad_filter=False,
      )
      text_parts = [segment.text.strip() for segment in segments]
    except Exception as exc:
      raise RuntimeError(f"Speech transcription failed: {exc}") from exc

    return " ".join(part for part in text_parts if part).strip()
