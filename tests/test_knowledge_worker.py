"""Tests for the Core knowledge ingestion worker."""

# Author: Clive Bostock
# Date: 12-Jul-2026
# Description: Verifies scheduled worker health and stale-error behaviour.

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

from orac_core.knowledge.worker import KnowledgeIngestionService  # noqa: E402
from orac_core.knowledge.managed_store import (  # noqa: E402
    ManagedStoreConfigurationError,
)
from orac_core.knowledge.managed_store import ManagedStoreError  # noqa: E402
from orac_core.knowledge.worker import managed_store_failure  # noqa: E402


class _Config:
    def __init__(self, values: dict[str, int | str]) -> None:
        self.values = values

    def int_config_value(self, section: str, key: str, *, default: int) -> int:
        del section
        return int(self.values.get(key, default))

    def config_value(self, section: str, key: str, *, default: str) -> str:
        del section
        return str(self.values.get(key, default))


class _IdleRepository:
    def try_claim_next_request(self, *, owner_id: str, lease_seconds: int) -> None:
        del owner_id, lease_seconds
        return None


class _Repository:
    def __init__(
        self,
        *,
        managed_root: Path,
        request_ids: list[int],
        fail_request_ids: set[int] | None = None,
    ) -> None:
        self._managed_root = managed_root
        self._managed_root.chmod(0o750)
        for directory, mode in (
            (self._managed_root / ".tmp", 0o700),
            (self._managed_root / "sha256", 0o750),
        ):
            directory.mkdir(exist_ok=True)
            directory.chmod(mode)
        self._request_ids = request_ids
        self._fail_request_ids = fail_request_ids or set()
        self._payloads: dict[int, tuple[str, str, int]] = {}
        self.claims = 0
        self.completed: list[int] = []
        self.failed: list[dict] = []
        self.stages: list[tuple[int, str, str]] = []
        self.embeddings: list[int] = []
        self.existing_extractions: dict[int, tuple[int, str]] = {}
        self.created_extractions = 0
        self.inserted_chunk_texts: list[str] = []

    def add_payload(self, request_id: int, text: str) -> None:
        payload = text.encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        payload_path = self._managed_root / "sha256" / digest[:2] / digest[2:4] / digest
        payload_path.parent.mkdir(parents=True, exist_ok=True)
        current = payload_path.parent
        while current != self._managed_root:
            current.chmod(0o750)
            current = current.parent
        payload_path.write_bytes(payload)
        payload_path.chmod(0o600)
        self._payloads[request_id] = (
            f"sha256:{digest}",
            digest,
            len(payload),
        )

    def try_claim_next_request(
        self, *, owner_id: str, lease_seconds: int
    ) -> int | None:
        del owner_id, lease_seconds
        self.claims += 1
        if not self._request_ids:
            return None
        return self._request_ids.pop(0)

    def request_detail(self, request_id: int) -> dict:
        content_uri, content_sha256, byte_size = self._payloads[request_id]
        detail = {
            "ingestion_request_id": request_id,
            "lease_owner": "worker",
            "lease_token": f"token-{request_id}",
            "content_uri": content_uri,
            "content_sha256": content_sha256,
            "byte_size": byte_size,
            "original_filename": f"payload-{request_id}.md",
            "source_modified_on": None,
        }
        existing = self.existing_extractions.get(request_id)
        if existing is not None:
            detail["extraction_id"], detail["extracted_text"] = existing
        return detail

    def mark_stage(
        self,
        *,
        ingestion_request_id: int,
        owner_id: str,
        lease_token: str,
        status: str,
        stage: str,
    ) -> None:
        del owner_id, lease_token
        self.stages.append((ingestion_request_id, status, stage))

    def ensure_document_version(
        self,
        *,
        ingestion_request_id: int,
        title: str | None,
        source_modified_on: object | None,
    ) -> int:
        del title, source_modified_on
        if ingestion_request_id in self._fail_request_ids:
            raise RuntimeError(f"boom {ingestion_request_id}")
        return ingestion_request_id * 10

    def create_extraction(
        self,
        *,
        document_version_id: int,
        extractor_code: str,
        extractor_version: str,
        extracted_text: str,
        text_sha256: str,
    ) -> int:
        del extractor_code, extractor_version, extracted_text, text_sha256
        self.created_extractions += 1
        return document_version_id + 1

    def create_chunk_set(
        self,
        *,
        extraction_id: int,
        chunker_code: str,
        chunker_version: str,
        chunk_size_tokens: int,
        overlap_tokens: int,
    ) -> int:
        del chunker_code, chunker_version, chunk_size_tokens, overlap_tokens
        return extraction_id + 1

    def insert_chunk(
        self,
        *,
        chunk_set_id: int,
        chunk_no: int,
        span_start: int,
        span_end: int,
        chunk_text: str,
        token_count: int,
        content_sha256: str,
        metadata_json: str | None = None,
    ) -> int:
        self.inserted_chunk_texts.append(chunk_text)
        del (
            chunk_set_id,
            span_start,
            span_end,
            token_count,
            content_sha256,
            metadata_json,
        )
        return chunk_no

    def upsert_embedding_model(
        self,
        *,
        provider_code: str,
        model_name: str,
        model_revision: str,
        dimensions: int,
    ) -> int:
        del provider_code, model_name, model_revision, dimensions
        return 77

    def insert_embedding(
        self,
        *,
        chunk_id: int,
        embedding_model_id: int,
        vector: list[float],
        embedding_text_sha256: str,
    ) -> None:
        del embedding_model_id, vector, embedding_text_sha256
        self.embeddings.append(chunk_id)

    def complete_request(
        self,
        *,
        ingestion_request_id: int,
        owner_id: str,
        lease_token: str,
    ) -> None:
        del owner_id, lease_token
        self.completed.append(ingestion_request_id)

    def fail_request(
        self,
        *,
        ingestion_request_id: int,
        owner_id: str,
        lease_token: str,
        error_code: str,
        error_message: str,
        retryable: bool,
    ) -> None:
        del owner_id, lease_token
        self.failed.append(
            {
                "ingestion_request_id": ingestion_request_id,
                "error_code": error_code,
                "error_message": error_message,
                "retryable": retryable,
            }
        )


