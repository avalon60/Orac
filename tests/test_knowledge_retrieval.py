"""Tests for scope-bound Core knowledge retrieval."""

# Author: Clive Bostock
# Date: 07-Sep-2026
# Description: Verifies scoped lexical retrieval, vector compatibility, and safe limits.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from orac_core.knowledge import KnowledgeRetrievalError  # noqa: E402
from orac_core.knowledge import KnowledgeRetrievalService  # noqa: E402
from orac_core.knowledge import KnowledgeScope  # noqa: E402
from orac_core.knowledge.embeddings import KnowledgeEmbeddingProfile  # noqa: E402
from orac_core.knowledge.repository import (  # noqa: E402
    KnowledgeRetrievalRepository,
)

FIXTURE_SENTENCE = "ORAC_INGESTION_FIXTURE_20260713_LUMEN_PATHWAY"


class _Provider:
    production_allowed = True
    profile = KnowledgeEmbeddingProfile(
        provider_code="ollama",
        model_id="nomic-embed-text:latest",
        model_digest="a" * 64,
        dimensions=768,
        profile_version="knowledge-v1",
        document_input_prefix="search_document:",
        query_input_prefix="search_query:",
        retrieval_policy_version="knowledge-hybrid-v1",
        semantic_threshold=0.60,
    )

    @property
    def model_id(self) -> str:
        return self.profile.model_id

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0] + [0.0] * 767

    def _embed(self, text: str) -> list[float]:
        return [1.0] + [0.0] * 767


class _EmbeddingRepository:
    def active_profile(self) -> dict:
        return {
            "embedding_profile_id": 17,
            "profile_version": "knowledge-v1",
            "model_digest": "a" * 64,
            "dimensions": 768,
            "storage_layout_code": "ORACLE_VECTOR_768_FLOAT32_V1",
        }


class _ThreeDimensionProvider(_Provider):
    """Semantic fixture proving generic retrieval follows profile dimensions."""

    profile = KnowledgeEmbeddingProfile(
        provider_code="test-semantic",
        model_id="test-semantic-3d",
        model_digest="b" * 64,
        dimensions=3,
        profile_version="knowledge-test-3d",
        document_input_prefix="search_document:",
        query_input_prefix="search_query:",
        retrieval_policy_version="knowledge-hybrid-test",
        semantic_threshold=0.0,
        storage_layout_code="ORACLE_VECTOR_3_FLOAT32_V1",
    )

    def embed_query(self, text: str) -> list[float]:
        """Return a valid vector for the fixture's declared profile."""
        del text
        return [1.0, 0.0, 0.0]


class _ThreeDimensionEmbeddingRepository:
    """Return the active three-dimensional semantic test profile."""

    def active_profile(self) -> dict:
        """Return a profile matching the injected semantic provider."""
        return {
            "embedding_profile_id": 23,
            "profile_version": "knowledge-test-3d",
            "model_digest": "b" * 64,
            "dimensions": 3,
            "storage_layout_code": "ORACLE_VECTOR_3_FLOAT32_V1",
        }


class _Repository:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.calls: list[dict] = []

        self.outcomes: list[dict] = []

    def open_hybrid_search_candidates(self, **kwargs):
        self.calls.append(kwargs)
        return (
            kwargs["retrieval_id"],
            {"status": "APPROVED", "reason_code": "RETRIEVAL_APPROVED"},
            self.rows,
        )

    def open_plugin_hybrid_candidates(self, **kwargs):
        self.calls.append(kwargs)
        return (
            kwargs["retrieval_id"],
            {"status": "APPROVED", "reason_code": "RETRIEVAL_APPROVED"},
            self.rows,
        )

    def open_authorised_project_candidates(self, **kwargs):
        self.calls.append(kwargs)
        return (
            kwargs["retrieval_id"],
            {"status": "APPROVED", "reason_code": "RETRIEVAL_APPROVED"},
            self.rows,
        )

    def record_outcome(self, **kwargs) -> None:
        self.outcomes.append(kwargs)


class _Var:
    def __init__(self) -> None:
        self.value = None

    def getvalue(self):
        return self.value


