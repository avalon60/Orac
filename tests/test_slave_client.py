"""Tests for the Orac interactive TCP console client."""

# Author: Clive Bostock
# Date: 2026-08-31
# Description: Verifies opt-in TTS request metadata and console CLI parsing.

from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

SLAVE_PATH = SRC_ROOT / "view" / "slave.py"
SLAVE_SPEC = importlib.util.spec_from_file_location(
    "test_isolated_slave_client",
    SLAVE_PATH,
)
if SLAVE_SPEC is None or SLAVE_SPEC.loader is None:
    raise RuntimeError(f"Unable to load slave client from {SLAVE_PATH}")
slave = importlib.util.module_from_spec(SLAVE_SPEC)
SLAVE_SPEC.loader.exec_module(slave)


class SlaveClientTests(unittest.TestCase):
    """Verify the console client's TTS opt-in contract."""

    def test_prompt_request_defaults_to_text_channel(self) -> None:
        """Ordinary console requests should remain silent by default."""
        request = slave.build_prompt_request("Hello")

        self.assertEqual(request["meta"]["channel"], "text")

    def test_prompt_request_accepts_voice_channel(self) -> None:
        """Explicit voice-channel requests should opt into TTS."""
        request = slave.build_prompt_request("Hello", channel="voice")

        self.assertEqual(request["meta"]["channel"], "voice")

    def test_main_defaults_to_tts_disabled(self) -> None:
        """Starting without --tts should run a silent console session."""
        sentinel = object()
        calls: list[bool] = []

        def fake_client(*, tts_enabled: bool):
            calls.append(tts_enabled)
            return sentinel

        with (
            patch.object(slave, "tcp_client", new=fake_client),
            patch.object(slave.asyncio, "run") as run,
        ):
            result = slave.main([])

        self.assertEqual(result, 0)
        self.assertEqual(calls, [False])
        run.assert_called_once_with(sentinel)

    def test_main_tts_flag_enables_voice_channel_requests(self) -> None:
        """Supplying --tts should enable speech for the console session."""
        sentinel = object()
        calls: list[bool] = []

        def fake_client(*, tts_enabled: bool):
            calls.append(tts_enabled)
            return sentinel

        with (
            patch.object(slave, "tcp_client", new=fake_client),
            patch.object(slave.asyncio, "run") as run,
        ):
            result = slave.main(["--tts"])

        self.assertEqual(result, 0)
        self.assertEqual(calls, [True])
        run.assert_called_once_with(sentinel)

    def test_help_documents_tts_flag(self) -> None:
        """Standard CLI help should describe the opt-in flag."""
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:
                slave.main(["--help"])

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("--tts", output.getvalue())

    def test_unknown_arguments_fail_cleanly(self) -> None:
        """Unexpected CLI arguments should be rejected by argparse."""
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                slave.main(["--unknown"])

        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
