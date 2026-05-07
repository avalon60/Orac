"""Local microphone capture abstraction for Orac voice input.

# Author: Clive Bostock
# Date: 2026-05-04
# Description: Provides local microphone recording for Orac.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
import queue
import threading
import uuid
import wave
from typing import Callable, Protocol

from loguru import logger

from lib.config_mgr import ConfigManager
from orac_voice.tts_piper import expand_config_path, resolve_orac_home
from orac_voice.vad_silero import (
  DEFAULT_STT_MAX_RECORD_SECONDS,
  DEFAULT_STT_MIN_RECORD_SECONDS,
  DEFAULT_VAD_CHUNK_MS,
  DEFAULT_VAD_END_THRESHOLD,
  DEFAULT_VAD_INITIAL_TIMEOUT_SECONDS,
  DEFAULT_VAD_MIN_SILENCE_MS,
  DEFAULT_VAD_MIN_SPEECH_MS,
  DEFAULT_VAD_PRE_SPEECH_PADDING_MS,
  DEFAULT_VAD_SAMPLE_RATE,
  DEFAULT_VAD_START_THRESHOLD,
  VadEndpointConfig,
  create_vad_engine,
)


DEFAULT_RECORD_SECONDS = 5.0
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_RECORD_MODE = "fixed"
DEFAULT_VAD_ENGINE = "energy"


@dataclass(frozen=True)
class VadCaptureResult:
  """Result metadata for a VAD-controlled recording.

  Args:
    wav_path (Path | None): Captured WAV path, if audio was captured.
    duration_seconds (float): Captured utterance duration.
    no_speech_timeout (bool): True when no speech started before timeout.
    max_duration_reached (bool): True when the safety limit stopped capture.
  """

  wav_path: Path | None
  duration_seconds: float = 0.0
  no_speech_timeout: bool = False
  max_duration_reached: bool = False


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
  """Capture mono WAV audio from a local microphone."""

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
    self.vad_config = VadEndpointConfig(
      sample_rate=int(
        self.config_mgr.int_config_value(
          "voice",
          "vad_sample_rate",
          default=self.sample_rate or DEFAULT_VAD_SAMPLE_RATE,
        )
      ),
      chunk_ms=int(
        self.config_mgr.int_config_value(
          "voice",
          "vad_chunk_ms",
          default=DEFAULT_VAD_CHUNK_MS,
        )
      ),
      speech_start_threshold=float(
        self.config_mgr.float_config_value(
          "voice",
          "vad_speech_start_threshold",
          default=DEFAULT_VAD_START_THRESHOLD,
        )
      ),
      speech_end_threshold=float(
        self.config_mgr.float_config_value(
          "voice",
          "vad_speech_end_threshold",
          default=DEFAULT_VAD_END_THRESHOLD,
        )
      ),
      min_speech_ms=int(
        self.config_mgr.int_config_value(
          "voice",
          "vad_min_speech_ms",
          default=DEFAULT_VAD_MIN_SPEECH_MS,
        )
      ),
      min_silence_ms=int(
        self.config_mgr.int_config_value(
          "voice",
          "vad_min_silence_ms",
          default=DEFAULT_VAD_MIN_SILENCE_MS,
        )
      ),
      pre_speech_padding_ms=int(
        self.config_mgr.int_config_value(
          "voice",
          "vad_pre_speech_padding_ms",
          default=DEFAULT_VAD_PRE_SPEECH_PADDING_MS,
        )
      ),
      initial_timeout_seconds=float(
        self.config_mgr.float_config_value(
          "voice",
          "vad_initial_timeout_seconds",
          default=DEFAULT_VAD_INITIAL_TIMEOUT_SECONDS,
        )
      ),
      max_record_seconds=float(
        self.config_mgr.float_config_value(
          "voice",
          "stt_max_record_seconds",
          default=DEFAULT_STT_MAX_RECORD_SECONDS,
        )
      ),
      min_record_seconds=float(
        self.config_mgr.float_config_value(
          "voice",
          "stt_min_record_seconds",
          default=DEFAULT_STT_MIN_RECORD_SECONDS,
        )
      ),
    )
    self.vad_engine_name = self.config_mgr.config_value(
      "voice",
      "vad_engine",
      default=DEFAULT_VAD_ENGINE,
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

  def record_until_silence_to_wav(
    self,
    *,
    session_id: str,
    turn_id: str,
    status_callback: Callable[[str], None] | None = None,
  ) -> VadCaptureResult:
    """Record one utterance using VAD endpoint detection.

    Args:
      session_id (str): Voice session identifier.
      turn_id (str): Voice turn identifier.
      status_callback (Callable[[str], None] | None): Optional callback for
        status labels such as ``listening`` and ``speech_started``.

    Returns:
      VadCaptureResult: Captured WAV path and endpoint metadata.

    Raises:
      RuntimeError: If the microphone or VAD layer fails.
    """
    try:
      import numpy as np
      import sounddevice as sd
    except ImportError as exc:
      raise RuntimeError(
        "sounddevice and numpy are required for VAD speech input"
      ) from exc

    if self.sample_rate != self.vad_config.sample_rate:
      raise RuntimeError(
        "stt_sample_rate and vad_sample_rate must match for local VAD capture"
      )

    from orac_voice.vad_silero import VadEndpointDetector

    detector = VadEndpointDetector(config=self.vad_config)
    vad_engine = create_vad_engine(
      engine_name=self.vad_engine_name,
      sample_rate=self.vad_config.sample_rate,
    )
    output_path = self._output_path(session_id=session_id, turn_id=turn_id)
    pre_speech = deque(maxlen=self.vad_config.pre_speech_chunks)
    captured_chunks: list = []
    audio_queue: queue.Queue = queue.Queue()
    self._cancel_requested = False

    def _callback(indata, frames, time_info, status) -> None:
      del frames, time_info
      if status:
        logger.debug("sounddevice VAD capture status: {}", status)
      audio_queue.put(indata.copy())

    def _status(label: str) -> None:
      if status_callback is not None:
        status_callback(label)

    logger.info(
      "Recording local microphone audio with {} VAD at {} Hz",
      self.vad_engine_name,
      self.sample_rate,
    )
    _status("listening")
    self._recording_active = True
    no_speech_timeout = False
    max_duration_reached = False
    try:
      with sd.InputStream(
        samplerate=self.sample_rate,
        channels=1,
        dtype="float32",
        blocksize=self.vad_config.chunk_frames,
        device=self.input_device,
        callback=_callback,
      ):
        while not self._cancel_requested:
          try:
            chunk = audio_queue.get(timeout=self.vad_config.chunk_seconds * 4.0)
          except queue.Empty as exc:
            raise RuntimeError("Timed out waiting for microphone audio") from exc

          samples = np.asarray(chunk, dtype=np.float32).reshape(-1)
          probability = vad_engine.speech_probability(samples)
          result = detector.process_probability(probability)

          if not detector.speech_started:
            pre_speech.append(samples.copy())
          else:
            if result.speech_started:
              captured_chunks.extend(pre_speech)
              pre_speech.clear()
              _status("speech_started")
            captured_chunks.append(samples.copy())

          if result.no_speech_timeout:
            no_speech_timeout = True
            _status("no_speech_timeout")
            break
          if result.speech_ended:
            _status("speech_ended")
            break
          if result.max_duration_reached:
            max_duration_reached = True
            _status("max_duration_reached")
            break
    except KeyboardInterrupt:
      self.cancel()
      raise
    except Exception as exc:
      self.cancel()
      raise RuntimeError(f"Unable to record VAD microphone audio: {exc}") from exc
    finally:
      self._recording_active = False

    if self._cancel_requested:
      raise RuntimeError("Microphone recording cancelled")
    if no_speech_timeout or not captured_chunks:
      return VadCaptureResult(
        wav_path=None,
        no_speech_timeout=no_speech_timeout,
        max_duration_reached=max_duration_reached,
      )

    audio = np.concatenate(captured_chunks)
    duration_seconds = float(audio.size) / float(self.sample_rate)
    if duration_seconds < self.vad_config.min_record_seconds:
      return VadCaptureResult(wav_path=None, duration_seconds=duration_seconds)

    int_audio = np.clip(audio, -1.0, 1.0)
    int_audio = (int_audio * 32767.0).astype(np.int16)
    self._write_wav(output_path=output_path, samples=int_audio)
    return VadCaptureResult(
      wav_path=output_path,
      duration_seconds=duration_seconds,
      no_speech_timeout=no_speech_timeout,
      max_duration_reached=max_duration_reached,
    )

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
