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

from drop_box.models import (
    CandidateFile,
    DropBoxHandoffJob,
    DropLocation,
    FileObservation,
    HashedCandidate,
)
from drop_box.models import ScanResult
from orac_core.knowledge import ManagedCaptureResult
from orac_core.knowledge.capture import KnowledgeCaptureError
from drop_box.service import DropBoxService


class _Repository:
    def __init__(
        self,
        *,
        exists: bool = False,
        configuration_errors: list[str] | None = None,
        handoff_available: bool = False,
    ) -> None:
        self.exists = exists
        self.configuration_errors = configuration_errors or []
        self.handoff_available = handoff_available
        self.enqueued: list[HashedCandidate] = []
        self.handoff_jobs: list[DropBoxHandoffJob] = []
        self.status_updates: list[dict] = []
        self.core_acceptances: list[dict] = []
        self.committed = False
        self.closed = False

    def load_configuration_errors(self):
        return self.configuration_errors

    def load_enabled_locations(self):
        return [_location()]

    def observation_exists(self, candidate):
        return self.exists

    def enqueue_job(self, hashed):
        self.enqueued.append(hashed)

    def load_handoff_jobs(self):
        return self.handoff_jobs

    def core_handoff_available(self):
        return self.handoff_available

    def update_status(self, **kwargs):
        self.status_updates.append(kwargs)

    def record_core_acceptance(self, **kwargs):
        self.core_acceptances.append(kwargs)

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


