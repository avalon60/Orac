"""Tests for the drop-box scheduled service."""
# Author: Clive Bostock
# Date: 27-Jun-2026
# Description: Verifies service orchestration, duplicate skips, and tick locking.

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
PLUGINS_ROOT = PROJECT_ROOT / "plugins"
for path in (SRC_ROOT, PLUGINS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from drop_box.models import CandidateFile, DropLocation, FileObservation, HashedCandidate
from drop_box.models import ScanResult
from drop_box.service import DropBoxService


class _Repository:
    def __init__(self, *, exists: bool = False) -> None:
        self.exists = exists
        self.enqueued: list[HashedCandidate] = []
        self.committed = False
        self.closed = False

    def load_enabled_locations(self):
        return [_location()]

    def observation_exists(self, candidate):
        return self.exists

    def enqueue_job(self, hashed):
        self.enqueued.append(hashed)

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        self.closed = True


class _Scanner:
    def __init__(self, *, hash_changed: bool = False) -> None:
        self.hash_changed = hash_changed
        self.hash_calls = 0
        self.candidate = _candidate()

    def scan_locations(self, locations):
        return ScanResult(stable_candidates=[self.candidate], observed_candidates=1)

    def hash_candidate(self, candidate):
        self.hash_calls += 1
        if self.hash_changed:
            return None
        return HashedCandidate(candidate=candidate, source_hash="b" * 64)


class DropBoxServiceTests(unittest.TestCase):
    """Tests service orchestration rules."""

    def test_tick_enqueues_hashed_candidates_and_commits(self) -> None:
        repository = _Repository()
        scanner = _Scanner()
        service = DropBoxService(
            scanner=scanner,
            repository_factory=lambda _context: repository,
        )

        service.tick(object())

        self.assertEqual(scanner.hash_calls, 1)
        self.assertEqual(len(repository.enqueued), 1)
        self.assertTrue(repository.committed)
        self.assertTrue(repository.closed)
        self.assertEqual(service.last_stats.enqueued, 1)

    def test_existing_observation_skips_hashing(self) -> None:
        repository = _Repository(exists=True)
        scanner = _Scanner()
        service = DropBoxService(
            scanner=scanner,
            repository_factory=lambda _context: repository,
        )

        service.tick(object())

        self.assertEqual(scanner.hash_calls, 0)
        self.assertEqual(service.last_stats.skipped_existing_observation, 1)
        self.assertEqual(repository.enqueued, [])

    def test_changed_during_hash_is_deferred(self) -> None:
        repository = _Repository()
        scanner = _Scanner(hash_changed=True)
        service = DropBoxService(
            scanner=scanner,
            repository_factory=lambda _context: repository,
        )

        service.tick(object())

        self.assertEqual(service.last_stats.deferred_changed_during_hash, 1)
        self.assertEqual(repository.enqueued, [])

    def test_overlapping_tick_is_skipped(self) -> None:
        repository = _Repository()
        service = DropBoxService(
            scanner=_Scanner(),
            repository_factory=lambda _context: repository,
        )
        self.assertTrue(service._tick_lock.acquire(blocking=False))
        try:
            service.tick(object())
        finally:
            service._tick_lock.release()

        self.assertTrue(service.last_stats.overlapping_tick_skipped)

    def test_manifest_declares_manual_start_and_run_on_start(self) -> None:
        manifest = (PROJECT_ROOT / "plugins" / "drop_box.json").read_text(
            encoding="utf-8"
        )

        self.assertIn('"start_policy": "manual"', manifest)
        self.assertIn('"run_on_start": true', manifest)


def _location() -> DropLocation:
    return DropLocation(
        drop_location_id=1,
        location_code="TEST",
        display_name="Test",
        path=Path("/tmp/drop"),
    )


def _candidate() -> CandidateFile:
    observed_at = datetime(2026, 6, 27, 12, 0, tzinfo=UTC)
    return CandidateFile(
        location=_location(),
        observation=FileObservation(
            path=Path("/tmp/drop/source.md"),
            size_bytes=1,
            mtime_ns=1,
            source_mtime=observed_at,
            observed_at=observed_at,
        ),
    )


if __name__ == "__main__":
    unittest.main()
