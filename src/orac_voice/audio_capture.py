"""Local microphone capture abstraction for Orac voice input.

# Author: Clive Bostock
# Date: 2026-05-04
# Description: Provides fixed-duration local microphone recording for Orac.
"""

from __future__ import annotations

from pathlib import Path
import threading
import uuid
import wave
from typing import Protocol

from loguru import logger

from lib.config_mgr import ConfigManager
from orac_voice.tts_piper import expand_config_path, resolve_orac_home


DEFAULT_RECORD_SECONDS = 5.0
DEFAULT_SAMPLE_RATE = 16000


class AudioCapture(Protocol):
  """Interface for capturing speech audio."""

  def record_to_wav(
    self,
    *,
    session_id: str,
    turn_id: str,
    record_seconds: float | None = None,
  ) -> Path:
    """Record audio to a WAV file.

    Args:
      session_id (str): Voice session identifier.
      turn_id (str): Voice turn identifier.
      record_seconds (float | None): Optional duration override.

    Returns:
      Path: Captured WAV path.
    """

  def cancel(self) -> None:
    """Cancel active recording if possible."""


def _safe_identifier(value: str) -> str:
  """Return a compact filesystem-safe identifier."""
  cleaned = "".join(ch if ch.isalnum() or ch in "_.-" else "_" for ch in value)
  return cleaned[:80] or "unknown"


def _normalise_input_device(value: str) -> int | str | None:
  """Normalise configured sounddevice input device value."""
  cleaned = value.strip()
  if not cleaned or cleaned.lower() == "default":
    return None
  if cleaned.isdigit():
    return int(cleaned)
  return cleaned