class _Logger:
    def __init__(self) -> None:
        self.warnings: list[str] = []

    def log_warning(self, message: str) -> None:
        self.warnings.append(message)


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

    def test_inactive_profile_configuration_errors_are_logged(self) -> None:
        repository = _Repository(
            configuration_errors=[
                "LEGACY: Processing profile is inactive. processing_profile=old_profile"
            ]
        )
        logger = _Logger()
        service = DropBoxService(
            logger=logger,
            scanner=_Scanner(),
            repository_factory=lambda _context: repository,
        )

        service.tick(object())

        self.assertEqual(service.last_stats.configuration_errors, 1)
        self.assertTrue(logger.warnings)
        self.assertIn("Processing profile is inactive", logger.warnings[0])

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

    def test_manifest_declares_auto_start_and_run_on_start(self) -> None:
        manifest = (PROJECT_ROOT / "plugins" / "drop_box.json").read_text(
            encoding="utf-8"
        )

        self.assertIn('"start_policy": "auto"', manifest)
        self.assertIn('"run_on_start": true', manifest)

    def test_handoff_success_marks_job_handed_off_after_core_capture(self) -> None:
        repository = _Repository(handoff_available=True)
        repository.handoff_jobs = [_handoff_job()]
        capture = _CaptureService()
        service = DropBoxService(
            scanner=_Scanner(),
            repository_factory=lambda _context: repository,
            capture_service_factory=lambda _context: capture,
        )

        service.tick(object())

        self.assertEqual(capture.requests[0].drop_job_id, 99)
        self.assertEqual(capture.requests[0].location_code, "TEST")
        self.assertEqual(capture.requests[0].source_key, "TEST:source.md")
        self.assertEqual(
            capture.requests[0].legacy_source_key, "TEST:/tmp/drop/source.md"
        )
        self.assertEqual(repository.status_updates, [])
        self.assertEqual(
            repository.core_acceptances[-1]["knowledge_ingestion_request_id"],
            1234,
        )
        self.assertEqual(service.last_stats.handed_off, 1)

    def test_handoff_source_key_uses_location_code_and_relative_path(self) -> None:
        first = _handoff_job(
            location_root=Path("/old/root"),
            source_path=Path("/old/root/sub/source.md"),
            source_filename="source.md",
        ).to_capture_request()
        migrated = _handoff_job(
            location_root=Path("/new/root"),
            source_path=Path("/new/root/sub/source.md"),
            source_filename="source.md",
        ).to_capture_request()
        renamed = _handoff_job(
            location_root=Path("/old/root"),
            source_path=Path("/old/root/sub/renamed.md"),
            source_filename="renamed.md",
        ).to_capture_request()

        self.assertEqual(first.source_key, "TEST:sub/source.md")
        self.assertEqual(migrated.source_key, first.source_key)
        self.assertEqual(renamed.source_key, "TEST:sub/renamed.md")
        self.assertNotEqual(renamed.source_key, first.source_key)

    def test_capture_validation_failure_marks_job_failed(self) -> None:
        repository = _Repository(handoff_available=True)
        repository.handoff_jobs = [_handoff_job()]
        service = DropBoxService(
            logger=_Logger(),
            scanner=_Scanner(),
            repository_factory=lambda _context: repository,
            capture_service_factory=lambda _context: _CaptureService(
                fail=KnowledgeCaptureError("source file changed")
            ),
        )

        service.tick(object())

        self.assertEqual(repository.status_updates[-1]["status_code"], "failed")
        self.assertIn(
            "Drop Box managed-file capture failed",
            repository.status_updates[-1]["error_message"],
        )
        self.assertEqual(service.last_stats.handoff_failed, 1)

    def test_transient_core_handoff_failure_leaves_job_queued(self) -> None:
        repository = _Repository(handoff_available=True)
        repository.handoff_jobs = [_handoff_job()]
        logger = _Logger()
        service = DropBoxService(
            logger=logger,
            scanner=_Scanner(),
            repository_factory=lambda _context: repository,
            capture_service_factory=lambda _context: _CaptureService(
                fail=RuntimeError("package invalid")
            ),
        )

        service.tick(object())

        self.assertEqual(repository.status_updates, [])
        self.assertEqual(repository.core_acceptances, [])
        self.assertEqual(service.last_stats.handoff_failed, 0)
        self.assertIn("remains queued", logger.warnings[-1])

    def test_missing_core_handoff_leaves_jobs_queued(self) -> None:
        repository = _Repository(handoff_available=False)
        repository.handoff_jobs = [_handoff_job()]
        capture = _CaptureService()
        logger = _Logger()
        service = DropBoxService(
            logger=logger,
            scanner=_Scanner(),
            repository_factory=lambda _context: repository,
            capture_service_factory=lambda _context: capture,
        )

        service.tick(object())

        self.assertEqual(capture.requests, [])
        self.assertEqual(repository.status_updates, [])
        self.assertEqual(service.last_stats.handoff_failed, 0)
        self.assertTrue(logger.warnings)
        self.assertIn("Core handoff skipped", logger.warnings[-1])


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


class _CaptureService:
    def __init__(self, *, fail: Exception | None = None) -> None:
        self.fail = fail
        self.requests = []

    def capture_drop_box_file(self, request):
        self.requests.append(request)
        if self.fail:
            raise self.fail
        return ManagedCaptureResult(
            ingestion_request_id=1234,
            content_uri="sha256/aa/bb/" + "a" * 64,
            content_sha256="a" * 64,
        )


def _handoff_job(
    *,
    location_root: Path = Path("/tmp/drop"),
    source_path: Path = Path("/tmp/drop/source.md"),
    source_filename: str = "source.md",
) -> DropBoxHandoffJob:
    observed_at = datetime(2026, 6, 27, 12, 0, tzinfo=UTC)
    return DropBoxHandoffJob(
        drop_job_id=99,
        drop_location_id=1,
        location_code="TEST",
        location_root=location_root,
        source_path=source_path,
        source_filename=source_filename,
        source_hash="a" * 64,
        source_size_bytes=12,
        source_mtime=observed_at,
        effective_scope_type="PROJECT",
        effective_scope_key="orac",
        effective_processing_profile="markdown",
        effective_instruction="ingest",
    )


if __name__ == "__main__":
    unittest.main()
