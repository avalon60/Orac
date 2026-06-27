"""Tests for the drop-box filesystem scanner."""
# Author: Clive Bostock
# Date: 27-Jun-2026
# Description: Verifies file filtering, stability checks, hashing, and deferral.

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLUGINS_ROOT = PROJECT_ROOT / "plugins"
if str(PLUGINS_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGINS_ROOT))

from drop_box.models import DropLocation
from drop_box.scanner import DropBoxScanner


class _Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 6, 27, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


class DropBoxScannerTests(unittest.TestCase):
    """Tests deterministic scanner behaviour using temporary directories."""

    def test_filters_extensions_size_recursive_symlinks_and_ignores(self) -> None:
        clock = _Clock()
        scanner = DropBoxScanner(clock=clock)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "accepted.md").write_text("ok", encoding="utf-8")
            (root / "skip.txt").write_text("no", encoding="utf-8")
            (root / "large.md").write_text("x" * 12, encoding="utf-8")
            (root / ".hidden.md").write_text("hidden", encoding="utf-8")
            (root / "draft.tmp").write_text("tmp", encoding="utf-8")
            sub = root / "sub"
            sub.mkdir()
            (sub / "nested.md").write_text("nested", encoding="utf-8")
            (root / "link.md").symlink_to(root / "accepted.md")

            location = DropLocation(
                drop_location_id=1,
                location_code="TEST",
                display_name="Test",
                path=root,
                allowed_extensions=("md",),
                recursive=False,
                max_file_size_bytes=10,
                stability_seconds=1,
            )
            first = scanner.scan_locations([location])
            clock.advance(1)
            second = scanner.scan_locations([location])

            self.assertEqual([item.source_filename for item in second.stable_candidates], ["accepted.md"])
            self.assertEqual(first.skipped_disallowed_type, 1)
            self.assertEqual(first.skipped_too_large, 1)
            self.assertEqual(first.skipped_ignored, 2)
            self.assertEqual(first.skipped_symlink, 1)

            recursive = DropLocation(
                drop_location_id=2,
                location_code="RECURSIVE",
                display_name="Recursive",
                path=root,
                allowed_extensions=("md",),
                recursive=True,
                max_file_size_bytes=10,
                stability_seconds=1,
            )
            scanner.scan_locations([recursive])
            clock.advance(1)
            recursive_result = scanner.scan_locations([recursive])

            self.assertEqual(
                sorted(item.source_filename for item in recursive_result.stable_candidates),
                ["accepted.md", "nested.md"],
            )

    def test_missing_path_is_reported(self) -> None:
        scanner = DropBoxScanner()
        result = scanner.scan_locations(
            [
                DropLocation(
                    drop_location_id=1,
                    location_code="MISSING",
                    display_name="Missing",
                    path=Path("/tmp/definitely-not-an-orac-drop-path"),
                )
            ]
        )

        self.assertEqual(result.missing_paths, 1)

    def test_hash_candidate_defers_when_file_changes_during_hash(self) -> None:
        clock = _Clock()
        scanner = DropBoxScanner(clock=clock)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "source.md"
            path.write_text("before", encoding="utf-8")
            location = DropLocation(
                drop_location_id=1,
                location_code="TEST",
                display_name="Test",
                path=root,
                stability_seconds=1,
            )
            scanner.scan_locations([location])
            clock.advance(1)
            candidate = scanner.scan_locations([location]).stable_candidates[0]
            path.write_text("after", encoding="utf-8")

            self.assertIsNone(scanner.hash_candidate(candidate))

    def test_sha256_hash_is_calculated_for_unchanged_candidate(self) -> None:
        clock = _Clock()
        scanner = DropBoxScanner(clock=clock)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "source.md").write_text("content", encoding="utf-8")
            location = DropLocation(
                drop_location_id=1,
                location_code="TEST",
                display_name="Test",
                path=root,
                stability_seconds=1,
            )
            scanner.scan_locations([location])
            clock.advance(1)
            candidate = scanner.scan_locations([location]).stable_candidates[0]

            hashed = scanner.hash_candidate(candidate)

            self.assertIsNotNone(hashed)
            self.assertEqual(
                hashed.source_hash,
                "ed7002b439e9ac845f22357d822bac1444730fbdb6016d3ec9432297b9ec9f73",
            )


if __name__ == "__main__":
    unittest.main()