class SoundDeviceAudioCapture:
  """Capture fixed-duration mono WAV audio from a local microphone."""

  def __init__(
    self,
    *,
    config_file_path: Path | None = None,
    output_dir: Path | str | None = None,
    sample_rate: int | None = None,
    input_device: str | None = None,
    record_seconds: float | None = None,
  ) -> None:
    """Initialise local microphone capture.

    Args:
      config_file_path (Path | None): Optional Orac config path.
      output_dir (Path | str | None): Optional capture output directory.
      sample_rate (int | None): Optional sample rate override.
      input_device (str | None): Optional sounddevice input device.
      record_seconds (float | None): Optional default duration.
    """
    self.orac_home = resolve_orac_home()
    config_path = config_file_path or (
      self.orac_home / "resources" / "config" / "orac.ini"
    )
    self.config_mgr = ConfigManager(config_file_path=config_path)
    self.sample_rate = int(
      sample_rate
      or self.config_mgr.int_config_value(
        "voice",
        "stt_sample_rate",
        default=DEFAULT_SAMPLE_RATE,
      )
    )
    self.record_seconds = float(
      record_seconds
      if record_seconds is not None
      else self.config_mgr.float_config_value(
        "voice",
        "stt_record_seconds",
        default=DEFAULT_RECORD_SECONDS,
      )
    )
    configured_device = input_device
    if configured_device is None:
      configured_device = self.config_mgr.config_value(
        "voice",
        "stt_input_device",
        default="default",
      )
    self.input_device = _normalise_input_device(configured_device)

    if output_dir is None:
      self.output_dir = self.orac_home / "var" / "tmp" / "orac_voice"
    else:
      self.output_dir = expand_config_path(str(output_dir), orac_home=self.orac_home)
    self.output_dir.mkdir(parents=True, exist_ok=True)
    self._cancel_requested = False
    self._recording_active = False

  @classmethod
  def from_config(
    cls,
    *,
    config_file_path: Path | None = None,
    record_seconds: float | None = None,
  ) -> "SoundDeviceAudioCapture":
    """Create a capture wrapper from Orac configuration."""
    return cls(config_file_path=config_file_path, record_seconds=record_seconds)

  def _output_path(self, *, session_id: str, turn_id: str) -> Path:
    """Build a unique capture WAV output path."""
    name = (
      f"capture-{_safe_identifier(session_id)}-"
      f"{_safe_identifier(turn_id)}-{uuid.uuid4().hex[:12]}.wav"
    )
    return self.output_dir / name

  def record_to_wav(
    self,
    *,
    session_id: str,
    turn_id: str,
    record_seconds: float | None = None,
  ) -> Path:
    """Record fixed-duration mono microphone input to a WAV file.

    Args:
      session_id (str): Voice session identifier.
      turn_id (str): Voice turn identifier.
      record_seconds (float | None): Optional duration override.

    Returns:
      Path: Captured WAV path.

    Raises:
      RuntimeError: If the microphone cannot be opened or recording fails.
    """
    try:
      import numpy as np
      import sounddevice as sd
    except ImportError as exc:
      raise RuntimeError(
        "sounddevice and numpy are required for local speech input"
      ) from exc

    duration = float(record_seconds or self.record_seconds)
    if duration <= 0:
      raise ValueError("record_seconds must be greater than zero")

    frames = max(1, int(self.sample_rate * duration))
    output_path = self._output_path(session_id=session_id, turn_id=turn_id)
    self._cancel_requested = False

    logger.info(
      "Recording local microphone audio: {}s at {} Hz",
      duration,
      self.sample_rate,
    )
    self._recording_active = True
    try:
      audio = self._record_with_timeout(sd=sd, frames=frames, duration=duration)
    except KeyboardInterrupt:
      self.cancel()
      raise
    except Exception as exc:
      self.cancel()
      raise RuntimeError(f"Unable to record from local microphone: {exc}") from exc
    finally:
      self._recording_active = False

    if self._cancel_requested:
      raise RuntimeError("Microphone recording cancelled")

    int_audio = np.clip(audio.reshape(-1), -1.0, 1.0)
    int_audio = (int_audio * 32767.0).astype(np.int16)
    self._write_wav(output_path=output_path, samples=int_audio)
    return output_path

  def cancel(self) -> None:
    """Cancel active recording if sounddevice is currently recording."""
    self._cancel_requested = True
    if not self._recording_active:
      return
    try:
      import sounddevice as sd
    except ImportError:
      return
    self._request_sounddevice_stop(sd)

  def _write_wav(self, *, output_path: Path, samples) -> None:
    """Write mono int16 samples to a WAV file."""
    with wave.open(str(output_path), "wb") as wav_file:
      wav_file.setnchannels(1)
      wav_file.setsampwidth(2)
      wav_file.setframerate(self.sample_rate)
      wav_file.writeframes(samples.tobytes())

  def _record_with_timeout(self, *, sd, frames: int, duration: float):
    """Record with a timeout safeguard around sounddevice calls."""
    result: list = []
    errors: list[BaseException] = []

    def _record() -> None:
      try:
        audio = sd.rec(
          frames,
          samplerate=self.sample_rate,
          channels=1,
          dtype="float32",
          device=self.input_device,
        )
        sd.wait()
        result.append(audio)
      except BaseException as exc:
        errors.append(exc)

    record_thread = threading.Thread(
      target=_record,
      name="orac-audio-capture-record",
      daemon=True,
    )
    record_thread.start()
    record_thread.join(timeout=max(3.0, duration + 3.0))
    if record_thread.is_alive():
      self._request_sounddevice_stop(sd)
      raise RuntimeError("Microphone recording timed out")
    if errors:
      raise errors[0]
    if not result:
      raise RuntimeError("Microphone recording produced no audio")
    return result[0]

  def _request_sounddevice_stop(self, sd) -> None:
    """Request sounddevice stop without risking a hung caller."""

    def _stop() -> None:
      try:
        sd.stop()
      except Exception as exc:
        logger.debug("sounddevice stop request failed: {}", exc)

    threading.Thread(
      target=_stop,
      name="orac-audio-capture-stop",
      daemon=True,
    ).start()
