"""Piper text-to-speech wrapper for Orac.

# Author: Clive Bostock
# Date: 2026-05-04
# Description: Provides replaceable Piper TTS synthesis for local voice.
"""

from __future__ import annotations

from pathlib import Path
import os
import re
import shutil
import subprocess
import threading
import uuid
from typing import Protocol

from loguru import logger

from lib.config_mgr import ConfigManager
from lib.fsutils import project_home


VOICE_SECTION = "voice"
DEFAULT_SYNTHESIS_TIMEOUT_SECONDS = 120
DEFAULT_PIPER_VOICE_DIR = "var/models/piper"
PACKAGED_PIPER_VOICE_DIR = "resources/models/piper"
LEGACY_PIPER_VOICE_DIR = "var/voices/piper"
SAFE_VOICE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


class TtsEngine(Protocol):
  """Interface for text-to-speech engines."""

  def synthesise_to_wav(
    self,
    text: str,
    *,
    session_id: str,
    turn_id: str,
    tts_options: dict[str, object] | None = None,
  ) -> Path:
    """Synthesise text to a WAV file.

    Args:
      text (str): Text to synthesise.
      session_id (str): Session identifier.
      turn_id (str): Turn identifier.

    Returns:
      Path: Generated WAV path.
    """

  def cancel(self) -> None:
    """Cancel active synthesis if possible."""


def resolve_orac_home() -> Path:
  """Resolve the Orac runtime/project home.

  Returns:
    Path: Orac home directory.

  Raises:
    RuntimeError: If no usable Orac home can be resolved.
  """
  configured = os.environ.get("ORAC_HOME")
  if configured:
    return Path(os.path.expandvars(os.path.expanduser(configured))).resolve()

  try:
    return project_home().resolve()
  except Exception as exc:
    raise RuntimeError(
      "ORAC_HOME is not set and Orac project_home() could not be resolved"
    ) from exc


def expand_config_path(raw_path: str, *, orac_home: Path) -> Path:
  """Expand a configured path containing environment or home markers.

  Args:
    raw_path (str): Raw configured path.
    orac_home (Path): Resolved Orac home used for ${ORAC_HOME}.

  Returns:
    Path: Expanded path.
  """
  expanded = raw_path.replace("${ORAC_HOME}", str(orac_home))
  expanded = os.path.expandvars(os.path.expanduser(expanded))
  return Path(expanded).resolve()


def _safe_identifier(value: str) -> str:
  """Return a filesystem-safe short identifier.

  Args:
    value (str): Candidate identifier.

  Returns:
    str: Sanitised identifier.
  """
  cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
  return cleaned[:80] or "unknown"