class _ResultCursor:
    def __init__(self, session) -> None:
        self._session = session
        self.description = [
            ("EMBEDDING_VECTOR",),
            ("CHUNK_TEXT",),
            ("CLASSIFICATION_TAGS_JSON",),
            ("CHUNK_METADATA_JSON",),
            ("EXTRACTOR_METADATA_JSON",),
            ("ARTEFACT_METADATA_JSON",),
        ]

    def fetchall(self):
        return [
            (
                self._session.vector,
                self._session.chunk_text,
                self._session.classification,
                self._session.native_json,
                self._session.extractor_metadata,
                self._session.artefact_metadata,
            )
        ]

    def close(self) -> None:
        return None


class _ConnectionBoundValue:
    """Test value that can only be read while its database session is open."""

    def __init__(self, session, value: object) -> None:
        self._session = session
        self._value = value
        self.read_count = 0

    def read(self) -> object:
        """Return the value while the owning fake session remains open."""
        if self._session.closed:
            raise RuntimeError("not connected to database")
        self.read_count += 1
        return self._value


class _SearchCursor:
    """Minimal cursor returning connection-bound knowledge values."""

    def __init__(self, session) -> None:
        self._session = session

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def var(self, data_type):
        return _Var()

    def callproc(self, name, parameters) -> None:
        parameters[-2].value = json.dumps(
            {"status": "APPROVED", "reason_code": "RETRIEVAL_APPROVED"}
        )
        if isinstance(parameters[-1], _Var):
            parameters[-1].value = _ResultCursor(self._session)


class _SearchSession:
    """Minimal session recording when its connection-bound values are read."""

    def __init__(
        self,
        *,
        overrides: dict[str, object] | None = None,
    ) -> None:
        self.closed = False
        self._cursor_calls = 0
        self.vector = _ConnectionBoundValue(self, "[1.0,0.0]")
        self.chunk_text = _ConnectionBoundValue(self, "stable scanner evidence")
        self.classification = _ConnectionBoundValue(self, '["RAW_REFERENCE"]')
        self.native_json = {"source": "oracle-json"}
        self.extractor_metadata = {"producer": "drop_box", "schema_version": 1}
        self.artefact_metadata = {"sheet_name": "Overview"}
        for name, value in (overrides or {}).items():
            setattr(self, name, value)

    def cursor(self):
        self._cursor_calls += 1
        if self._cursor_calls % 2 == 0:
            return _ResultCursor(self)
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
        "embedding_model_identifier": "nomic-embed-text:latest",
        "embedding_dimensions": 768,
        "embedding_profile_id": 17,
        "semantic_score": 0.82,
        "lexical_score": 0.75,
        "semantic_rank": 1,
        "lexical_rank": 1,
        "chunk_text": f"{FIXTURE_SENTENCE} confirms the lumen pathway retrieval.",
    }
    row.update(overrides)
    return row


