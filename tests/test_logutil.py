"""Tests for Orac logging utility helpers."""
# Author: Clive Bostock
# Date: 2026-06-05
# Description: Verifies duplicate log sink prevention helpers.

from __future__ import annotations

from pathlib import Path
import os
import asyncio
import sys
import tempfile
import unittest

from loguru import logger as logr


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from lib.logutil import _fd_targets_path, log_call


class LogutilTests(unittest.TestCase):
    """Tests for low-level logging utility behaviour."""

    def test_fd_targets_path_detects_matching_file_descriptor(self) -> None:
        """A descriptor opened against a file should match that file path."""
        with tempfile.NamedTemporaryFile() as handle:
            self.assertTrue(_fd_targets_path(handle.fileno(), Path(handle.name)))

    def test_fd_targets_path_rejects_non_file_descriptors(self) -> None:
        """A pipe descriptor should not be treated as the log file path."""
        read_fd, write_fd = os.pipe()
        try:
            with tempfile.NamedTemporaryFile() as handle:
                self.assertFalse(_fd_targets_path(write_fd, Path(handle.name)))
        finally:
            os.close(read_fd)
            os.close(write_fd)

    def test_log_call_times_sync_and_async_calls_without_call_data(self) -> None:
        """TRACE records identify calls without exposing inputs or results."""
        records = []
        sink_id = logr.add(records.append, level="TRACE", format="{message}")
        try:
            @log_call
            def sync_call(secret: str) -> str:
                return secret

            @log_call
            async def async_call(secret: str) -> str:
                return secret

            self.assertEqual(sync_call("private-input"), "private-input")
            self.assertEqual(asyncio.run(async_call("private-output")), "private-output")
        finally:
            logr.remove(sink_id)

        messages = [record.record["message"] for record in records]
        self.assertEqual(len(messages), 2)
        self.assertTrue(all("[ok; elapsed " in message for message in messages))
        self.assertTrue(all("private-" not in message for message in messages))

    def test_log_call_records_failures_and_stream_completion(self) -> None:
        """Exceptions propagate and stream timing covers iteration."""
        records = []
        sink_id = logr.add(records.append, level="TRACE", format="{message}")
        try:
            @log_call
            def failing_call() -> None:
                raise ValueError("private-error")

            @log_call
            async def failing_async_call() -> None:
                raise RuntimeError("private-async-error")

            @log_call
            def stream():
                yield "first"
                yield "second"

            @log_call
            async def async_stream():
                yield "first"

            with self.assertRaises(ValueError):
                failing_call()
            with self.assertRaises(RuntimeError):
                asyncio.run(failing_async_call())
            self.assertEqual(list(stream()), ["first", "second"])

            async def consume() -> list[str]:
                return [item async for item in async_stream()]

            self.assertEqual(asyncio.run(consume()), ["first"])
        finally:
            logr.remove(sink_id)

        messages = [record.record["message"] for record in records]
        self.assertEqual(len(messages), 4)
        self.assertEqual(
            sum("[raised; elapsed " in message for message in messages), 2
        )
        self.assertTrue(all("private-" not in message for message in messages))

    def test_log_call_is_filtered_below_trace(self) -> None:
        """A DEBUG sink does not receive call timing records."""
        records = []
        sink_id = logr.add(records.append, level="DEBUG")
        try:
            @log_call
            def call() -> None:
                return None

            call()
        finally:
            logr.remove(sink_id)
        self.assertEqual(records, [])


if __name__ == "__main__":
    unittest.main()