class PiperTtsEngine:
  """Synthesis wrapper for Piper CLI.

  The wrapper keeps Piper-specific details behind a small interface so a
  different engine can be introduced without changing the worker.
  """

  def __init__(
    self,
    *,
    config_file_path: Path | None = None,
    voice_name: str | None = None,
    voice_dir: Path | str | None = None,
    voice_model_path: Path | str | None = None,
    output_dir: Path | str | None = None,
    piper_bin: Path | str | None = None,
    timeout_seconds: int = DEFAULT_SYNTHESIS_TIMEOUT_SECONDS,
  ) -> None:
    """Initialise Piper synthesis.

    Args:
      config_file_path (Path | None): Optional Orac config path.
      voice_name (str | None): Optional voice override.
      voice_dir (Path | str | None): Optional voice directory override.
      voice_model_path (Path | str | None): Optional direct model path.
      output_dir (Path | str | None): Optional WAV output directory.
      piper_bin (Path | str | None): Optional Piper executable path.
      timeout_seconds (int): Synthesis timeout.

    Raises:
      RuntimeError: If voice configuration is invalid.
    """
    self.orac_home = resolve_orac_home()
    resolved_config_path = config_file_path or (
      self.orac_home / "resources" / "config" / "orac.ini"
    )
    self.config_mgr = ConfigManager(config_file_path=resolved_config_path)
    self.timeout_seconds = timeout_seconds

    self.voice_name = voice_name or self.config_mgr.config_value(
      VOICE_SECTION,
      "tts_voice",
    )
    if not SAFE_VOICE_NAME.fullmatch(self.voice_name):
      raise RuntimeError(f"Invalid Piper voice name: {self.voice_name!r}")

    if voice_dir is None:
      raw_voice_dir = self.config_mgr.config_value(VOICE_SECTION, "tts_voice_dir")
      self.voice_dir = expand_config_path(raw_voice_dir, orac_home=self.orac_home)
      default_voice_dir = self.orac_home / DEFAULT_PIPER_VOICE_DIR
      self._legacy_voice_dirs = (
        [
          self.orac_home / PACKAGED_PIPER_VOICE_DIR,
          self.orac_home / LEGACY_PIPER_VOICE_DIR,
        ]
        if self.voice_dir == default_voice_dir
        else []
      )
    else:
      self.voice_dir = expand_config_path(str(voice_dir), orac_home=self.orac_home)
      self._legacy_voice_dirs = []

    if output_dir is None:
      self.output_dir = self.orac_home / "var" / "tmp" / "orac_voice"
    else:
      self.output_dir = expand_config_path(str(output_dir), orac_home=self.orac_home)
    self.output_dir.mkdir(parents=True, exist_ok=True)

    if voice_model_path is None:
      self.voice_model_path = self._resolve_voice_model_path()
    else:
      self.voice_model_path = expand_config_path(
        str(voice_model_path),
        orac_home=self.orac_home,
      )
      if not self.voice_model_path.exists():
        raise RuntimeError(
          f"Piper voice model was not found: {self.voice_model_path}"
        )
    self.piper_bin = self._resolve_piper_bin(piper_bin=piper_bin)
    self._process_lock = threading.Lock()
    self._active_process: subprocess.Popen[str] | None = None

  @classmethod
  def from_config(
    cls,
    *,
    config_file_path: Path | None = None,
    voice_name: str | None = None,
    voice_dir: Path | str | None = None,
    voice_model_path: Path | str | None = None,
  ) -> "PiperTtsEngine":
    """Create a Piper engine from Orac configuration.

    Args:
      config_file_path (Path | None): Optional config path.
      voice_name (str | None): Optional voice override.
      voice_dir (Path | str | None): Optional voice directory override.
      voice_model_path (Path | str | None): Optional direct model path.

    Returns:
      PiperTtsEngine: Configured engine.
    """
    return cls(
      config_file_path=config_file_path,
      voice_name=voice_name,
      voice_dir=voice_dir,
      voice_model_path=voice_model_path,
    )

  def _resolve_piper_bin(self, *, piper_bin: Path | str | None) -> Path:
    """Resolve the Piper executable path.

    Args:
      piper_bin (Path | str | None): Optional executable override.

    Returns:
      Path: Piper executable path.

    Raises:
      RuntimeError: If Piper cannot be found.
    """
    candidates: list[Path] = []
    if piper_bin is not None:
      candidates.append(Path(piper_bin))

    env_bin = os.environ.get("ORAC_PIPER_BIN")
    if env_bin:
      candidates.append(Path(env_bin))

    path_bin = shutil.which("piper")
    if path_bin:
      candidates.append(Path(path_bin))

    candidates.extend(
      [
        self.orac_home / ".venv" / "bin" / "piper",
        self.orac_home / ".venv-voice" / "bin" / "piper",
        self.orac_home / "src" / "view" / ".venv-voice" / "bin" / "piper",
      ]
    )

    for candidate in candidates:
      expanded = expand_config_path(str(candidate), orac_home=self.orac_home)
      if expanded.exists() and os.access(expanded, os.X_OK):
        return expanded

    raise RuntimeError(
      "Piper executable not found. Put piper on PATH or set ORAC_PIPER_BIN."
    )

  def _resolve_voice_model_path(self) -> Path:
    """Resolve the configured Piper voice model.

    Returns:
      Path: Voice model ``.onnx`` path.

    Raises:
      RuntimeError: If the voice model is not available.
    """
    searched_dirs: list[Path] = []
    candidate_dirs = [self.voice_dir, *self._legacy_voice_dirs]

    for voice_dir in candidate_dirs:
      if voice_dir in searched_dirs:
        continue
      searched_dirs.append(voice_dir)

      if not voice_dir.exists():
        continue

      direct = voice_dir / f"{self.voice_name}.onnx"
      if direct.exists():
        if voice_dir != self.voice_dir:
          logger.warning(
            "Piper voice {} resolved from fallback directory {}.",
            self.voice_name,
            voice_dir,
          )
        return direct

      matches = list(voice_dir.rglob(f"{self.voice_name}.onnx"))
      if matches:
        if voice_dir != self.voice_dir:
          logger.warning(
            "Piper voice {} resolved from fallback directory {}.",
            self.voice_name,
            voice_dir,
          )
        return matches[0]

    searched_text = ", ".join(str(path) for path in searched_dirs)

    raise RuntimeError(
      f"Piper voice '{self.voice_name}' was not found under {searched_text}"
    )

  def _output_path(self, *, session_id: str, turn_id: str) -> Path:
    """Build a unique WAV output path.

    Args:
      session_id (str): Session identifier.
      turn_id (str): Turn identifier.

    Returns:
      Path: Output WAV path.
    """
    name = (
      f"{_safe_identifier(session_id)}-"
      f"{_safe_identifier(turn_id)}-"
      f"{uuid.uuid4().hex[:12]}.wav"
    )
    return self.output_dir / name

  def synthesise_to_wav(
    self,
    text: str,
    *,
    session_id: str,
    turn_id: str,
    tts_options: dict[str, object] | None = None,
  ) -> Path:
    """Synthesise text to a generated WAV file.

    Args:
      text (str): Text to synthesise.
      session_id (str): Session identifier.
      turn_id (str): Turn identifier.

    Returns:
      Path: Generated WAV path.

    Raises:
      ValueError: If text is empty.
      RuntimeError: If Piper fails.
    """
    if tts_options:
      unsupported = sorted(
        key for key in tts_options
        if key in {"tts_rate", "tts_pitch"}
      )
      if unsupported:
        logger.debug(
          "Piper TTS ignores unsupported per-turn option(s): {}",
          ", ".join(unsupported),
        )

    clean_text = text.strip()
    if not clean_text:
      raise ValueError("Cannot synthesise empty text")

    output_path = self._output_path(session_id=session_id, turn_id=turn_id)
    command = [
      str(self.piper_bin),
      "--model",
      str(self.voice_model_path),
      "--output_file",
      str(output_path),
    ]

    logger.debug(
      "Synthesising voice chunk with Piper voice {} to {}",
      self.voice_name,
      output_path,
    )
    process: subprocess.Popen[str] | None = None
    try:
      process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
      )
      with self._process_lock:
        self._active_process = process
      stdout, stderr = process.communicate(
        input=clean_text,
        timeout=self.timeout_seconds,
      )
      if process.returncode != 0:
        raise subprocess.CalledProcessError(
          process.returncode,
          command,
          output=stdout,
          stderr=stderr,
        )
    except subprocess.CalledProcessError as exc:
      message = (exc.stderr or exc.stdout or "").strip()
      raise RuntimeError(f"Piper synthesis failed: {message}") from exc
    except subprocess.TimeoutExpired as exc:
      self._terminate_process(process, reason="synthesis timed out")
      raise RuntimeError("Piper synthesis timed out") from exc
    finally:
      with self._process_lock:
        if self._active_process is process:
          self._active_process = None

    if not output_path.exists():
      raise RuntimeError(f"Piper did not create WAV output: {output_path}")
    return output_path

  def cancel(self) -> None:
    """Terminate active Piper synthesis."""
    with self._process_lock:
      process = self._active_process
    self._terminate_process(process, reason="cancellation requested")

  def _terminate_process(
    self,
    process: subprocess.Popen[str] | None,
    *,
    reason: str,
  ) -> None:
    """Terminate a Piper process if it is still running."""
    if process is None or process.poll() is not None:
      return
    logger.info("Terminating Piper synthesis process: {}", reason)
    process.terminate()
    try:
      process.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
      logger.warning("Killing unresponsive Piper synthesis process")
      process.kill()
      process.wait(timeout=1.0)
