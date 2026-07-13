"""Tests for scope-bound Core knowledge retrieval."""

# Author: Clive Bostock
# Date: 13-Jul-2026
# Description: Verifies retrieval scope, vector compatibility, and malformed vector rejection.

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from orac_core.knowledge import KnowledgeRetrievalError
from orac_core.knowledge import KnowledgeRetrievalService

FIXTURE_SENTENCE = "ORAC_INGESTION_FIXTURE_20260713_LUMEN_PATHWAY"


class _Provider:
    @property
    def model_id(self) -> str:
        return "hash-embedding-v1"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_text(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        if "lumen" in text.lower() or FIXTURE_SENTENCE in text:
            return [1.0, 0.0]
        return [0.0, 1.0]


class _Repository:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.calls: list[dict] = []

    def load_searchable_chunks(self, **kwargs) -> list[dict]:
        self.calls.append(kwargs)
        return self.rows


def _row(**overrides) -> dict:
    row = {
        "ingestion_request_id": 101,
        "document_id": 201,
        "document_version_id": 301,
        "source_object_id": 401,
        "source_reference": "drop_box:source:abc",
        "parent_source_reference": "LOCAL_TEST:fixture.md",
        "chunk_id": 501,
        "chunk_no": 1,
        "target_scope_type": "PROJECT",
        "target_scope_key": "orac",
        "embedding_model_identifier": "hash-embedding-v1",
        "embedding_dimensions": 2,
        "chunk_text": f"{FIXTURE_SENTENCE} confirms scoped retrieval.",
        "embedding_vector": json.dumps([1.0, 0.0]),
    }
    row.update(overrides)
    return row


class KnowledgeRetrievalTests(unittest.TestCase):
    """Tests safe retrieval over approved searchable chunk rows."""

    def test_requires_scope_without_cross_scope_authorisation(self) -> None:
        service = KnowledgeRetrievalService(
            repository=_Repository([_row()]),
            embedding_provider=_Provider(),
        )

        with self.assertRaisesRegex(KnowledgeRetrievalError, "requires"):
            service.search("lumen", target_scope_type=None, target_scope_key=None)

    def test_search_passes_scope_and_scores_compatible_vectors(self) -> None:
        repository = _Repository([_row()])
        service = KnowledgeRetrievalService(
            repository=repository,
            embedding_provider=_Provider(),
        )

        results = service.search(
            "lumen pathway",
            target_scope_type="project",
            target_scope_key="orac",
        )

        self.assertEqual(repository.calls[0]["target_scope_type"], "PROJECT")
        self.assertEqual(repository.calls[0]["target_scope_key"], "orac")
        self.assertEqual(
            repository.calls[0]["embedding_model_identifier"], "hash-embedding-v1"
        )
        self.assertEqual(repository.calls[0]["embedding_dimensions"], 2)
        self.assertFalse(repository.calls[0]["allow_cross_scope"])
        self.assertEqual(len(results), 1)
        self.assertIn(FIXTURE_SENTENCE, results[0].chunk_text)
        self.assertEqual(results[0].score, 1.0)

    def test_cross_scope_requires_explicit_authorisation(self) -> None:
        repository = _Repository(
            [_row(target_scope_type="PLUGIN", target_scope_key="alpha")]
        )
        service = KnowledgeRetrievalService(
            repository=repository,
            embedding_provider=_Provider(),
        )

        results = service.search(
            "lumen",
            target_scope_type=None,
            target_scope_key=None,
            allow_cross_scope=True,
        )

        self.assertTrue(repository.calls[0]["allow_cross_scope"])
        self.assertEqual(results[0].target_scope_type, "PLUGIN")

    def test_rejects_model_identifier_mismatch(self) -> None:
        service = KnowledgeRetrievalService(
            repository=_Repository([_row(embedding_model_identifier="other-model")]),
            embedding_provider=_Provider(),
        )

        with self.assertRaisesRegex(KnowledgeRetrievalError, "model"):
            service.search(
                "lumen", target_scope_type="PROJECT", target_scope_key="orac"
            )

    def test_rejects_dimension_mismatch(self) -> None:
        service = KnowledgeRetrievalService(
            repository=_Repository([_row(embedding_dimensions=3)]),
            embedding_provider=_Provider(),
        )

        with self.assertRaisesRegex(KnowledgeRetrievalError, "dimension"):
            service.search(
                "lumen", target_scope_type="PROJECT", target_scope_key="orac"
            )

    def test_rejects_malformed_vectors(self) -> None:
        service = KnowledgeRetrievalService(
            repository=_Repository([_row(embedding_vector='["nope", 1.0]')]),
            embedding_provider=_Provider(),
        )

        with self.assertRaisesRegex(KnowledgeRetrievalError, "non-numeric"):
            service.search(
                "lumen", target_scope_type="PROJECT", target_scope_key="orac"
            )


if __name__ == "__main__":
    unittest.main()
