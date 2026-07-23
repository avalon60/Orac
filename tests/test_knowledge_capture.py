"""Tests for Core managed-file capture."""

# Author: Clive Bostock
# Date: 12-Jul-2026
# Description: Verifies path, hash, UTF-8, and idempotent capture behaviour.

from __future__ import annotations

from datetime import datetime
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from orac_core.knowledge import DropBoxCaptureRequest
from orac_core.knowledge import KnowledgeManagedFileCaptureService
from orac_core.knowledge.capture import KnowledgeCaptureError


class _Repository:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def submit_managed_file(self, **kwargs) -> int:
        self.calls.append(kwargs)
        return 456


class _FailingRepository:
    def __init__(self, message: str) -> None:
        self.message = message

    def submit_managed_file(self, **kwargs) -> int:
        raise RuntimeError(self.message)


class KnowledgeCaptureTests(unittest.TestCase):
    """Tests Core-managed file capture safety."""

    def test_capture_copies_hashes_and_registers_managed_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "drop"
            managed = Path(temp) / "managed"
            root.mkdir()
            source = root / "note.md"
            source.write_text("# Note\nhello", encoding="utf-8")
            repo = _Repository()

            result = KnowledgeManagedFileCaptureService(
                managed_root=managed,
                repository=repo,
            ).capture_drop_box_file(_request(root, source))

            self.assertEqual(result.ingestion_request_id, 456)
            self.assertTrue((managed / result.content_uri).is_file())
            source_key = "TEST:note.md"
            expected_reference = (
                "drop_box:source:"
                + hashlib.sha256(source_key.encode("utf-8")).hexdigest()
            )
            self.assertEqual(repo.calls[0]["source_reference"], expected_reference)
            self.assertEqual(repo.calls[0]["parent_source_reference"], source_key)
            self.assertEqual(
                repo.calls[0]["legacy_parent_source_reference"],
                f"TEST:{source}",
            )
            self.assertEqual(
                repo.calls[0]["source_modified_on"],
                _request(root, source).source_mtime,
            )

    def test_rejects_path_outside_location_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "drop"
            other = Path(temp) / "other"
            root.mkdir()
            other.mkdir()
            source = other / "note.md"
            source.write_text("hello", encoding="utf-8")

            with self.assertRaisesRegex(KnowledgeCaptureError, "outside"):
                KnowledgeManagedFileCaptureService(
                    managed_root=Path(temp) / "managed",
                    repository=_Repository(),
                ).capture_drop_box_file(_request(root, source))

    def test_rejects_hash_mismatch_and_cleans_temp(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "drop"
            managed = Path(temp) / "managed"
            root.mkdir()
            source = root / "note.md"
            source.write_text("hello", encoding="utf-8")
            request = _request(root, source, sha256="0" * 64)

            with self.assertRaisesRegex(KnowledgeCaptureError, "hash"):
                KnowledgeManagedFileCaptureService(
                    managed_root=managed,
                    repository=_Repository(),
                ).capture_drop_box_file(request)

            temp_dir = managed / ".tmp"
            self.assertEqual(list(temp_dir.glob("*")) if temp_dir.exists() else [], [])

    def test_rejects_non_utf8_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "drop"
            root.mkdir()
            source = root / "note.md"
            source.write_bytes(b"\xff\xfe")

            with self.assertRaisesRegex(KnowledgeCaptureError, "UTF-8"):
                KnowledgeManagedFileCaptureService(
                    managed_root=Path(temp) / "managed",
                    repository=_Repository(),
                ).capture_drop_box_file(_request(root, source))

    def test_duplicate_capture_reuses_existing_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "drop"
            managed = Path(temp) / "managed"
            root.mkdir()
            source = root / "note.txt"
            source.write_text("hello", encoding="utf-8")
            service = KnowledgeManagedFileCaptureService(
                managed_root=managed,
                repository=_Repository(),
            )

            first = service.capture_drop_box_file(_request(root, source))
            second = service.capture_drop_box_file(_request(root, source))

            self.assertFalse(first.duplicate_payload)
            self.assertTrue(second.duplicate_payload)
            temp_dir = managed / ".tmp"
            self.assertEqual(list(temp_dir.glob("*")) if temp_dir.exists() else [], [])

    def test_scope_rejection_is_redacted_as_capture_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "drop"
            root.mkdir()
            source = root / "note.md"
            source.write_text("hello", encoding="utf-8")
            service = KnowledgeManagedFileCaptureService(
                managed_root=Path(temp) / "managed",
                repository=_FailingRepository(
                    "ORA-20409: scope SECRET_PROJECT is not registered"
                ),
            )

            with self.assertRaisesRegex(
                KnowledgeCaptureError,
                "requested knowledge scope is not available",
            ) as raised:
                service.capture_drop_box_file(_request(root, source))

            self.assertNotIn("SECRET_PROJECT", str(raised.exception))

    def test_unrelated_database_failure_remains_retryable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "drop"
            root.mkdir()
            source = root / "note.md"
            source.write_text("hello", encoding="utf-8")
            service = KnowledgeManagedFileCaptureService(
                managed_root=Path(temp) / "managed",
                repository=_FailingRepository("ORA-03113: connection lost"),
            )

            with self.assertRaisesRegex(RuntimeError, "ORA-03113"):
                service.capture_drop_box_file(_request(root, source))


def _request(
    root: Path,
    source: Path,
    *,
    sha256: str | None = None,
) -> DropBoxCaptureRequest:
    payload = source.read_bytes()
    return DropBoxCaptureRequest(
        drop_job_id=7,
        drop_location_id=3,
        location_root=root,
        source_path=source,
        source_filename=source.name,
        source_sha256=sha256 or hashlib.sha256(payload).hexdigest(),
        source_size_bytes=len(payload),
        source_mtime=datetime(2026, 7, 12, 12, 0),
        target_scope_type="PROJECT",
        target_scope_key="orac",
        processing_profile="markdown",
        processing_instruction="ingest",
        location_code="TEST",
        legacy_source_key=f"TEST:{source}",
    )


if __name__ == "__main__":
    unittest.main()
