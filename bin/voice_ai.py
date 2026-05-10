"""Convenience launcher for the local Orac voice assistant."""
# Author: Clive Bostock
# Date: 2026-05-08
# Description: Starts local Orac voice modes without manual PYTHONPATH setup.

from __future__ import annotations

import argparse
import py_compile
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_ACTIVATION_MODE = "openwakeword"
DEFAULT_RECORD_MODE = "vad"
CHECK_PATHS = (
  SRC_ROOT / "orac_voice" / "voice_loop_local.py",
  SRC_ROOT / "orac_voice" / "wake_openwakeword.py",
  SRC_ROOT / "orac_voice" / "activation.py",
)


def _ensure_src_path() -> None:
  """Add the project source tree to ``sys.path``."""
  src_path = str(SRC_ROOT)
  if src_path not in sys.path:
    sys.path.insert(0, src_path)


def build_parser() -> argparse.ArgumentParser:
  """Build the command line parser.

  Returns:
    argparse.ArgumentParser: Configured parser.
  """
  parser = argparse.ArgumentParser(
    prog="python bin/voice_ai.py",
    description=(
      "Run the local Orac voice assistant with sensible defaults. "
      "The default command starts a voice session using openWakeWord."
    ),
  )
  parser.add_argument(
    "--mode",
    choices=("session", "turn", "listen-once", "tts-test"),
    default="session",
    help="Voice mode to run. Default: %(default)s.",
  )
  parser.add_argument(
    "--activation-mode",
    choices=("openwakeword", "enter", "stt_phrase", "porcupine", "wake_word"),
    default=DEFAULT_ACTIVATION_MODE,
    help="Activation mode for session mode. Default: %(default)s.",
  )
  parser.add_argument(
    "--record-mode",
    choices=("vad", "fixed"),
    default=DEFAULT_RECORD_MODE,
    help="Speech recording mode. Default: %(default)s.",
  )
  parser.add_argument(
    "--record-seconds",
    type=float,
    help="Fixed recording duration override.",
  )
  parser.add_argument(
    "--host",
    default=DEFAULT_HOST,
    help="Orac TCP host. Default: %(default)s.",
  )
  parser.add_argument(
    "--port",
    type=int,
    default=DEFAULT_PORT,
    help="Orac TCP port. Default: %(default)s.",
  )
  parser.add_argument(
    "--tts-text",
    help="Text to speak when --mode tts-test is selected.",
  )
  parser.add_argument(
    "--voice",
    help="Override configured Piper voice name.",
  )
  parser.add_argument(
    "--voice-dir",
    help="Override configured Piper voice directory.",
  )
  parser.add_argument(
    "--wait-seconds",
    type=float,
    help="Maximum seconds to wait for queued TTS in tts-test mode.",
  )
  parser.add_argument(
    "--check",
    action="store_true",
    help="Compile-check the key local voice modules and exit.",
  )
  return parser


def _compile_check() -> int:
  """Compile-check key local voice modules.

  Returns:
    int: Process exit code.
  """
  for path in CHECK_PATHS:
    py_compile.compile(str(path), doraise=True)
    print(f"OK: {path.relative_to(PROJECT_ROOT)}")
  return 0


def _build_voice_loop_args(args: argparse.Namespace) -> list[str]:
  """Build arguments for ``orac_voice.voice_loop_local``.

  Args:
    args (argparse.Namespace): Parsed wrapper arguments.

  Returns:
    list[str]: Arguments for the underlying voice loop.
  """
  voice_args: list[str] = []
  if args.mode == "session":
    voice_args.extend(["--voice-session", "--activation-mode", args.activation_mode])
  elif args.mode == "turn":
    voice_args.append("--voice-turn")
  elif args.mode == "listen-once":
    voice_args.append("--listen-once")
  elif args.mode == "tts-test":
    if not args.tts_text:
      raise ValueError("--mode tts-test requires --tts-text")
    voice_args.extend(["--tts-test", args.tts_text])

  voice_args.extend(["--record-mode", args.record_mode])
  voice_args.extend(["--host", args.host])
  voice_args.extend(["--port", str(args.port)])

  if args.record_seconds is not None:
    voice_args.extend(["--record-seconds", str(args.record_seconds)])
  if args.voice:
    voice_args.extend(["--voice", args.voice])
  if args.voice_dir:
    voice_args.extend(["--voice-dir", args.voice_dir])
  if args.wait_seconds is not None:
    voice_args.extend(["--wait-seconds", str(args.wait_seconds)])
  return voice_args


def main() -> int:
  """Run the wrapper entrypoint.

  Returns:
    int: Process exit code.
  """
  parser = build_parser()
  args = parser.parse_args()
  _ensure_src_path()

  if args.check:
    return _compile_check()

  from orac_voice import voice_loop_local

  voice_args = _build_voice_loop_args(args)
  sys.argv = ["python -m orac_voice.voice_loop_local", *voice_args]
  return voice_loop_local.main()


if __name__ == "__main__":
  raise SystemExit(main())