class KnowledgeRetrievalTests(unittest.TestCase):
    """Tests safe retrieval over approved searchable chunk rows."""

    def test_requires_canonical_scope(self) -> None:
        service = KnowledgeRetrievalService(
            repository=_Repository([_row()]),
            embedding_repository=_EmbeddingRepository(),
            embedding_provider=_Provider(),
        )
        with self.assertRaisesRegex(KnowledgeRetrievalError, "requires"):
            service.search(
                "lumen",
                target_scope_type="",
                target_scope_key="",
                principal_username="clive",
            )

    def test_query_dimensions_follow_the_active_profile_contract(self) -> None:
        """Generic retrieval must not encode the current Nomic dimensions."""
        service = KnowledgeRetrievalService(
            repository=_Repository(
                [
                    _row(
                        embedding_model_identifier="test-semantic-3d",
                        embedding_dimensions=3,
                        embedding_profile_id=23,
                    )
                ]
            ),
            embedding_repository=_ThreeDimensionEmbeddingRepository(),
            embedding_provider=_ThreeDimensionProvider(),
        )

        results = service.search(
            "lumen",
            target_scope_type="PROJECT",
            target_scope_key="ORAC_CORE",
            principal_username="clive",
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].embedding_dimensions, 3)

    def test_plugin_retrieval_uses_narrow_repository_path_and_audits_chunks(
        self,
    ) -> None:
        repository = _Repository(
            [_row(target_scope_type="PLUGIN", target_scope_key="weather")]
        )
        service = KnowledgeRetrievalService(
            repository=repository,
            embedding_repository=_EmbeddingRepository(),
            embedding_provider=_Provider(),
        )

        outcome = service.retrieve_for_plugin(
            "lumen",
            principal_username="clive",
            plugin_id="weather",
            max_selected_chunks=1,
            correlation_id="request-17",
        )

        self.assertEqual(outcome.status, "grounded")
        self.assertEqual(repository.calls[0]["plugin_id"], "weather")
        self.assertNotIn("target_scope_type", repository.calls[0])
        self.assertNotIn("target_scope_key", repository.calls[0])
        self.assertEqual(repository.calls[0]["principal_username"], "clive")
        self.assertEqual(repository.calls[0]["correlation_id"], "request-17")
        self.assertEqual(repository.outcomes[0]["selected_chunk_ids"], (501,))

    def test_repository_materializes_lobs_before_closing_session(self) -> None:
        session = _SearchSession()
        repository = KnowledgeRetrievalRepository(session_factory=lambda: session)

        _, _, rows = repository.open_hybrid_search_candidates(
            principal_username="clive",
            target_scope_type="PLUGIN",
            target_scope_key="drop_box",
            embedding_profile_id=17,
            query_vector=[1.0, 0.0],
            lexical_tokens=["stable"],
            lexical_phrase="stable scanner evidence",
            semantic_limit=10,
            lexical_limit=10,
        )

        self.assertTrue(session.closed)
        self.assertEqual(rows[0]["embedding_vector"], "[1.0,0.0]")
        self.assertEqual(rows[0]["chunk_text"], "stable scanner evidence")
        self.assertEqual(rows[0]["classification_tags_json"], '["RAW_REFERENCE"]')
        self.assertEqual(rows[0]["chunk_metadata_json"], session.native_json)
        self.assertEqual(rows[0]["extractor_metadata_json"], session.extractor_metadata)
        self.assertEqual(rows[0]["artefact_metadata_json"], session.artefact_metadata)
        self.assertEqual(session.vector.read_count, 1)
        self.assertEqual(session.chunk_text.read_count, 1)
        self.assertEqual(session.classification.read_count, 1)

    def test_repository_rejects_non_text_retrieval_clob_payloads(self) -> None:
        for attribute, field_name in (
            ("vector", "embedding_vector"),
            ("chunk_text", "chunk_text"),
            ("classification", "classification_tags_json"),
        ):
            with self.subTest(field_name=field_name):
                session = _SearchSession()
                value = _ConnectionBoundValue(session, b"not text")
                setattr(session, attribute, value)
                repository = KnowledgeRetrievalRepository(
                    session_factory=lambda: session
                )

                with self.assertRaisesRegex(TypeError, field_name):
                    repository.open_hybrid_search_candidates(
                        principal_username="clive",
                        target_scope_type="PLUGIN",
                        target_scope_key="drop_box",
                        embedding_profile_id=17,
                        query_vector=[1.0, 0.0],
                        lexical_tokens=["stable"],
                        lexical_phrase="stable scanner evidence",
                        semantic_limit=10,
                        lexical_limit=10,
                    )

                self.assertTrue(session.closed)
                self.assertEqual(value.read_count, 1)

    def test_repository_rejects_direct_bytes_in_retrieval_clob_fields(self) -> None:
        for attribute, field_name in (
            ("vector", "embedding_vector"),
            ("chunk_text", "chunk_text"),
            ("classification", "classification_tags_json"),
        ):
            with self.subTest(field_name=field_name):
                session = _SearchSession(overrides={attribute: b"not text"})
                repository = KnowledgeRetrievalRepository(
                    session_factory=lambda: session
                )

                with self.assertRaisesRegex(TypeError, field_name):
                    repository.open_hybrid_search_candidates(
                        principal_username="clive",
                        target_scope_type="PLUGIN",
                        target_scope_key="drop_box",
                        embedding_profile_id=17,
                        query_vector=[1.0, 0.0],
                        lexical_tokens=["stable"],
                        lexical_phrase="stable scanner evidence",
                        semantic_limit=10,
                        lexical_limit=10,
                    )

                self.assertTrue(session.closed)

    def test_search_passes_scope_and_scores_compatible_vectors(self) -> None:
        repository = _Repository([_row()])
        service = KnowledgeRetrievalService(
            repository=repository,
            embedding_repository=_EmbeddingRepository(),
            embedding_provider=_Provider(),
        )
        results = service.search(
            "lumen pathway",
            principal_username="clive",
            target_scope_type="project",
            target_scope_key="ORAC_CORE",
        )
        self.assertEqual(repository.calls[0]["target_scope_type"], "PROJECT")
        self.assertEqual(repository.calls[0]["target_scope_key"], "ORAC_CORE")
        self.assertEqual(repository.calls[0]["semantic_limit"], 50)
        self.assertEqual(repository.calls[0]["lexical_limit"], 50)
        self.assertEqual(repository.calls[0]["embedding_profile_id"], 17)
        self.assertEqual(len(results), 1)
        self.assertGreaterEqual(results[0].score, 0.75)

    def test_authorised_project_search_ranks_globally_without_descriptor_input(
        self,
    ) -> None:
        repository = _Repository(
            [
                _row(
                    chunk_id=501,
                    target_scope_key="GENERAL_DOCS",
                    semantic_rank=2,
                    lexical_rank=2,
                ),
                _row(
                    chunk_id=502,
                    target_scope_key="AI_DOCS",
                    semantic_rank=1,
                    lexical_rank=1,
                    original_filename="AI-OS-Book.docx",
                ),
            ]
        )
        service = KnowledgeRetrievalService(
            repository=repository,
            embedding_repository=_EmbeddingRepository(),
            embedding_provider=_Provider(),
        )

        outcome = service.retrieve_authorised_projects(
            "Please summarise John Elder's AI-OS.",
            principal_username="clive",
            max_selected_chunks=2,
            timeout_seconds=10,
        )

        self.assertEqual(outcome.status, "grounded")
        self.assertIsNone(outcome.scope)
        self.assertEqual(
            tuple(scope.canonical_name for scope in outcome.scopes),
            ("PROJECT:AI_DOCS", "PROJECT:GENERAL_DOCS"),
        )
        self.assertEqual(outcome.results[0].chunk_id, 502)
        self.assertEqual(repository.calls[0]["timeout_seconds"], 10)
        self.assertNotIn("target_scope_key", repository.calls[0])

    def test_authorised_project_search_can_focus_lexical_follow_up_terms(
        self,
    ) -> None:
        """Contextual semantics and current-turn lexical intent remain separate."""
        repository = _Repository([_row()])
        service = KnowledgeRetrievalService(
            repository=repository,
            embedding_repository=_EmbeddingRepository(),
            embedding_provider=_Provider(),
        )

        service.retrieve_authorised_projects(
            "Earlier subject. Does it require a command line?",
            lexical_query="terminal application setup",
            principal_username="clive",
        )

        self.assertEqual(
            repository.calls[0]["lexical_tokens"],
            ["terminal", "application", "setup"],
        )
        self.assertEqual(
            repository.calls[0]["lexical_phrase"],
            "terminal application setup",
        )

    def test_authorised_project_search_rejects_non_project_rows(self) -> None:
        service = KnowledgeRetrievalService(
            repository=_Repository(
                [_row(target_scope_type="PLUGIN", target_scope_key="drop_box")]
            ),
            embedding_repository=_EmbeddingRepository(),
            embedding_provider=_Provider(),
        )

        outcome = service.retrieve_authorised_projects(
            "lumen",
            principal_username="clive",
        )

        self.assertEqual(outcome.status, "failed")
        self.assertEqual(outcome.malformed_count, 1)

    def test_substantive_prose_precedes_pandoc_navigation_candidates(self) -> None:
        repository = _Repository(
            [
                _row(
                    chunk_id=501,
                    semantic_rank=1,
                    lexical_rank=1,
                    chunk_text=(
                        "TABLE OF CONTENTS\n"
                        "The AI Operating System...............................59"
                    ),
                ),
                _row(
                    chunk_id=502,
                    semantic_rank=2,
                    lexical_rank=2,
                    chunk_text=(
                        "An AI-OS is a folder containing workflows, code, data, "
                        "logs, and instructions coordinated by AI."
                    ),
                ),
            ]
        )
        service = KnowledgeRetrievalService(
            repository=repository,
            embedding_repository=_EmbeddingRepository(),
            embedding_provider=_Provider(),
        )

        outcome = service.retrieve(
            "John Elder AI-OS",
            principal_username="clive",
            scope=KnowledgeScope("PROJECT", "ORAC_CORE"),
            max_selected_chunks=1,
        )

        self.assertEqual(outcome.status, "grounded")
        self.assertEqual(outcome.results[0].chunk_id, 502)

    def test_selected_continuation_promotes_available_predecessor(self) -> None:
        """A split sentence includes its preceding authorised candidate."""
        repository = _Repository(
            [
                _row(
                    chunk_id=502,
                    chunk_no=2,
                    semantic_rank=1,
                    lexical_rank=1,
                    chunk_text="8 continues the setup explanation.",
                ),
                _row(
                    chunk_id=501,
                    chunk_no=1,
                    semantic_rank=20,
                    lexical_rank=20,
                    chunk_text="The setup names the supported applications and",
                ),
            ]
        )
        service = KnowledgeRetrievalService(
            repository=repository,
            embedding_repository=_EmbeddingRepository(),
            embedding_provider=_Provider(),
        )

        outcome = service.retrieve_authorised_projects(
            "setup applications",
            principal_username="clive",
            max_selected_chunks=2,
        )

        self.assertEqual(
            [result.chunk_id for result in outcome.results],
            [501, 502],
        )

    def test_selected_split_end_promotes_available_successor(self) -> None:
        """A selected chunk ending mid-sentence includes its continuation."""
        repository = _Repository(
            [
                _row(
                    chunk_id=501,
                    chunk_no=1,
                    semantic_rank=1,
                    lexical_rank=1,
                    chunk_text="The setup continues in the next chunk",
                ),
                _row(
                    chunk_id=502,
                    chunk_no=2,
                    semantic_rank=20,
                    lexical_rank=20,
                    chunk_text="with the decisive terminal requirement.",
                ),
            ]
        )
        service = KnowledgeRetrievalService(
            repository=repository,
            embedding_repository=_EmbeddingRepository(),
            embedding_provider=_Provider(),
        )

        outcome = service.retrieve_authorised_projects(
            "setup terminal",
            principal_username="clive",
            max_selected_chunks=2,
        )

        self.assertEqual(
            [result.chunk_id for result in outcome.results],
            [501, 502],
        )

    def test_native_oracle_metadata_is_canonical_json_in_search_results(self) -> None:
        service = KnowledgeRetrievalService(
            repository=_Repository(
                [
                    _row(
                        extractor_metadata_json={
                            "zeta": Decimal("2"),
                            "alpha": Decimal("1.25"),
                        },
                        chunk_metadata_json={"source_row_start": Decimal("3")},
                    )
                ]
            ),
            embedding_repository=_EmbeddingRepository(),
            embedding_provider=_Provider(),
        )

        outcome = service.retrieve(
            "lumen pathway",
            principal_username="clive",
            scope=KnowledgeScope("PROJECT", "ORAC_CORE"),
        )

        self.assertEqual(outcome.status, "grounded")
        self.assertEqual(
            outcome.results[0].extractor_metadata_json,
            '{"alpha":1.25,"zeta":2}',
        )
        self.assertEqual(
            outcome.results[0].chunk_metadata_json,
            '{"source_row_start":3}',
        )

    def test_malformed_metadata_rejects_only_the_affected_row(self) -> None:
        service = KnowledgeRetrievalService(
            repository=_Repository(
                [
                    _row(chunk_id=501, extractor_metadata_json=["not", "an", "object"]),
                    _row(chunk_id=502, extractor_metadata_json={"schema_version": 1}),
                ]
            ),
            embedding_repository=_EmbeddingRepository(),
            embedding_provider=_Provider(),
        )

        outcome = service.retrieve(
            "lumen pathway",
            principal_username="clive",
            scope=KnowledgeScope("PROJECT", "ORAC_CORE"),
        )

        self.assertEqual(outcome.status, "grounded")
        self.assertEqual(outcome.malformed_count, 1)
        self.assertEqual(tuple(result.chunk_id for result in outcome.results), (502,))

    def test_no_evidence_below_lexical_threshold(self) -> None:
        service = KnowledgeRetrievalService(
            repository=_Repository([]),
            embedding_repository=_EmbeddingRepository(),
            embedding_provider=_Provider(),
        )
        outcome = service.retrieve(
            "lumen pathway",
            principal_username="clive",
            scope=KnowledgeScope("PROJECT", "ORAC_CORE"),
        )
        self.assertEqual(outcome.status, "no_evidence")
        self.assertEqual(outcome.reason_codes, ("no_evidence_above_threshold",))

    def test_route_control_and_scope_words_do_not_create_false_evidence(self) -> None:
        service = KnowledgeRetrievalService(
            repository=_Repository([]),
            embedding_repository=_EmbeddingRepository(),
            embedding_provider=_Provider(),
        )

        outcome = service.retrieve(
            (
                "Use the Drop Box knowledge base to explain mitochondrial "
                "ribosome assembly in Antarctic krill."
            ),
            principal_username="clive",
            scope=KnowledgeScope("PLUGIN", "drop_box"),
        )

        self.assertEqual(outcome.status, "no_evidence")
        self.assertEqual(outcome.threshold_count, 0)

    def test_candidate_limit_fails_without_partial_results(self) -> None:
        service = KnowledgeRetrievalService(
            repository=_Repository([_row(chunk_id=index) for index in range(3)]),
            embedding_repository=_EmbeddingRepository(),
            embedding_provider=_Provider(),
        )
        outcome = service.retrieve(
            "lumen",
            principal_username="clive",
            scope=KnowledgeScope("PROJECT", "ORAC_CORE"),
            max_candidate_chunks=2,
        )
        self.assertEqual(outcome.status, "failed")
        self.assertEqual(outcome.reason_codes, ("candidate_limit_exceeded",))

    def test_rejects_embedding_profile_mismatch(self) -> None:
        service = KnowledgeRetrievalService(
            repository=_Repository([_row(embedding_profile_id=18)]),
            embedding_repository=_EmbeddingRepository(),
            embedding_provider=_Provider(),
        )
        with self.assertRaisesRegex(KnowledgeRetrievalError, "profile"):
            service.search(
                "lumen",
                target_scope_type="PROJECT",
                target_scope_key="ORAC_CORE",
                principal_username="clive",
            )

    def test_rejects_dimension_mismatch(self) -> None:
        service = KnowledgeRetrievalService(
            repository=_Repository([_row(embedding_dimensions=3)]),
            embedding_repository=_EmbeddingRepository(),
            embedding_provider=_Provider(),
        )
        with self.assertRaisesRegex(KnowledgeRetrievalError, "dimension"):
            service.search(
                "lumen",
                target_scope_type="PROJECT",
                target_scope_key="ORAC_CORE",
                principal_username="clive",
            )

    def test_semantic_candidates_do_not_transfer_stored_vectors(self) -> None:
        service = KnowledgeRetrievalService(
            repository=_Repository([_row()]),
            embedding_repository=_EmbeddingRepository(),
            embedding_provider=_Provider(),
        )
        results = service.search(
            "lumen",
            target_scope_type="PROJECT",
            target_scope_key="ORAC_CORE",
            principal_username="clive",
        )
        self.assertEqual(len(results), 1)
        self.assertNotIn("embedding_vector", service._repository.rows[0])


if __name__ == "__main__":
    unittest.main()
