"""Kokoro text-to-speech backend for Orac."""

# Author: Clive Bostock
# Date: 2026-05-17
# Description: Calls a local OpenAI-compatible Kokoro speech endpoint.

from __future__ import annotations

from pathlib import Path
import os
import re
import threading
import uuid

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
SAFE_KOKORO_TOKEN = re.compile(r"^[A-Za-z0-9_.:-]+$")
SAFE_KOKORO_VOICE = re.compile(r"^[A-Za-z0-9_.:+()-]+$")


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
      self.output_dir = expand_config_path(str(output_dir), orac_home=self.orac_home)
    self.output_dir.mkdir(parents=True, exist_ok=True)

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

    output_path.write_bytes(audio)
    return output_path

  def cancel(self) -> None:
    """Cancel future Kokoro requests by replacing the HTTP session."""
    with self._session_lock:
      old_session = self._session
      self._session = requests.Session()
    old_session.close()
