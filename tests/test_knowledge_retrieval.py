"""Tests for scope-bound Core knowledge retrieval."""

# Author: Clive Bostock
# Date: 18-Jul-2026
# Description: Verifies scoped lexical retrieval, vector compatibility, and safe limits.

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
from orac_core.knowledge import KnowledgeScope
from orac_core.knowledge.repository import KnowledgeIngestionRepository

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


class _ConnectionBoundValue:
    """Test value that can only be read while its database session is open."""

    def __init__(self, session, value: str) -> None:
        self._session = session
        self._value = value
        self.read_count = 0

    def read(self) -> str:
        """Return the value while the owning fake session remains open."""
        if self._session.closed:
            raise RuntimeError("not connected to database")
        self.read_count += 1
        return self._value


class _SearchCursor:
    """Minimal cursor returning connection-bound knowledge values."""

    def __init__(self, session) -> None:
        self._session = session
        self.description = [("EMBEDDING_VECTOR",), ("CHUNK_TEXT",)]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def execute(self, statement, parameters) -> None:
        self.statement = statement
        self.parameters = parameters

    def fetchall(self) -> list[tuple[object, object]]:
        return [(self._session.vector, self._session.chunk_text)]


class _SearchSession:
    """Minimal session recording when its connection-bound values are read."""

    def __init__(self) -> None:
        self.closed = False
        self.vector = _ConnectionBoundValue(self, "[1.0,0.0]")
        self.chunk_text = _ConnectionBoundValue(self, "stable scanner evidence")

    def cursor(self) -> _SearchCursor:
        return _SearchCursor(self)

    def close(self) -> None:
        self.closed = True


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
        "target_scope_key": "ORAC_CORE",
        "embedding_model_identifier": "hash-embedding-v1",
        "embedding_dimensions": 2,
        "chunk_text": f"{FIXTURE_SENTENCE} confirms the lumen pathway retrieval.",
        "embedding_vector": json.dumps([1.0, 0.0]),
    }
    row.update(overrides)
    return row


class KnowledgeRetrievalTests(unittest.TestCase):
    """Tests safe retrieval over approved searchable chunk rows."""

    def test_requires_canonical_scope(self) -> None:
        service = KnowledgeRetrievalService(
            repository=_Repository([_row()]), embedding_provider=_Provider()
        )
        with self.assertRaisesRegex(KnowledgeRetrievalError, "requires"):
            service.search("lumen", target_scope_type="", target_scope_key="")

    def test_repository_materializes_lobs_before_closing_session(self) -> None:
        session = _SearchSession()
        repository = KnowledgeIngestionRepository(session_factory=lambda: session)

        rows = repository.load_searchable_chunks(
            target_scope_type="PLUGIN",
            target_scope_key="drop_box",
            embedding_model_identifier="hash-embedding-v1",
            embedding_dimensions=32,
            candidate_limit=10,
        )

        self.assertTrue(session.closed)
        self.assertEqual(rows[0]["embedding_vector"], "[1.0,0.0]")
        self.assertEqual(rows[0]["chunk_text"], "stable scanner evidence")
        self.assertEqual(session.vector.read_count, 1)
        self.assertEqual(session.chunk_text.read_count, 1)

    def test_search_passes_scope_and_scores_compatible_vectors(self) -> None:
        repository = _Repository([_row()])
        service = KnowledgeRetrievalService(
            repository=repository, embedding_provider=_Provider()
        )
        results = service.search(
            "lumen pathway",
            target_scope_type="project",
            target_scope_key="ORAC_CORE",
        )
        self.assertEqual(repository.calls[0]["target_scope_type"], "PROJECT")
        self.assertEqual(repository.calls[0]["target_scope_key"], "ORAC_CORE")
        self.assertEqual(repository.calls[0]["candidate_limit"], 1000)
        self.assertEqual(len(results), 1)
        self.assertGreaterEqual(results[0].score, 0.75)

    def test_no_evidence_below_lexical_threshold(self) -> None:
        service = KnowledgeRetrievalService(
            repository=_Repository([_row(chunk_text="Unrelated material")]),
            embedding_provider=_Provider(),
        )
        outcome = service.retrieve(
            "lumen pathway", scope=KnowledgeScope("PROJECT", "ORAC_CORE")
        )
        self.assertEqual(outcome.status, "no_evidence")
        self.assertEqual(outcome.reason_codes, ("no_evidence_above_threshold",))

    def test_route_control_and_scope_words_do_not_create_false_evidence(self) -> None:
        service = KnowledgeRetrievalService(
            repository=_Repository(
                [
                    _row(
                        target_scope_type="PLUGIN",
                        target_scope_key="drop_box",
                        chunk_text=(
                            "Use the Drop Box knowledge source to explain file "
                            "processing and operational configuration."
                        ),
                    )
                ]
            ),
            embedding_provider=_Provider(),
        )

        outcome = service.retrieve(
            (
                "Use the Drop Box knowledge base to explain mitochondrial "
                "ribosome assembly in Antarctic krill."
            ),
            scope=KnowledgeScope("PLUGIN", "drop_box"),
        )

        self.assertEqual(outcome.status, "no_evidence")
        self.assertEqual(outcome.threshold_count, 0)

    def test_candidate_limit_fails_without_partial_results(self) -> None:
        service = KnowledgeRetrievalService(
            repository=_Repository([_row(chunk_id=index) for index in range(3)]),
            embedding_provider=_Provider(),
        )
        outcome = service.retrieve(
            "lumen",
            scope=KnowledgeScope("PROJECT", "ORAC_CORE"),
            max_candidate_chunks=2,
        )
        self.assertEqual(outcome.status, "failed")
        self.assertEqual(outcome.reason_codes, ("candidate_limit_exceeded",))

    def test_rejects_model_identifier_mismatch(self) -> None:
        service = KnowledgeRetrievalService(
            repository=_Repository([_row(embedding_model_identifier="other-model")]),
            embedding_provider=_Provider(),
        )
        with self.assertRaisesRegex(KnowledgeRetrievalError, "model"):
            service.search(
                "lumen", target_scope_type="PROJECT", target_scope_key="ORAC_CORE"
            )

    def test_rejects_dimension_mismatch(self) -> None:
        service = KnowledgeRetrievalService(
            repository=_Repository([_row(embedding_dimensions=3)]),
            embedding_provider=_Provider(),
        )
        with self.assertRaisesRegex(KnowledgeRetrievalError, "dimension"):
            service.search(
                "lumen", target_scope_type="PROJECT", target_scope_key="ORAC_CORE"
            )

    def test_rejects_malformed_vectors(self) -> None:
        service = KnowledgeRetrievalService(
            repository=_Repository([_row(embedding_vector='["nope", 1.0]')]),
            embedding_provider=_Provider(),
        )
        with self.assertRaisesRegex(KnowledgeRetrievalError, "non_numeric"):
            service.search(
                "lumen", target_scope_type="PROJECT", target_scope_key="ORAC_CORE"
            )


if __name__ == "__main__":
    unittest.main()
