"""Tests for the ad-hoc Orac Piper speech utility.
# Author: Clive Bostock
# Date: 2026-05-14
# Description: Verifies command-line text handling and TTS worker invocation.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import types
from unittest import TestCase
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ORAC_SAY_PATH = PROJECT_ROOT / "bin" / "orac_say.py"


def _load_orac_say_module():
  """Load the non-package ``bin/orac_say.py`` module for tests."""
  spec = importlib.util.spec_from_file_location("orac_say", ORAC_SAY_PATH)
  if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load module from {ORAC_SAY_PATH}")
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  return module


class _FakeWorker:
  """Fake TTS worker used to verify utility orchestration."""

  def __init__(self) -> None:
    """Initialise fake worker state."""
    self.is_running = False
    self.error_count = 0
    self.last_error = None
    self.enqueued: list[tuple[str, str, str]] = []
    self.completed: list[tuple[str, str]] = []
    self.stopped: list[bool] = []

  def start(self) -> None:
    """Mark the fake worker as running."""
    self.is_running = True

  def enqueue_text(self, *, session_id: str, turn_id: str, text: str) -> bool:
    """Capture enqueued speech text."""
    self.enqueued.append((session_id, turn_id, text))
    return bool(text.strip())

  def mark_turn_input_complete(
    self,
    *,
    session_id: str,
    turn_id: str,
  ) -> None:
    """Capture completed turn input."""
    self.completed.append((session_id, turn_id))

  def wait_until_idle(self, *, timeout: float | None = None) -> bool:
    """Pretend queued playback drained."""
    return True

  def stop(self, *, drain: bool = True) -> None:
    """Capture stop calls."""
    self.stopped.append(drain)
    self.is_running = False


class OracSayTests(TestCase):
  """Tests for the ``orac-say`` utility."""

  def test_resolve_text_joins_positional_arguments(self) -> None:
    """Positional words should become one speech string."""
    module = _load_orac_say_module()
    args = argparse.Namespace(text=["Hello", "from", "Orac"])

    self.assertEqual(module.resolve_text(args), "Hello from Orac")

  def test_speak_text_queues_text_on_configured_worker(self) -> None:
    """The utility should reuse the configured local TTS worker."""
    module = _load_orac_say_module()
    worker = _FakeWorker()
    fake_package = types.ModuleType("orac_voice")
    fake_worker_module = types.ModuleType("orac_voice.tts_worker")
    fake_worker_module.create_local_tts_worker_from_config = lambda **_kwargs: worker

    with patch.object(module, "_ensure_src_path"), patch.dict(
      "sys.modules",
      {
        "orac_voice": fake_package,
        "orac_voice.tts_worker": fake_worker_module,
      },
    ):
      result = module.speak_text(text="Testing Piper.", wait_seconds=2.0)

    self.assertEqual(result, 0)
    self.assertEqual(worker.enqueued[0][0], "orac-say")
    self.assertEqual(worker.enqueued[0][2], "Testing Piper.")
    self.assertEqual(len(worker.completed), 1)
    self.assertEqual(worker.stopped, [True])

  def test_speak_text_rejects_empty_text(self) -> None:
    """Empty input should fail before creating a worker."""
    module = _load_orac_say_module()

    self.assertEqual(module.speak_text(text="   "), 2)
