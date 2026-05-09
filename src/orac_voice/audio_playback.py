"""Local audio playback abstraction for Orac voice output.

# Author: Clive Bostock
# Date: 2026-05-09
# Description: Provides shell and native local WAV playback behind a replaceable interface.
"""

from __future__ import annotations

from collections.abc import Callable
import importlib
from pathlib import Path
import shutil
import subprocess
import threading
import time
import wave
from typing import Protocol

from loguru import logger


DEFAULT_PLAYBACK_TIMEOUT_SECONDS = 30
DEFAULT_NATIVE_PLAYBACK_FRAME_MS = 10
PlaybackFrameHandler = Callable[[bytes, int, int, int], None]


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


class NativeAudioPlayback:
  """Play WAV files through ``sounddevice`` while exposing PCM frames.

  The native backend is experimental and exists so future AEC wiring can
  receive the exact playback PCM frames before they are sent to the output
  device.
  """

  def __init__(
    self,
    *,
    on_playback_frame: PlaybackFrameHandler | None = None,
    frame_ms: int = DEFAULT_NATIVE_PLAYBACK_FRAME_MS,
    timeout_seconds: int = DEFAULT_PLAYBACK_TIMEOUT_SECONDS,
    device: str | int | None = None,
    sounddevice_module=None,
  ) -> None:
    """Initialise the experimental native playback backend.

    Args:
      on_playback_frame (PlaybackFrameHandler | None): Optional PCM hook.
      frame_ms (int): Target frame duration in milliseconds.
      timeout_seconds (int): Maximum playback time before cancellation.
      device (str | int | None): Optional sounddevice output device.
      sounddevice_module: Optional dependency injection hook for tests.
    """
    self.on_playback_frame = on_playback_frame
    self.frame_ms = frame_ms
    self.timeout_seconds = timeout_seconds
    self.device = device
    self._sounddevice = sounddevice_module
    self._process_lock = threading.Lock()
    self._active_stream = None
    self._cancel_requested = threading.Event()

  def set_playback_frame_handler(
    self,
    handler: PlaybackFrameHandler | None,
  ) -> None:
    """Set or clear the PCM hook used for playback frame inspection.

    Args:
      handler (PlaybackFrameHandler | None): Optional PCM hook.
    """
    self.on_playback_frame = handler

  def _load_sounddevice(self):
    """Return the ``sounddevice`` module or fail clearly.

    Returns:
      module: Imported ``sounddevice`` module.

    Raises:
      RuntimeError: If the dependency is missing.
    """
    if self._sounddevice is not None:
      return self._sounddevice
    try:
      self._sounddevice = importlib.import_module("sounddevice")
    except ImportError as exc:
      raise RuntimeError(
        "playback_backend=native requires the sounddevice package"
      ) from exc
    return self._sounddevice

  def play_wav(self, wav_path: Path) -> None:
    """Play a WAV file through the native PCM path.

    Args:
      wav_path (Path): Path to a WAV file.

    Raises:
      FileNotFoundError: If the WAV file does not exist.
      RuntimeError: If playback fails or is cancelled.
    """
    if not wav_path.exists():
      raise FileNotFoundError(f"WAV file does not exist: {wav_path}")

    sd = self._load_sounddevice()
    self._cancel_requested.clear()
    logger.debug("Playing generated voice WAV with native sounddevice backend")

    with wave.open(str(wav_path), "rb") as wav_file:
      channels = wav_file.getnchannels()
      sample_width = wav_file.getsampwidth()
      sample_rate = wav_file.getframerate()
      frame_samples = max(1, round(sample_rate * self.frame_ms / 1000))
      frame_bytes = frame_samples * channels * sample_width
      logger.info(
        (
          "Native playback backend selected: sample_rate={} channels={} "
          "sample_width={} frame_samples={} frame_bytes={} device={}"
        ),
        sample_rate,
        channels,
        sample_width,
        frame_samples,
        frame_bytes,
        self.device,
      )
      if self.on_playback_frame is not None:
        logger.debug("Native playback frame hook configured")

      stream = sd.RawOutputStream(
        samplerate=sample_rate,
        channels=channels,
        dtype=self._dtype_for_sample_width(sample_width),
        blocksize=frame_samples,
        device=self.device,
      )
      deadline = time.monotonic() + self.timeout_seconds if self.timeout_seconds else None
      with stream:
        with self._process_lock:
          self._active_stream = stream
        try:
          first_frame_logged = False
          while not self._cancel_requested.is_set():
            if deadline is not None and time.monotonic() > deadline:
              raise RuntimeError("Audio playback timed out")
            chunk = wav_file.readframes(frame_samples)
            if not chunk:
              break
            if self.on_playback_frame is not None:
              self.on_playback_frame(chunk, sample_rate, channels, sample_width)
            if not first_frame_logged:
              logger.debug(
                "Native playback frame hook invoked: sample_rate={} channels={} sample_width={} frame_bytes={}",
                sample_rate,
                channels,
                sample_width,
                len(chunk),
              )
              first_frame_logged = True
            stream.write(chunk)
          if self._cancel_requested.is_set():
            raise RuntimeError("Audio playback cancelled")
        finally:
          with self._process_lock:
            if self._active_stream is stream:
              self._active_stream = None

  def cancel(self) -> None:
    """Cancel native playback if a stream is active."""
    self._cancel_requested.set()
    with self._process_lock:
      stream = self._active_stream
    if stream is None:
      return
    logger.info("Terminating native audio playback stream: cancellation requested")
    try:
      stream.abort()
    except Exception as exc:  # pragma: no cover - defensive cleanup
      logger.debug("Native playback abort request failed: {}", exc)

  @staticmethod
  def _dtype_for_sample_width(sample_width: int) -> str:
    """Return a ``sounddevice`` dtype for one PCM sample width."""
    if sample_width == 1:
      return "uint8"
    if sample_width == 2:
      return "int16"
    if sample_width == 4:
      return "int32"
    raise RuntimeError(f"Unsupported PCM sample width for native playback: {sample_width}")
