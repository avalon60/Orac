"""Local audio playback abstraction for Orac voice output.

# Author: Clive Bostock
# Date: 2026-05-04
# Description: Provides local WAV playback behind a replaceable interface.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import threading
from typing import Protocol

from loguru import logger


DEFAULT_PLAYBACK_TIMEOUT_SECONDS = 30


class AudioPlayback(Protocol):
  """Interface for playing generated speech audio."""

  def play_wav(self, wav_path: Path) -> None:
    """Play a WAV file.

    Args:
      wav_path (Path): Path to a WAV file.

    Raises:
      RuntimeError: If playback cannot be started or completes with an
        error.
    """

  def cancel(self) -> None:
    """Cancel active playback if possible."""


class LocalAudioPlayback:
  """Play WAV files on the local Linux desktop.

  The command selection is intentionally isolated so it can later be
  replaced with a Raspberry Pi streaming endpoint.
  """

  def __init__(
    self,
    *,
    player: str | None = None,
    timeout_seconds: int = DEFAULT_PLAYBACK_TIMEOUT_SECONDS,
  ) -> None:
    """Initialise local playback.

    Args:
      player (str | None): Optional command override.
      timeout_seconds (int): Playback timeout.
    """
    self.timeout_seconds = timeout_seconds
    self.players = [player] if player else self._detect_players()
    self.player = self.players[0]
    self._process_lock = threading.Lock()
    self._active_process: subprocess.Popen[str] | None = None

  def _detect_players(self) -> list[str]:
    """Return supported WAV players in preference order.

    Returns:
      list[str]: Player executable names.

    Raises:
      RuntimeError: If no supported player is available.
    """
    players: list[str] = []
    for candidate in ("paplay", "aplay", "ffplay"):
      if shutil.which(candidate):
        players.append(candidate)
    if not players:
      raise RuntimeError("No supported audio player found: paplay, aplay, ffplay")
    return players

  def _command_for(self, *, player: str, wav_path: Path) -> list[str]:
    """Build the playback command for the selected player.

    Args:
      player (str): Player executable.
      wav_path (Path): WAV file path.

    Returns:
      list[str]: Command arguments.
    """
    if player == "ffplay":
      return [
        player,
        "-nodisp",
        "-autoexit",
        "-loglevel",
        "error",
        str(wav_path),
      ]
    return [player, str(wav_path)]

  def play_wav(self, wav_path: Path) -> None:
    """Play a WAV file locally.

    Args:
      wav_path (Path): Path to a WAV file.

    Raises:
      FileNotFoundError: If the WAV file does not exist.
      RuntimeError: If playback fails.
    """
    if not wav_path.exists():
      raise FileNotFoundError(f"WAV file does not exist: {wav_path}")

    failures: list[str] = []
    for player in self.players:
      command = self._command_for(player=player, wav_path=wav_path)
      logger.debug("Playing generated voice WAV with {}", player)
      process: subprocess.Popen[str] | None = None
      try:
        process = subprocess.Popen(
          command,
          stdin=subprocess.DEVNULL,
          stdout=subprocess.PIPE,
          stderr=subprocess.PIPE,
          text=True,
        )
        with self._process_lock:
          self._active_process = process

        stdout, stderr = process.communicate(
          timeout=self.timeout_seconds,
        )
        if process.returncode != 0:
          raise subprocess.CalledProcessError(
            process.returncode,
            command,
            output=stdout,
            stderr=stderr,
          )
        self.player = player
        return
      except subprocess.CalledProcessError as exc:
        message = self._summarise_failure(exc.stderr or exc.stdout or "")
        failures.append(f"{player}: {message}")
      except subprocess.TimeoutExpired:
        self._terminate_process(process, reason="playback timed out")
        failures.append(f"{player}: playback timed out")
      finally:
        with self._process_lock:
          if self._active_process is process:
            self._active_process = None

    raise RuntimeError("Audio playback failed: " + " | ".join(failures))

  def cancel(self) -> None:
    """Terminate any active local playback process."""
    with self._process_lock:
      process = self._active_process
    self._terminate_process(process, reason="cancellation requested")

  def _terminate_process(
    self,
    process: subprocess.Popen[str] | None,
    *,
    reason: str,
  ) -> None:
    """Terminate a playback process if it is still running."""
    if process is None or process.poll() is not None:
      return
    logger.info("Terminating audio playback process: {}", reason)
    process.terminate()
    try:
      process.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
      logger.warning("Killing unresponsive audio playback process")
      process.kill()
      process.wait(timeout=1.0)

  @staticmethod
  def _summarise_failure(output: str, *, limit: int = 600) -> str:
    """Return a bounded single-line playback failure summary."""
    cleaned = " ".join((output or "").strip().split())
    if not cleaned:
      return "command failed"
    if len(cleaned) <= limit:
      return cleaned
    return cleaned[:limit].rstrip() + "..."
