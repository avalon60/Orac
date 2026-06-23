"""Tests for Orac logging utility helpers."""
# Author: Clive Bostock
# Date: 2026-06-05
# Description: Verifies duplicate log sink prevention helpers.

from __future__ import annotations

from pathlib import Path
import os
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from lib.logutil import _fd_targets_path


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


if __name__ == "__main__":
    unittest.main()
