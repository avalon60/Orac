"""Tests for native semantic knowledge embedding and retrieval boundaries."""

# Author: Clive Bostock
# Date: 2026-09-07
# Description: Verifies Nomic input guards, transforms, storage, and branch fusion.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from orac_core.embedding_providers import OllamaEmbeddingProvider  # noqa: E402
from orac_core.knowledge.embeddings import (  # noqa: E402
    KnowledgeEmbeddingProfile,
    OllamaKnowledgeEmbeddingProvider,
)
from orac_core.knowledge.retrieval import _rrf_score  # noqa: E402
from orac_core.knowledge.token_accounting import (  # noqa: E402
    EmbeddingInputContextExceeded,
)


class _RecordingProvider:
    """Record bounded calls while returning stable unit vectors."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[1.0] + [0.0] * 767 for _item in texts]

    def embed_text(self, text: str) -> list[float]:
        self.calls.append([text])
        return [1.0] + [0.0] * 767


def _profile() -> KnowledgeEmbeddingProfile:
    """Return the immutable profile used by unit tests."""
    return KnowledgeEmbeddingProfile(
        provider_code="ollama",
        model_id="nomic-embed-text:latest",
        model_digest="a" * 64,
        dimensions=768,
        profile_version="knowledge-v1",
        document_input_prefix="search_document:",
        query_input_prefix="search_query:",
        retrieval_policy_version="knowledge-hybrid-v1",
        semantic_threshold=0.60,
        model_context_tokens=2048,
        context_safety_margin_tokens=64,
        input_estimator_code="utf8_byte_upper_bound_v1",
    )


def test_nomic_modes_and_operational_batches_are_explicit() -> None:
    """Document and query inputs use distinct transforms and bounded calls."""
    raw = _RecordingProvider()
    provider = OllamaKnowledgeEmbeddingProvider(
        provider=raw,  # type: ignore[arg-type]
        profile=_profile(),
        request_batch_size=2,
    )

    vectors = provider.embed_texts(["one", "two", "three", "four", "five"])
    query_vector = provider.embed_query("explain the architecture")

    assert len(vectors) == 5
    assert len(query_vector) == 768
    assert [len(call) for call in raw.calls] == [2, 2, 1, 1]
    assert raw.calls[0][0] == "search_document: one"
    assert raw.calls[-1][0] == "search_query: explain the architecture"


def test_over_limit_document_input_is_rejected_before_provider_call() -> None:
    """Known-over-limit document input fails locally with a stable reason."""
    raw = _RecordingProvider()
    provider = OllamaKnowledgeEmbeddingProvider(
        provider=raw,  # type: ignore[arg-type]
        profile=_profile(),
    )

    try:
        provider.embed_texts(["x" * 3000])
    except EmbeddingInputContextExceeded as exc:
        assert exc.reason_code == "EMBEDDING_INPUT_CONTEXT_EXCEEDED"
        assert exc.input_index == 0
        assert exc.estimated_tokens > exc.usable_limit_tokens
    else:
        raise AssertionError("over-limit input was accepted")
    assert raw.calls == []


class _Response:
    """Minimal successful HTTP response fixture."""

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        """Represent an HTTP success."""

    def json(self):
        """Return the configured JSON payload."""
        return self._payload


@pytest.mark.parametrize(
    "payload,error",
    [
        ({"embeddings": []}, "count"),
        ({"embeddings": [[1.0, 0.0]]}, "dimensions"),
        ({"embeddings": [[float("nan")] + [0.0] * 767]}, "non-finite"),
        (
            {
                "model": "another-model",
                "embeddings": [[1.0] + [0.0] * 767],
            },
            "model identity",
        ),
    ],
)
def test_ollama_response_validation_is_fail_closed(monkeypatch, payload, error) -> None:
    """Count, dimensions, finite values, and returned identity are validated."""
    captured = {}

    def _post(url, *, json, timeout):
        captured.update({"url": url, "json": json, "timeout": timeout})
        return _Response(payload)

    monkeypatch.setattr("orac_core.embedding_providers.requests.post", _post)
    provider = OllamaEmbeddingProvider(
        service_url="http://127.0.0.1:11434",
        model_id="nomic-embed-text:latest",
        dimensions=768,
        truncate=False,
    )

    with pytest.raises(ValueError, match=error):
        provider.embed_texts(["bounded input"])

    assert captured["json"]["truncate"] is False


def test_current_chunk_lineage_is_enforced_by_projection_and_completion() -> None:
    """Historical chunk sets cannot mix with the newest source lineage."""
    projection = (
        PROJECT_ROOT
        / "resources/db/schema/orac_code/view/knowledge_searchable_chunk_content_v.sql"
    ).read_text(encoding="utf-8").lower()
    completion = (
        PROJECT_ROOT
        / "resources/db/schema/orac_code/package_body/knowledge_ingestion_api.sql"
    ).read_text(encoding="utf-8").lower()
    expected = "newer.chunk_set_id > chs.chunk_set_id"
    assert expected in projection
    assert expected in completion


def test_rrf_is_deterministic_and_keeps_independent_branches_useful() -> None:
    """Both candidate paths contribute without making lexical a hard gate."""
    semantic_only = _rrf_score(1, None)
    lexical_only = _rrf_score(None, 1)
    both = _rrf_score(1, 1)

    assert semantic_only > lexical_only > 0
    assert both > semantic_only
    assert both == _rrf_score(1, 1)


def test_native_oracle_storage_and_exact_candidate_sql_are_mandatory() -> None:
    """Production DDL and SQL cannot regress to CLOB/host cosine retrieval."""
    table_sql = (
        PROJECT_ROOT
        / "resources/db/schema/orac_core/table/knowledge_chunk_vector_embeddings.sql"
    ).read_text(encoding="utf-8").lower()
    retrieval_sql = (
        PROJECT_ROOT
        / "resources/db/schema/orac_code/package_body/knowledge_retrieval_api.sql"
    ).read_text(encoding="utf-8").lower()
    native_view = (
        PROJECT_ROOT
        / "resources/db/schema/orac_code/view/knowledge_native_searchable_chunks_v.sql"
    ).read_text(encoding="utf-8").lower()

    assert "embedding_vector          vector(768, float32)" in table_sql
    assert "embedding_vector          clob" not in table_sql
    assert "vector_distance(" in retrieval_sql
    assert "fetch exact first l_semantic_limit rows only" in retrieval_sql
    assert "semantic_score >= l_semantic_threshold" in retrieval_sql
    assert "lexical_score >= 0.25" in retrieval_sql
    assert "candidate_keys as" in retrieval_sql
    assert "embedding_text_sha256 = chunk.chunk_content_sha256" in native_view


def test_hash_provider_is_explicitly_test_only() -> None:
    """The deterministic provider cannot be mistaken for semantic production."""
    provider_sql = (
        PROJECT_ROOT / "src/model/plugin_routing/embeddings.py"
    ).read_text(encoding="utf-8")

    assert "class DeterministicHashTestEmbeddingProvider" in provider_sql
    assert "semantic = False" in provider_sql
    assert "production_allowed = False" in provider_sql


def test_fresh_ingestion_bootstraps_only_an_absent_native_activation() -> None:
    """Fresh databases activate safely while later profile changes stay governed."""
    worker = (PROJECT_ROOT / "src/orac_core/knowledge/worker.py").read_text(
        encoding="utf-8"
    )
    bootstrap = worker.index("if active_profile is None:")
    activation = worker.index("self._embedding_repository.activate_profile(")
    completion = worker.index("self._repository.complete_request(")

    assert bootstrap < activation < completion
    assert "Later profile changes never" in worker


def test_operational_searchability_is_active_profile_driven() -> None:
    """Reporting and retrieval share the native active-profile contract."""
    report = (
        PROJECT_ROOT
        / "resources/db/schema/orac_code/view/knowledge_ingestion_requests_v.sql"
    ).read_text(encoding="utf-8").lower()
    native = (
        PROJECT_ROOT
        / "resources/db/schema/orac_code/view/knowledge_native_searchable_chunks_v.sql"
    ).read_text(encoding="utf-8").lower()
    apex = (PROJECT_ROOT / "plugins/drop_box/apex/f10020.sql").read_text(
        encoding="utf-8"
    ).lower()

    for text in (report, native):
        assert "knowledge_embedding_activations_v" in text
        assert "knowledge_embedding_profiles_v" in text
        assert "knowledge_chunk_vector_embeddings_v" in text
        assert "knowledge_chunk_embeddings_v" not in text
        assert "vector_dimension_count" in text
    assert "model.dimensions = 768" not in native
    assert "active.dimensions" in report
    assert "emb.embedding_text_sha256 = chn.content_sha256" in report
    assert "when req.status_code = 'completed'" in report
    assert "then 'y'" in report
    assert "when core.searchable_yn = ''y''" in apex
    assert "then ''searchable''" in apex


def test_legacy_knowledge_objects_are_purge_only_and_dictionary_guarded() -> None:
    """Install controllers cannot recreate or retain superseded objects."""
    schema = PROJECT_ROOT / "resources/db/schema"
    forbidden = (
        "knowledge_chunk_embeddings",
        "knowledge_searchable_chunks_v",
    )
    definition_roots = (
        schema / "orac_code/package_spec",
        schema / "orac_code/package_body",
        schema / "orac_code/trigger",
    )
    for root in definition_roots:
        for path in root.glob("*.sql"):
            text = path.read_text(encoding="utf-8").lower()
            assert not any(name in text for name in forbidden), path

    legacy_api = (
        schema / "orac_api/view/knowledge_chunk_embeddings_v.sql"
    ).read_text(encoding="utf-8").lower()
    legacy_search = (
        schema / "orac_code/post_install/purge_knowledge_searchable_chunks_v.sql"
    ).read_text(encoding="utf-8").lower()
    table_purge = (
        schema / "orac_core/migration/zz_purge_legacy_knowledge_embeddings.sql"
    ).read_text(encoding="utf-8").lower()
    installed_guard = (
        schema / "orac/validation/legacy_knowledge_embedding_purge.sql"
    ).read_text(encoding="utf-8").lower()
    searchability_guard = (
        schema / "orac/validation/native_knowledge_searchability.sql"
    ).read_text(encoding="utf-8").lower()
    controller = (schema / "orac/schemaController.xml").read_text(
        encoding="utf-8"
    ).lower()

    assert "drop view orac_api.knowledge_chunk_embeddings_v" in legacy_api
    assert "create or replace" not in legacy_api
    assert "drop view orac_code.knowledge_searchable_chunks_v" in legacy_search
    assert "create or replace" not in legacy_search
    assert "drop table orac_core.knowledge_chunk_embeddings" in table_purge
    for dictionary_surface in (
        "dba_objects",
        "dba_dependencies",
        "dba_source",
        "dba_views",
        "dba_synonyms",
        "dba_tab_privs",
    ):
        assert dictionary_surface in installed_guard
    assert "knowledge_searchable_chunk_content_v" in searchability_guard
    assert "knowledge_native_searchable_chunks_v" in searchability_guard
    assert "knowledge_ingestion_requests_v" in searchability_guard
    assert "report.searchable_yn <> 'y'" in searchability_guard
    assert controller.index('path="synonym"') < controller.index('path="validation"')


def test_knowledge_worker_has_no_profileless_completion_or_legacy_write() -> None:
    """Production ingestion can only persist native active-profile vectors."""
    worker = (PROJECT_ROOT / "src/orac_core/knowledge/worker.py").read_text(
        encoding="utf-8"
    ).lower()
    repository = (
        PROJECT_ROOT / "src/orac_core/knowledge/repository.py"
    ).read_text(encoding="utf-8").lower()

    assert "insert_embedding(" not in worker
    assert "hash-test" not in worker
    assert "embedding_profile_id=self._embedding_profile_id" in worker
    assert "legacy_hash_searchable_count" not in repository
    assert "open_search_candidates" not in repository
    assert "open_plugin_search_candidates" not in repository
