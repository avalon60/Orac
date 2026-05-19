"""Kokoro text-to-speech backend for Orac."""

# Author: Clive Bostock
# Date: 2026-05-17
# Description: Calls a local OpenAI-compatible Kokoro speech endpoint.

from __future__ import annotations

from dataclasses import dataclass
import io
from pathlib import Path
import os
import re
import shutil
import threading
import uuid
import wave

from loguru import logger
import requests

from lib.config_mgr import ConfigManager
from orac_voice.tts_piper import expand_config_path
from orac_voice.tts_piper import resolve_orac_home


VOICE_SECTION = "voice"
DEFAULT_KOKORO_BASE_URL = "http://127.0.0.1:8880/v1"
DEFAULT_KOKORO_MODEL = "kokoro"
DEFAULT_KOKORO_VOICE = "af_heart"
DEFAULT_KOKORO_RESPONSE_FORMAT = "wav"
DEFAULT_KOKORO_TIMEOUT_SECONDS = 60
DEFAULT_KOKORO_FINAL_FADE_MS = 8
STREAMED_WAV_FRAME_SENTINEL = 0x3FFFFFFF
SAFE_KOKORO_TOKEN = re.compile(r"^[A-Za-z0-9_.:-]+$")
SAFE_KOKORO_VOICE = re.compile(r"^[A-Za-z0-9_.:+()-]+$")


@dataclass(frozen=True)
class WavAudio:
  """Decoded WAV audio plus stable format metadata."""

  channels: int
  sample_width: int
  sample_rate: int
  frame_count: int
  pcm: bytes

  @property
  def duration_seconds(self) -> float:
    """Return the decoded audio duration in seconds."""
    if self.sample_rate <= 0:
      return 0.0
    return float(self.frame_count) / float(self.sample_rate)


def build_kokoro_speech_url(base_url: str) -> str:
  """Build the OpenAI-compatible Kokoro speech endpoint URL.

  Args:
    base_url (str): Configured Kokoro base URL. It may include ``/v1`` and
      may have trailing whitespace or slashes.

  Returns:
    str: Normalised speech endpoint URL.

  Raises:
    RuntimeError: If the base URL is empty.
  """
  cleaned = base_url.strip().rstrip("/")
  if not cleaned:
    raise RuntimeError("Kokoro base URL is empty")
  if cleaned.endswith("/v1"):
    return f"{cleaned}/audio/speech"
  return f"{cleaned}/v1/audio/speech"


def _safe_identifier(value: str) -> str:
  """Return a filesystem-safe short identifier."""
  cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
  return cleaned[:80] or "unknown"


def _optional_config_value(
  config_mgr: ConfigManager,
  section: str,
  key: str,
  *,
  default: str,
) -> str:
  """Read an optional string config value."""
  try:
    value = config_mgr.config_value(section, key, default=default)
  except KeyError:
    return default
  return str(value or default).strip() or default


def _optional_int_config_value(
  config_mgr: ConfigManager,
  section: str,
  key: str,
  *,
  default: int,
) -> int:
  """Read an optional integer config value."""
  try:
    return int(config_mgr.int_config_value(section, key, default=default))
  except Exception:
    logger.warning(
      "Invalid integer for {}.{}; using default {}",
      section,
      key,
      default,
    )
    return default


def _optional_bool_config_value(
  config_mgr: ConfigManager,
  section: str,
  key: str,
  *,
  default: bool,
) -> bool:
  """Read an optional boolean config value."""
  try:
    return bool(config_mgr.bool_config_value(section, key, default=default))
  except Exception:
    logger.warning(
      "Invalid boolean for {}.{}; using default {}",
      section,
      key,
      default,
    )
    return default


def _find_embedded_riff_offsets(audio: bytes) -> list[int]:
  """Return offsets of extra RIFF headers after the first byte."""
  offsets: list[int] = []
  start = 1
  while True:
    offset = audio.find(b"RIFF", start)
    if offset < 0:
      return offsets
    offsets.append(offset)
    start = offset + 4


