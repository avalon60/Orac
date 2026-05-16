"""Speak ad-hoc text through Orac's configured Piper voice.
# Author: Clive Bostock
# Date: 2026-05-14
# Description: Provides a small command-line utility for Piper speech output.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

from loguru import logger


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
DEFAULT_WAIT_SECONDS = 60.0


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
    prog="orac-say",
    description="Speak a text string through Orac's configured Piper voice.",
  )
  parser.add_argument(
    "text",
    nargs="*",
    help=(
      "Text to speak. If omitted and stdin is piped, text is read from stdin."
    ),
  )
  parser.add_argument(
    "--voice",
    help="Override the configured Piper voice name.",
  )
  parser.add_argument(
    "--voice-dir",
    help="Override the configured Piper voice directory.",
  )
  parser.add_argument(
    "--wait-seconds",
    type=float,
    default=DEFAULT_WAIT_SECONDS,
    help="Maximum seconds to wait for speech playback. Default: %(default)s.",
  )
  return parser


def resolve_text(args: argparse.Namespace) -> str:
  """Resolve speech text from positional arguments or piped stdin.

  Args:
    args (argparse.Namespace): Parsed command-line arguments.

  Returns:
    str: Text to speak.
  """
  positional_text = " ".join(args.text).strip()
  if positional_text:
    return positional_text

  if not sys.stdin.isatty():
    return sys.stdin.read().strip()

  return ""


def speak_text(
  *,
  text: str,
  voice: str | None = None,
  voice_dir: str | None = None,
  wait_seconds: float = DEFAULT_WAIT_SECONDS,
) -> int:
  """Speak text using Orac's configured local TTS worker.

  Args:
    text (str): Text to speak.
    voice (str | None): Optional Piper voice override.
    voice_dir (str | None): Optional Piper voice directory override.
    wait_seconds (float): Maximum seconds to wait for playback.

  Returns:
    int: Process exit code.
  """
  clean_text = text.strip()
  if not clean_text:
    logger.error("No text supplied to speak")
    return 2

  _ensure_src_path()
  from orac_voice.tts_worker import create_local_tts_worker_from_config

  worker = create_local_tts_worker_from_config(
    voice_name=voice,
    voice_dir=voice_dir,
  )
  if worker is None:
    logger.error("Voice output is disabled in orac.ini")
    return 2

  session_id = "orac-say"
  turn_id = f"say-{uuid.uuid4().hex[:12]}"

  worker.start()
  try:
    queued = worker.enqueue_text(
      session_id=session_id,
      turn_id=turn_id,
      text=clean_text,
    )
    worker.mark_turn_input_complete(session_id=session_id, turn_id=turn_id)

    if not queued:
      logger.error("No speakable text supplied")
      return 2

    if not worker.wait_until_idle(timeout=wait_seconds):
      logger.error("Timed out waiting for Piper speech playback")
      worker.stop(drain=False)
      return 1

    if worker.error_count:
      message = worker.last_error.message if worker.last_error else "unknown"
      logger.error("Piper speech playback failed: {}", message)
      return 1

    return 0
  finally:
    if worker.is_running:
      worker.stop(drain=True)


def main() -> int:
  """Run the command-line entrypoint.

  Returns:
    int: Process exit code.
  """
  parser = build_parser()
  args = parser.parse_args()
  return speak_text(
    text=resolve_text(args),
    voice=args.voice,
    voice_dir=args.voice_dir,
    wait_seconds=args.wait_seconds,
  )


if __name__ == "__main__":
  raise SystemExit(main())