class KnowledgeIngestionWorkerTests(unittest.TestCase):
    """Tests scheduled worker state transitions."""

    def test_idle_tick_clears_previous_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = KnowledgeIngestionService(
                repository=_IdleRepository(),
                managed_root=Path(temp),
            )
            service.last_error = "previous package error"

            service.tick(object())

            self.assertIsNone(service.last_error)
            self.assertTrue(service.health(object()))

    def test_tick_processes_configured_batch_with_independent_error_boundaries(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            managed_root = Path(temp)
            repository = _Repository(
                managed_root=managed_root,
                request_ids=[1, 2, 3],
                fail_request_ids={2},
            )
            for request_id in (1, 2, 3):
                repository.add_payload(request_id, f"content for request {request_id}")

            service = KnowledgeIngestionService(
                config_mgr=_Config({"batch_size": 3}),
                repository=repository,
                managed_root=managed_root,
            )

            service.tick(object())

            self.assertEqual(repository.completed, [1, 3])
            self.assertEqual(
                [failure["ingestion_request_id"] for failure in repository.failed],
                [2],
            )
            self.assertEqual(
                repository.failed[0]["error_code"], "KNOWLEDGE_WORKER_ERROR"
            )
            self.assertEqual(service.last_error, "boom 2")
            self.assertFalse(service.health(object()))

    def test_tick_honours_configured_batch_size(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            managed_root = Path(temp)
            repository = _Repository(managed_root=managed_root, request_ids=[1, 2, 3])
            for request_id in (1, 2, 3):
                repository.add_payload(request_id, f"content for request {request_id}")

            service = KnowledgeIngestionService(
                config_mgr=_Config({"batch_size": 2}),
                repository=repository,
                managed_root=managed_root,
            )

            service.tick(object())

            self.assertEqual(repository.completed, [1, 2])
            self.assertEqual(repository.failed, [])

    def test_empty_payload_is_visible_non_retryable_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            managed_root = Path(temp)
            repository = _Repository(managed_root=managed_root, request_ids=[1])
            repository.add_payload(1, " \n\t ")
            service = KnowledgeIngestionService(
                repository=repository,
                managed_root=managed_root,
            )

            service.tick(object())

            self.assertEqual(repository.completed, [])
            self.assertEqual(
                repository.failed[0]["error_code"], "EMPTY_MANAGED_PAYLOAD"
            )
            self.assertFalse(repository.failed[0]["retryable"])

    def test_existing_extraction_is_chunked_and_embedded_as_materialised_text(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            managed_root = Path(temp)
            repository = _Repository(managed_root=managed_root, request_ids=[1])
            repository.add_payload(1, "raw payload must not be extracted again")
            repository.existing_extractions[1] = (
                91,
                "# Existing extraction\n\nMaterialised lumen text.",
            )
            service = KnowledgeIngestionService(
                repository=repository,
                managed_root=managed_root,
            )

            service.tick(object())

            self.assertEqual(repository.created_extractions, 0)
            self.assertEqual(repository.completed, [1])
            self.assertEqual(repository.failed, [])
            self.assertTrue(repository.inserted_chunk_texts)
            self.assertIn(
                "Materialised lumen text.",
                "\n".join(repository.inserted_chunk_texts),
            )
            self.assertEqual(
                len(repository.embeddings), len(repository.inserted_chunk_texts)
            )

    def test_managed_store_reason_mapping_is_stable(self) -> None:
        expected = {
            "INVALID_STORAGE_KEY": ("INVALID_MANAGED_STORAGE_KEY", False),
            "STORAGE_KEY_IDENTITY_MISMATCH": (
                "INVALID_MANAGED_STORAGE_KEY",
                False,
            ),
            "MANAGED_OBJECT_SYMLINK": ("UNSAFE_MANAGED_PAYLOAD", False),
            "MANAGED_OBJECT_NOT_REGULAR": ("UNSAFE_MANAGED_PAYLOAD", False),
            "UNSAFE_STORE_LAYOUT": ("UNSAFE_MANAGED_PAYLOAD", False),
            "MANAGED_OBJECT_HASH_MISMATCH": (
                "CORRUPT_MANAGED_PAYLOAD",
                False,
            ),
            "MANAGED_OBJECT_SIZE_MISMATCH": (
                "CORRUPT_MANAGED_PAYLOAD",
                False,
            ),
            "MANAGED_OBJECT_MISSING": ("MISSING_MANAGED_PAYLOAD", False),
            "MANAGED_OBJECT_PERMISSION_INVALID": (
                "MANAGED_PAYLOAD_PERMISSION_ERROR",
                False,
            ),
            "MANAGED_STORE_TRANSIENT_IO": (
                "MANAGED_STORE_UNAVAILABLE",
                True,
            ),
            "MANAGED_STORE_IO_ERROR": (
                "MANAGED_STORE_UNAVAILABLE",
                False,
            ),
        }
        for reason_code, mapping in expected.items():
            with self.subTest(reason_code=reason_code):
                self.assertEqual(
                    managed_store_failure(
                        ManagedStoreError(
                            reason_code,
                            "test",
                            transient=reason_code == "MANAGED_STORE_TRANSIENT_IO",
                        )
                    ),
                    mapping,
                )
        self.assertEqual(
            managed_store_failure(
                ManagedStoreConfigurationError(
                    "STORE_HARDLINK_UNSUPPORTED",
                    "test",
                )
            ),
            ("MANAGED_STORE_CONFIGURATION_INVALID", False),
        )
        self.assertEqual(
            managed_store_failure(
                ManagedStoreConfigurationError(
                    "STORE_ROOT_IDENTITY_CHANGED",
                    "test",
                    transient=True,
                )
            ),
            ("MANAGED_STORE_UNAVAILABLE", True),
        )


if __name__ == "__main__":
    unittest.main()