def _read_wav_audio(audio: bytes) -> WavAudio:
  """Decode a single WAV payload into PCM frames.

  Args:
    audio (bytes): Raw WAV file bytes.

  Returns:
    WavAudio: Decoded audio and format metadata.

  Raises:
    RuntimeError: If the payload is not one complete PCM WAV file.
  """
  embedded_riffs = _find_embedded_riff_offsets(audio)
  if embedded_riffs:
    raise RuntimeError(
      "Kokoro synthesis returned WAV audio with embedded RIFF headers at "
      f"offsets {embedded_riffs}; refusing byte-concatenated audio."
    )

  try:
    with wave.open(io.BytesIO(audio), "rb") as wav_file:
      if wav_file.getcomptype() != "NONE":
        raise RuntimeError(
          f"Unsupported compressed Kokoro WAV type: {wav_file.getcomptype()}"
        )
      channels = wav_file.getnchannels()
      sample_width = wav_file.getsampwidth()
      sample_rate = wav_file.getframerate()
      frame_count = wav_file.getnframes()
      pcm = wav_file.readframes(frame_count)
  except wave.Error as exc:
    raise RuntimeError(
      f"Kokoro synthesis returned invalid WAV audio: {exc}"
    ) from exc

  if channels <= 0 or sample_width <= 0 or sample_rate <= 0:
    raise RuntimeError(
      "Kokoro synthesis returned WAV audio with invalid format metadata"
    )
  frame_size = channels * sample_width
  expected_len = frame_count * frame_size
  if len(pcm) != expected_len and frame_count >= STREAMED_WAV_FRAME_SENTINEL:
    if len(pcm) % frame_size != 0:
      raise RuntimeError(
        "Kokoro synthesis returned streamed WAV PCM with a partial frame: "
        f"{len(pcm)} bytes is not divisible by frame size {frame_size}"
      )
    logger.debug(
      (
        "Kokoro streamed WAV used unknown-length frame sentinel {}; "
        "using actual decoded frame count {}."
      ),
      frame_count,
      len(pcm) // frame_size,
    )
    frame_count = len(pcm) // frame_size
    expected_len = len(pcm)

  if len(pcm) != expected_len:
    raise RuntimeError(
      "Kokoro synthesis returned truncated WAV PCM: "
      f"expected {expected_len} bytes, got {len(pcm)}"
    )
  return WavAudio(
    channels=channels,
    sample_width=sample_width,
    sample_rate=sample_rate,
    frame_count=frame_count,
    pcm=pcm,
  )


def _sample_value(sample: bytes, *, sample_width: int) -> int:
  """Return a PCM sample value normalised around zero."""
  if sample_width == 1:
    return int(sample[0]) - 128
  return int.from_bytes(sample, byteorder="little", signed=True)


def _encode_sample(value: int, *, sample_width: int) -> bytes:
  """Encode one PCM sample value."""
  if sample_width == 1:
    return bytes([max(0, min(255, value + 128))])

  bits = sample_width * 8
  minimum = -(1 << (bits - 1))
  maximum = (1 << (bits - 1)) - 1
  clipped = max(minimum, min(maximum, int(value)))
  return clipped.to_bytes(sample_width, byteorder="little", signed=True)


def _scale_sample(sample: bytes, *, sample_width: int, scale: float) -> bytes:
  """Scale one PCM sample toward silence."""
  value = _sample_value(sample, sample_width=sample_width)
  return _encode_sample(round(value * scale), sample_width=sample_width)


def _apply_final_fade(audio: WavAudio, *, fade_ms: int) -> bytes:
  """Apply a short fade-out to the final PCM frames."""
  if fade_ms <= 0 or not audio.pcm:
    return audio.pcm

  frame_size = audio.channels * audio.sample_width
  fade_frames = min(
    audio.frame_count,
    max(1, round(audio.sample_rate * fade_ms / 1000)),
  )
  fade_start = max(0, audio.frame_count - fade_frames)
  faded = bytearray(audio.pcm)

  for frame_index in range(fade_start, audio.frame_count):
    remaining = audio.frame_count - frame_index - 1
    scale = float(remaining) / float(fade_frames)
    frame_offset = frame_index * frame_size
    for channel in range(audio.channels):
      sample_offset = frame_offset + (channel * audio.sample_width)
      sample = bytes(faded[sample_offset : sample_offset + audio.sample_width])
      faded[sample_offset : sample_offset + audio.sample_width] = _scale_sample(
        sample,
        sample_width=audio.sample_width,
        scale=scale,
      )
  return bytes(faded)


def _frame_peak(audio: WavAudio, *, frame_index: int) -> int:
  """Return the absolute peak sample value for one frame."""
  if audio.frame_count <= 0:
    return 0
  bounded_index = max(0, min(audio.frame_count - 1, frame_index))
  frame_size = audio.channels * audio.sample_width
  frame_offset = bounded_index * frame_size
  peak = 0
  for channel in range(audio.channels):
    sample_offset = frame_offset + (channel * audio.sample_width)
    sample = audio.pcm[sample_offset : sample_offset + audio.sample_width]
    peak = max(peak, abs(_sample_value(sample, sample_width=audio.sample_width)))
  return peak


def _write_wav_file(
  *,
  output_path: Path,
  audio: WavAudio,
  pcm: bytes,
) -> None:
  """Write PCM frames with a fresh single WAV header."""
  tmp_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
  with wave.open(str(tmp_path), "wb") as wav_file:
    wav_file.setnchannels(audio.channels)
    wav_file.setsampwidth(audio.sample_width)
    wav_file.setframerate(audio.sample_rate)
    wav_file.writeframes(pcm)
  tmp_path.replace(output_path)


