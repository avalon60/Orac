"""Tests for Core knowledge preflight and legacy migration orchestration."""

# Author: Clive Bostock
# Date: 13-Aug-2026
# Description: Verifies dry-run, classification, batching, and retry behaviour.

from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from orac_core.knowledge.maintenance import KnowledgeMigrationService  # noqa: E402
from orac_core.knowledge.managed_store import KnowledgeManagedStore  # noqa: E402


class _Repository:
    """In-memory candidate source and migration call recorder."""

    def __init__(self, backfill: list[dict], raw: list[dict]) -> None:
        self.backfill = backfill
        self.raw = raw
        self.backfill_calls: list[dict] = []
        self.raw_calls: list[dict] = []

    def backfill_candidates(
        self,
        *,
        after_extraction_id: int | None,
        limit: int,
    ) -> list[dict]:
        return self._page(self.backfill, "extraction_id", after_extraction_id, limit)

    def raw_locator_candidates(
        self,
        *,
        after_document_version_id: int | None,
        limit: int,
    ) -> list[dict]:
        return self._page(
            self.raw,
            "document_version_id",
            after_document_version_id,
            limit,
        )

    @staticmethod
    def _page(
        rows: list[dict],
        key: str,
        after_id: int | None,
        limit: int,
    ) -> list[dict]:
        return [row.copy() for row in rows if row[key] > (after_id or 0)][:limit]

    def backfill_extraction(self, **kwargs) -> dict:
        self.backfill_calls.append(kwargs)
        return {
            "outcome": "BACKFILLED",
            "extraction_id": kwargs["extraction_id"],
            "artefact_id": 901,
            "relinked_chunk_set_count": 1,
        }

    def migrate_raw_locator(self, **kwargs) -> dict:
        self.raw_calls.append(kwargs)
        return {
            "outcome": "MIGRATED",
            "document_version_id": kwargs["document_version_id"],
        }


def _extraction(extraction_id: int, text: str = "# Legacy\n") -> dict:
    payload = text.encode("utf-8")
    return {
        "extraction_id": extraction_id,
        "document_version_id": extraction_id,
        "extractor_code": "legacy",
        "extractor_version": "1",
        "output_mime_type": "text/markdown; charset=utf-8",
        "text_sha256": hashlib.sha256(payload).hexdigest(),
        "extracted_text": text,
        "artefact_count": 0,
        "artefact_set_complete_yn": None,
        "primary_artefact_id": None,
        "primary_content_sha256": None,
        "primary_storage_key": None,
        "primary_byte_size": None,
        "legacy_chunk_set_count": 1,
        "artefact_chunk_set_count": 0,
    }


class KnowledgeMaintenanceTests(unittest.TestCase):
    """Tests safe migration classification and bounded apply operations."""

    def _stores(self, root: Path) -> tuple[KnowledgeManagedStore, KnowledgeManagedStore]:
        write_store = KnowledgeManagedStore(root)
        inspection_store = KnowledgeManagedStore.for_read_only_inspection(root)
        return write_store, inspection_store

    def test_preflight_classifies_backfill_and_current_raw_locator(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "managed"
            write_store, inspection_store = self._stores(root)
            raw = write_store.put_bytes(b"raw")
            repository = _Repository(
                [_extraction(1)],
                [
                    {
                        "document_version_id": 1,
                        "content_sha256": raw.identity.sha256,
                        "content_uri": raw.storage_key,
                        "byte_size": raw.identity.byte_size,
                    }
                ],
            )

            report = KnowledgeMigrationService(
                repository=repository,
                inspection_store=inspection_store,
            ).preflight()

            self.assertEqual(report.as_dict()["status"], "READY")
            self.assertEqual(report.backfill[0].reason_code, "BACKFILL_REQUIRED")
            self.assertEqual(report.raw_locators[0].reason_code, "RAW_LOCATOR_CURRENT")

    def test_dry_run_never_writes_store_or_database(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "managed"
            _write_store, inspection_store = self._stores(root)
            repository = _Repository([_extraction(1)], [])
            before = list((root / "sha256").rglob("*"))

            report = KnowledgeMigrationService(
                repository=repository,
                inspection_store=inspection_store,
            ).backfill(apply=False, limit=25)

            self.assertEqual(report["status"], "DRY_RUN")
            self.assertEqual(repository.backfill_calls, [])
            self.assertEqual(list((root / "sha256").rglob("*")), before)

    def test_apply_is_bounded_and_builds_primary_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "managed"
            write_store, inspection_store = self._stores(root)
            repository = _Repository([_extraction(1), _extraction(2)], [])

            report = KnowledgeMigrationService(
                repository=repository,
                inspection_store=inspection_store,
                write_store=write_store,
            ).backfill(apply=True, limit=1)

            self.assertEqual(report["status"], "COMPLETED")
            self.assertEqual(len(repository.backfill_calls), 1)
            envelope = repository.backfill_calls[0]["output_set_json"]
            self.assertIn('"role":"PRIMARY"', envelope)
            self.assertIn('"logical_name":"primary.md"', envelope)

    def test_noncanonical_extraction_blocks_apply(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "managed"
            write_store, inspection_store = self._stores(root)
            repository = _Repository([_extraction(1, "missing LF")], [])

            report = KnowledgeMigrationService(
                repository=repository,
                inspection_store=inspection_store,
                write_store=write_store,
            ).backfill(apply=True, limit=1)

            self.assertEqual(report["status"], "BLOCKED")
            self.assertEqual(repository.backfill_calls, [])

    def test_verified_legacy_locator_is_migrated(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "managed"
            write_store, inspection_store = self._stores(root)
            raw = write_store.put_bytes(b"raw")
            digest = raw.identity.sha256
            legacy = write_store.legacy_storage_key(digest)
            repository = _Repository(
                [],
                [
                    {
                        "document_version_id": 7,
                        "content_sha256": digest,
                        "content_uri": legacy,
                        "byte_size": raw.identity.byte_size,
                    }
                ],
            )

            report = KnowledgeMigrationService(
                repository=repository,
                inspection_store=inspection_store,
            ).migrate_raw_locators(apply=True, limit=1)

            self.assertEqual(report["status"], "COMPLETED")
            self.assertEqual(repository.raw_calls[0]["expected_locator"], legacy)


if __name__ == "__main__":
    unittest.main()
