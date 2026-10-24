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

    def test_log_call_reports_nested_depth_and_restores_after_failure(self) -> None:
        """Nested calls advance depth and failures leave later calls at the root."""
        records = []
        sink_id = logr.add(records.append, level="TRACE")
        try:
            @log_call
            def recurse(remaining: int) -> None:
                if remaining:
                    recurse(remaining - 1)

            @log_call
            def fail() -> None:
                recurse(0)
                raise ValueError("private-error")

            recurse(2)
            with self.assertRaises(ValueError):
                fail()
            recurse(0)
        finally:
            logr.remove(sink_id)

        messages = [item.record["message"] for item in records]
        self.assertEqual(
            [message.rsplit("depth ", 1)[1].rstrip("]") for message in messages],
            ["2", "1", "0", "1", "0", "0"],
        )
        self.assertTrue(all("private-error" not in message for message in messages))

    def test_log_call_isolates_concurrent_async_calls_and_cancellation(self) -> None:
        """Concurrent tasks keep their own depth and cancellation restores it."""
        records = []
        sink_id = logr.add(records.append, level="TRACE")
        try:
            @log_call
            async def child() -> None:
                await asyncio.sleep(0)

            @log_call
            async def parent() -> None:
                await asyncio.gather(child(), child())

            @log_call
            async def cancelled() -> None:
                raise asyncio.CancelledError()

            async def run() -> None:
                await asyncio.gather(parent(), parent())
                with self.assertRaises(asyncio.CancelledError):
                    await cancelled()
                await child()

            asyncio.run(run())
        finally:
            logr.remove(sink_id)

        messages = [item.record["message"] for item in records]
        self.assertEqual(sum("depth 1]" in message for message in messages), 4)
        self.assertEqual(sum("depth 0]" in message for message in messages), 4)
        self.assertEqual(sum("[raised;" in message for message in messages), 1)

    def test_log_call_stream_depth_does_not_leak_between_yields(self) -> None:
        """Stream internals are nested while consumers resume at their own depth."""
        records = []
        sink_id = logr.add(records.append, level="TRACE")
        try:
            @log_call
            def leaf() -> None:
                pass

            @log_call
            def stream():
                leaf()
                yield "private-item"
                leaf()

            @log_call
            async def async_stream():
                leaf()
                yield "private-async-item"
                leaf()

            iterator = stream()
            self.assertEqual(next(iterator), "private-item")
            leaf()
            self.assertEqual(list(iterator), [])

            async def consume() -> None:
                iterator = async_stream()
                self.assertEqual(await anext(iterator), "private-async-item")
                leaf()
                self.assertEqual([item async for item in iterator], [])

            asyncio.run(consume())
        finally:
            logr.remove(sink_id)

        messages = [item.record["message"] for item in records]
        self.assertEqual(sum("depth 1]" in message for message in messages), 4)
        self.assertEqual(sum("depth 0]" in message for message in messages), 4)
        self.assertTrue(all("private-item" not in message for message in messages))

    def test_log_call_records_partial_stream_closure(self) -> None:
        """Closing suspended streams records their outcome at the root depth."""
        records = []
        sink_id = logr.add(records.append, level="TRACE")
        try:
            @log_call
            def stream():
                yield "first"
                yield "second"

            @log_call
            async def async_stream():
                yield "first"
                yield "second"

            iterator = stream()
            self.assertEqual(next(iterator), "first")
            iterator.close()

            async def consume() -> None:
                iterator = async_stream()
                self.assertEqual(await anext(iterator), "first")
                await iterator.aclose()

            asyncio.run(consume())
        finally:
            logr.remove(sink_id)

        messages = [item.record["message"] for item in records]
        self.assertEqual(len(messages), 2)
        self.assertTrue(all("[closed; elapsed " in message for message in messages))
        self.assertTrue(all("depth 0]" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