class KokoroTtsEngine:
  """Synthesis wrapper for a local Kokoro speech HTTP service."""

  def __init__(
    self,
    *,
    config_file_path: Path | None = None,
    base_url: str = DEFAULT_KOKORO_BASE_URL,
    voice_name: str = DEFAULT_KOKORO_VOICE,
    model: str = DEFAULT_KOKORO_MODEL,
    response_format: str = DEFAULT_KOKORO_RESPONSE_FORMAT,
    output_dir: Path | str | None = None,
    timeout_seconds: int = DEFAULT_KOKORO_TIMEOUT_SECONDS,
    api_key_env: str | None = None,
    final_fade_ms: int = DEFAULT_KOKORO_FINAL_FADE_MS,
    debug_audio: bool = False,
    retain_raw_response: bool = False,
  ) -> None:
    """Initialise Kokoro synthesis.

    Args:
      config_file_path (Path | None): Optional Orac config path.
      base_url (str): OpenAI-compatible base URL, usually ending in ``/v1``.
      voice_name (str): Kokoro voice identifier.
      model (str): Kokoro model identifier.
      response_format (str): Requested audio format. Must be ``wav``.
      output_dir (Path | str | None): Optional output directory.
      timeout_seconds (int): HTTP request timeout in seconds.
      api_key_env (str | None): Optional environment variable containing a
        bearer token for protected local endpoints.
      final_fade_ms (int): Fade-out duration applied to the generated WAV.
      debug_audio (bool): Whether to retain diagnostic audio files.
      retain_raw_response (bool): Whether to retain raw Kokoro responses.

    Raises:
      RuntimeError: If configuration is invalid.
    """
    self.orac_home = resolve_orac_home()
    self.config_file_path = config_file_path
    self.base_url = base_url.rstrip("/")
    self._speech_url = build_kokoro_speech_url(base_url)
    self.voice_name = voice_name.strip()
    self.model = model.strip()
    self.response_format = response_format.strip().lower()
    self.timeout_seconds = int(timeout_seconds or DEFAULT_KOKORO_TIMEOUT_SECONDS)
    self.api_key_env = (api_key_env or "").strip()
    self.final_fade_ms = max(0, int(final_fade_ms))
    self.debug_audio = bool(debug_audio)
    self.retain_raw_response = bool(retain_raw_response)

    if not self.base_url:
      raise RuntimeError("Kokoro base URL is empty")
    if not SAFE_KOKORO_VOICE.fullmatch(self.voice_name):
      raise RuntimeError(f"Invalid Kokoro voice name: {self.voice_name!r}")
    if not SAFE_KOKORO_TOKEN.fullmatch(self.model):
      raise RuntimeError(f"Invalid Kokoro model name: {self.model!r}")
    if self.response_format != "wav":
      raise RuntimeError(
        "Kokoro backend currently requires tts_kokoro_response_format=wav"
      )

    if output_dir is None:
      self.output_dir = self.orac_home / "var" / "tmp" / "orac_voice"
    else:
      self.output_dir = expand_config_path(
        str(output_dir),
        orac_home=self.orac_home,
      )
    self.output_dir.mkdir(parents=True, exist_ok=True)
    self.debug_dir = self.output_dir / "kokoro_debug"
    if self.debug_audio or self.retain_raw_response:
      self.debug_dir.mkdir(parents=True, exist_ok=True)

    self._session_lock = threading.Lock()
    self._session = requests.Session()
    logger.debug("Kokoro speech endpoint resolved to {}", self._speech_url)

  @classmethod
  def from_config(
    cls,
    *,
    config_file_path: Path | None = None,
    voice_name: str | None = None,
  ) -> "KokoroTtsEngine":
    """Create a Kokoro engine from Orac configuration."""
    orac_home = resolve_orac_home()
    resolved_config_path = config_file_path or (
      orac_home / "resources" / "config" / "orac.ini"
    )
    config_mgr = ConfigManager(config_file_path=resolved_config_path)
    configured_voice = _optional_config_value(
      config_mgr,
      VOICE_SECTION,
      "tts_kokoro_voice",
      default=DEFAULT_KOKORO_VOICE,
    )
    return cls(
      config_file_path=resolved_config_path,
      base_url=_optional_config_value(
        config_mgr,
        VOICE_SECTION,
        "tts_kokoro_base_url",
        default=DEFAULT_KOKORO_BASE_URL,
      ),
      voice_name=voice_name or configured_voice,
      model=_optional_config_value(
        config_mgr,
        VOICE_SECTION,
        "tts_kokoro_model",
        default=DEFAULT_KOKORO_MODEL,
      ),
      response_format=_optional_config_value(
        config_mgr,
        VOICE_SECTION,
        "tts_kokoro_response_format",
        default=DEFAULT_KOKORO_RESPONSE_FORMAT,
      ),
      timeout_seconds=_optional_int_config_value(
        config_mgr,
        VOICE_SECTION,
        "tts_kokoro_timeout_seconds",
        default=DEFAULT_KOKORO_TIMEOUT_SECONDS,
      ),
      api_key_env=_optional_config_value(
        config_mgr,
        VOICE_SECTION,
        "tts_kokoro_api_key_env",
        default="",
      ),
      final_fade_ms=_optional_int_config_value(
        config_mgr,
        VOICE_SECTION,
        "tts_kokoro_final_fade_ms",
        default=DEFAULT_KOKORO_FINAL_FADE_MS,
      ),
      debug_audio=_optional_bool_config_value(
        config_mgr,
        VOICE_SECTION,
        "tts_kokoro_debug_audio",
        default=False,
      ),
      retain_raw_response=_optional_bool_config_value(
        config_mgr,
        VOICE_SECTION,
        "tts_kokoro_retain_raw_response",
        default=False,
      ),
    )

  @property
  def speech_url(self) -> str:
    """Return the OpenAI-compatible speech endpoint URL."""
    return self._speech_url

  def _output_path(self, *, session_id: str, turn_id: str) -> Path:
    """Build a unique WAV output path."""
    name = (
      f"{_safe_identifier(session_id)}-"
      f"{_safe_identifier(turn_id)}-"
      f"{uuid.uuid4().hex[:12]}-kokoro.wav"
    )
    return self.output_dir / name

  def synthesise_to_wav(
    self,
    text: str,
    *,
    session_id: str,
    turn_id: str,
  ) -> Path:
    """Synthesise text to a generated WAV file."""
    clean_text = text.strip()
    if not clean_text:
      raise ValueError("Cannot synthesise empty text")

    output_path = self._output_path(session_id=session_id, turn_id=turn_id)
    headers: dict[str, str] = {}
    if self.api_key_env:
      token = os.environ.get(self.api_key_env, "").strip()
      if token:
        headers["Authorization"] = f"Bearer {token}"

    payload = {
      "model": self.model,
      "voice": self.voice_name,
      "input": clean_text,
      "response_format": self.response_format,
    }
    logger.debug(
      "Synthesising voice chunk with Kokoro voice {} to {}",
      self.voice_name,
      output_path,
    )

    try:
      with self._session_lock:
        response = self._session.post(
          self.speech_url,
          json=payload,
          headers=headers,
          timeout=self.timeout_seconds,
        )
      response.raise_for_status()
    except requests.RequestException as exc:
      raise RuntimeError(f"Kokoro synthesis request failed: {exc}") from exc

    audio = response.content or b""
    if not audio:
      raise RuntimeError("Kokoro synthesis returned an empty audio response")
    if not audio.startswith(b"RIFF"):
      raise RuntimeError(
        "Kokoro synthesis did not return WAV audio; check "
        "tts_kokoro_response_format and the local Kokoro endpoint."
      )

    raw_path = self.debug_dir / f"{output_path.stem}-raw.wav"
    if self.retain_raw_response:
      raw_path.write_bytes(audio)

    wav_audio = _read_wav_audio(audio)
    logger.info(
      (
        "Kokoro WAV segment: path={} duration={:.3f}s sample_rate={} "
        "channels={} sample_width={} frames={} bytes={} "
        "start_peak={} end_peak={} final_fade_ms={}"
      ),
      output_path,
      wav_audio.duration_seconds,
      wav_audio.sample_rate,
      wav_audio.channels,
      wav_audio.sample_width,
      wav_audio.frame_count,
      len(wav_audio.pcm),
      _frame_peak(wav_audio, frame_index=0),
      _frame_peak(wav_audio, frame_index=wav_audio.frame_count - 1),
      self.final_fade_ms,
    )

    faded_pcm = _apply_final_fade(wav_audio, fade_ms=self.final_fade_ms)
    _write_wav_file(output_path=output_path, audio=wav_audio, pcm=faded_pcm)
    if self.debug_audio:
      shutil.copy2(output_path, self.debug_dir / f"{output_path.stem}-final.wav")

    final_riffs = _find_embedded_riff_offsets(output_path.read_bytes())
    if final_riffs:
      raise RuntimeError(
        "Final Kokoro WAV contains embedded RIFF headers at offsets "
        f"{final_riffs}"
      )
    return output_path

  def cancel(self) -> None:
    """Cancel future Kokoro requests by replacing the HTTP session."""
    with self._session_lock:
      old_session = self._session
      self._session = requests.Session()
    old_session.close()
