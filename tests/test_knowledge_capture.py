"""Tests for Core managed-file capture."""

# Author: Clive Bostock
# Date: 12-Jul-2026
# Description: Verifies path, hash, UTF-8, and idempotent capture behaviour.

from __future__ import annotations

from datetime import datetime
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
PLUGINS_ROOT = PROJECT_ROOT / "plugins"
for path in (SRC_ROOT, PLUGINS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from drop_box.models import DropBoxHandoffJob  # noqa: E402
from orac_core.knowledge import DropBoxCaptureRequest  # noqa: E402
from orac_core.knowledge import KnowledgeManagedFileCaptureService  # noqa: E402
from orac_core.knowledge.capture import KnowledgeCaptureError  # noqa: E402


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


class _FailOnceRepository:
    """Fail the first database registration and accept the retry."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def submit_managed_file(self, **kwargs) -> int:
        """Retain calls while injecting one transient registration failure."""
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            raise RuntimeError("ORA-03113: connection lost after promotion")
        return 789


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
            digest = result.content_sha256
            self.assertTrue(
                (managed / "sha256" / digest[:2] / digest[2:4] / digest).is_file()
            )
            self.assertEqual(result.content_uri, f"sha256:{digest}")
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
            output_set = json.loads(repo.calls[0]["output_set_json"])
            self.assertEqual(output_set["set_kind"], "SINGLE")
            self.assertEqual(len(output_set["members"]), 1)
            primary = output_set["members"][0]
            self.assertEqual(primary["role"], "PRIMARY")
            self.assertEqual(primary["media_type"], "text/markdown; charset=utf-8")
            normalised = b"# Note\nhello\n"
            normalised_digest = hashlib.sha256(normalised).hexdigest()
            self.assertEqual(primary["content_sha256"], normalised_digest)
            self.assertEqual(primary["storage_key"], f"sha256:{normalised_digest}")
            self.assertEqual(primary["byte_size"], len(normalised))
            self.assertEqual(
                (
                    managed
                    / "sha256"
                    / normalised_digest[:2]
                    / normalised_digest[2:4]
                    / normalised_digest
                ).read_bytes(),
                normalised,
            )

    def test_capture_rejects_noncanonical_producer_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "drop"
            root.mkdir()
            source = root / "note.md"
            source.write_text("source", encoding="utf-8")
            service = KnowledgeManagedFileCaptureService(
                managed_root=Path(temp) / "managed",
                repository=_Repository(),
            )
            base = _request(root, source)
            metadata = json.dumps(
                {
                    "schema_version": 1,
                    "producer_plugin_id": "drop_box",
                    "drop_location_id": 3,
                    "drop_job_id": 7,
                    "source_format": "markdown",
                    "fixed_option_identifiers": [],
                }
            )
            for text in ("\ufeffhello\n", "hello\r\n", "hello"):
                payload = text.encode("utf-8")
                request = replace(
                    base,
                    source_format_code="markdown",
                    source_mime_type="text/markdown",
                    normalised_markdown=text,
                    normalised_text_sha256=hashlib.sha256(payload).hexdigest(),
                    normalised_byte_size=len(payload),
                    output_mime_type="text/markdown; charset=utf-8",
                    extractor_code="dropbox_markdown_passthrough",
                    extractor_version="1",
                    extraction_metadata_json=metadata,
                )
                with self.subTest(text=repr(text)):
                    with self.assertRaisesRegex(
                        KnowledgeCaptureError,
                        "must not contain a BOM or CR and must end with LF",
                    ):
                        service.capture_drop_box_file(request)

    def test_capture_accepts_orac_home_handoff_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            orac_home = Path(temp) / "orac"
            root = orac_home / "docs"
            root.mkdir(parents=True)
            source = root / "source.md"
            source.write_text("# Source\n", encoding="utf-8")
            payload = source.read_bytes()
            row = {
                "DROP_JOB_ID": 10,
                "DROP_LOCATION_ID": 1,
                "LOCATION_CODE": "ORAC_DOCS",
                "LOCATION_ROOT": "${ORAC_HOME}/docs",
                "SOURCE_PATH": str(source),
                "SOURCE_FILENAME": source.name,
                "SOURCE_HASH": hashlib.sha256(payload).hexdigest(),
                "SOURCE_SIZE_BYTES": len(payload),
                "SOURCE_MTIME": datetime(2026, 8, 12, 12, 0),
                "EFFECTIVE_SCOPE_TYPE": "PROJECT",
                "EFFECTIVE_SCOPE_KEY": "ORAC_CORE",
                "EFFECTIVE_PROCESSING_PROFILE": "raw_reference",
                "EFFECTIVE_PROFILE_INSTRUCTION": None,
                "EFFECTIVE_INSTRUCTION": None,
                "EFFECTIVE_CLASSIFICATION_TAGS_JSON": '["RAW_REFERENCE"]',
            }

            with patch.dict(
                os.environ,
                {"ORAC_HOME": str(orac_home)},
                clear=False,
            ):
                request = DropBoxHandoffJob.from_row(row).to_capture_request()

            repo = _Repository()
            result = KnowledgeManagedFileCaptureService(
                managed_root=Path(temp) / "managed",
                repository=repo,
            ).capture_drop_box_file(request)

            self.assertEqual(result.ingestion_request_id, 456)
            self.assertEqual(
                repo.calls[0]["parent_source_reference"],
                "ORAC_DOCS:source.md",
            )
            self.assertEqual(
                repo.calls[0]["classification_tags_json"],
                '["RAW_REFERENCE"]',
            )

    def test_rejects_invalid_classification_code_payloads(self) -> None:
        invalid_payloads = (
            None,
            "not-json",
            "{}",
            "[]",
            '["raw_reference"]',
            '["Raw_Reference"]',
            '["RAW_REFERENCE","RAW_REFERENCE"]',
            '["RAW-REFERENCE"]',
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "drop"
            root.mkdir()
            source = root / "note.md"
            source.write_text("hello", encoding="utf-8")
            service = KnowledgeManagedFileCaptureService(
                managed_root=Path(temp) / "managed",
                repository=_Repository(),
            )

            for payload in invalid_payloads:
                request = replace(
                    _request(root, source),
                    classification_tags_json=payload,
                )
                with self.subTest(payload=payload):
                    with self.assertRaises(KnowledgeCaptureError):
                        service._validate_classification_tags(request)

    def test_legacy_upgrade_does_not_derive_classification_from_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "drop"
            root.mkdir()
            source = root / "note.md"
            source.write_text("hello", encoding="utf-8")
            request = replace(
                _request(root, source),
                classification_tags_json=None,
                processing_profile="markdown",
            )

            with self.assertRaisesRegex(
                KnowledgeCaptureError,
                "classification tag JSON",
            ):
                KnowledgeManagedFileCaptureService(
                    managed_root=Path(temp) / "managed",
                    repository=_Repository(),
                ).capture_drop_box_file(request)

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

    def test_rejects_source_symlink_even_when_target_is_inside_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "drop"
            root.mkdir()
            target = root / "target.md"
            target.write_text("hello", encoding="utf-8")
            source = root / "link.md"
            source.symlink_to(target)

            with self.assertRaisesRegex(KnowledgeCaptureError, "opened safely"):
                KnowledgeManagedFileCaptureService(
                    managed_root=Path(temp) / "managed",
                    repository=_Repository(),
                ).capture_drop_box_file(_request(root, source))

    def test_rejects_symlinked_source_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            target_root = base / "target"
            target_root.mkdir()
            source = target_root / "note.md"
            source.write_text("hello", encoding="utf-8")
            linked_root = base / "linked"
            linked_root.symlink_to(target_root, target_is_directory=True)
            linked_source = linked_root / source.name

            with self.assertRaisesRegex(KnowledgeCaptureError, "opened safely"):
                KnowledgeManagedFileCaptureService(
                    managed_root=base / "managed",
                    repository=_Repository(),
                ).capture_drop_box_file(_request(linked_root, linked_source))

    def test_rejects_non_regular_source_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "drop"
            root.mkdir()
            source = root / "note.md"
            source.write_text("hello", encoding="utf-8")
            request = _request(root, source)
            source.unlink()
            source.mkdir()
            request = replace(request, source_size_bytes=source.stat().st_size)

            with self.assertRaisesRegex(KnowledgeCaptureError, "regular file"):
                KnowledgeManagedFileCaptureService(
                    managed_root=Path(temp) / "managed",
                    repository=_Repository(),
                ).capture_drop_box_file(request)

    def test_rejects_hash_mismatch_and_cleans_temp(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "drop"
            managed = Path(temp) / "managed"
            root.mkdir()
            source = root / "note.md"
            source.write_text("hello", encoding="utf-8")
            request = _request(root, source, sha256="0" * 64)

            with self.assertRaisesRegex(KnowledgeCaptureError, "identity"):
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

    def test_database_failure_after_promotion_reuses_objects_on_retry(self) -> None:
        """A failed registration leaves verified objects reusable by a retry."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "drop"
            managed = Path(temp) / "managed"
            root.mkdir()
            source = root / "note.md"
            source.write_text("# Retry", encoding="utf-8")
            repository = _FailOnceRepository()
            service = KnowledgeManagedFileCaptureService(
                managed_root=managed,
                repository=repository,
            )
            request = _request(root, source)

            with self.assertRaisesRegex(RuntimeError, "after promotion"):
                service.capture_drop_box_file(request)

            promoted = [
                path for path in (managed / "sha256").rglob("*") if path.is_file()
            ]
            self.assertEqual(len(promoted), 2)
            result = service.capture_drop_box_file(request)

            self.assertEqual(result.ingestion_request_id, 789)
            self.assertTrue(result.duplicate_payload)
            self.assertEqual(len(repository.calls), 2)
            self.assertEqual(
                [path for path in (managed / "sha256").rglob("*") if path.is_file()],
                promoted,
            )
            self.assertEqual(list((managed / ".tmp").iterdir()), [])


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
        classification_tags_json='["RAW_REFERENCE"]',
        location_code="TEST",
        legacy_source_key=f"TEST:{source}",
    )


if __name__ == "__main__":
    unittest.main()
