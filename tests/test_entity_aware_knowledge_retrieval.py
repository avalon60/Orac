"""Verify entity-aware knowledge selection and absence-response policy."""

# Author: Clive Bostock
# Date: 27-Sep-2026
# Description: Covers literal anchors, emitted excerpts, and safe streaming output.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from orac_core.knowledge.constraints import extract_literal_constraints
from orac_core.knowledge.constraints import literal_match_span
from orac_core.knowledge.embeddings import KnowledgeEmbeddingProfile
from orac_core.knowledge.models import KnowledgeSearchResult
from orac_core.knowledge.response_policy import apply_response_policy
from orac_core.knowledge.response_policy import ResponsePolicyStreamBuffer
from orac_core.knowledge.response_policy import rewrite_unsupported_absence_claims
from orac_core.knowledge.retrieval import KnowledgeRetrievalService
from orac_core.knowledge.retrieval import _select_constraint_aware_results


def _result(
    chunk_id: int,
    text: str,
    *,
    rank: int,
    semantic: float = 0.7,
    document_version_id: int = 10,
    digest: str | None = None,
) -> KnowledgeSearchResult:
    """Build one compact retrieval candidate for deterministic selection tests."""
    return KnowledgeSearchResult(
        ingestion_request_id=1,
        document_id=1,
        document_version_id=document_version_id,
        source_object_id=1,
        source_reference="test.md",
        parent_source_reference=None,
        chunk_id=chunk_id,
        chunk_no=chunk_id,
        lexical_score=0.4,
        semantic_score=semantic,
        target_scope_type="PROJECT",
        target_scope_key="orac",
        embedding_model_identifier="test",
        embedding_dimensions=3,
        chunk_text=text,
        fused_score=1.0 / rank,
        chunk_content_sha256=digest,
        preselection_rank=rank,
    )


def _select(query: str, rows: list[KnowledgeSearchResult], **limits):
    """Run the pure selection stage with production defaults."""
    return _select_constraint_aware_results(
        rows,
        query=query,
        constraints=extract_literal_constraints(query),
        semantic_threshold=0.6,
        max_selected_chunks=limits.get("max_selected_chunks", 6),
        max_chunk_chars=limits.get("max_chunk_chars", 2200),
        max_context_chars=limits.get("max_context_chars", 12000),
    )


class _EmbeddingProvider:
    """Return one valid deterministic query embedding for service tests."""

    production_allowed = True
    profile = KnowledgeEmbeddingProfile(
        provider_code="test",
        model_id="test-embedding",
        model_digest="a" * 64,
        dimensions=3,
        profile_version="test-v1",
        document_input_prefix="document:",
        query_input_prefix="query:",
        retrieval_policy_version="hybrid-v1",
        semantic_threshold=0.6,
        storage_layout_code="ORACLE_VECTOR_3_FLOAT32_V1",
    )
    model_id = profile.model_id

    def embed_query(self, text: str) -> list[float]:
        """Return a fixed vector while accepting the production signature."""
        del text
        return [1.0, 0.0, 0.0]


class _EmbeddingRepository:
    """Expose the active profile fields consumed by retrieval."""

    def active_profile(self) -> dict[str, object]:
        """Return a profile matching the deterministic provider."""
        return {
            "embedding_profile_id": 7,
            "profile_version": "test-v1",
            "model_digest": "a" * 64,
            "dimensions": 3,
            "storage_layout_code": "ORACLE_VECTOR_3_FLOAT32_V1",
            "semantic_threshold": 0.6,
        }


def _service_row(chunk_id: int, text: str, *, semantic: float) -> dict[str, object]:
    """Build one Oracle-shaped row for recovery service tests."""
    return {
        "ingestion_request_id": 1,
        "document_id": 2,
        "document_version_id": 3,
        "source_object_id": 4,
        "source_reference": "test.md",
        "parent_source_reference": None,
        "chunk_id": chunk_id,
        "chunk_no": chunk_id,
        "target_scope_type": "PROJECT",
        "target_scope_key": "TEST",
        "embedding_model_identifier": "test-embedding",
        "embedding_dimensions": 3,
        "embedding_profile_id": 7,
        "semantic_score": semantic,
        "lexical_score": 0.4,
        "semantic_rank": chunk_id,
        "lexical_rank": chunk_id,
        "chunk_text": text,
    }


class _RecoveryRepository:
    """Return separate initial and literal-recovery candidate sets."""

    def __init__(self, initial_rows: list[dict], recovery_rows: list[dict]) -> None:
        """Store deterministic rows and captured calls/outcomes."""
        self.initial_rows = initial_rows
        self.recovery_rows = recovery_rows
        self.calls: list[dict] = []
        self.outcomes: list[dict] = []

    def open_authorised_project_candidates(self, **kwargs):
        """Return recovery rows only when literal constraints are supplied."""
        self.calls.append(kwargs)
        rows = self.recovery_rows if kwargs.get("constraints") else self.initial_rows
        return (
            kwargs["retrieval_id"],
            {"status": "APPROVED", "reason_code": "RETRIEVAL_APPROVED"},
            rows,
        )

    def record_outcome(self, **kwargs) -> None:
        """Capture terminal audit calls without persistence."""
        self.outcomes.append(kwargs)


def test_exact_entity_and_concept_gets_anchor_without_dominating_slots():
    """A suitable late entity result survives while conceptual slots remain."""
    rows = [
        _result(index, f"Conceptual operating-system material {index}.", rank=index)
        for index in range(1, 7)
    ]
    rows.append(
        _result(631, "John Elder describes the AI-OS architecture.", rank=78)
    )

    selected = _select("Tell me about John Elder's AI-OS", rows)

    assert 631 in {item.chunk_id for item in selected}
    assert sum(item.selection_reason == "constraint_anchor" for item in selected) == 1
    assert len(selected) == 6


def test_missing_initial_constraint_runs_one_bounded_authorised_recovery():
    """Recovery reuses the authorised project path and merges one literal match."""
    repository = _RecoveryRepository(
        [_service_row(1, "AI-OS is a local reasoning architecture.", semantic=0.9)],
        [
            _service_row(
                2,
                "John Elder describes the AI-OS architecture.",
                semantic=0.7,
            )
        ],
    )
    service = KnowledgeRetrievalService(
        repository=repository,
        embedding_repository=_EmbeddingRepository(),
        embedding_provider=_EmbeddingProvider(),
    )

    outcome = service.retrieve_authorised_projects(
        "Can you tell me about John Elder's AI-OS?",
        principal_username="clive",
        max_selected_chunks=2,
    )

    assert len(repository.calls) == 2
    assert repository.calls[1]["constraints"] == ("john elder",)
    assert repository.calls[1]["parent_retrieval_id"] == outcome.retrieval_id
    assert repository.calls[1]["lexical_limit"] == 4
    assert {item.chunk_id for item in outcome.results} == {1, 2}
    assert outcome.method == "bounded_hybrid_plus_literal_recovery"
    assert "john elder" in outcome.covered_constraints
    assert repository.outcomes[0]["retrieval_id"] == outcome.recovery_retrieval_id


def test_covered_initial_constraints_do_not_trigger_recovery():
    """The ordinary retrieval remains a single database call when coverage exists."""
    repository = _RecoveryRepository(
        [
            _service_row(
                1,
                "John Elder describes the AI-OS architecture.",
                semantic=0.9,
            )
        ],
        [],
    )
    service = KnowledgeRetrievalService(
        repository=repository,
        embedding_repository=_EmbeddingRepository(),
        embedding_provider=_EmbeddingProvider(),
    )

    outcome = service.retrieve_authorised_projects(
        "Can you tell me about John Elder's AI-OS?",
        principal_username="clive",
        max_selected_chunks=2,
    )

    assert len(repository.calls) == 1
    assert outcome.method == "bounded_hybrid"
    assert outcome.recovery_retrieval_id is None


def test_genuinely_absent_constraint_does_not_create_false_anchor():
    """No literal occurrence means no claimed constraint coverage."""
    selected = _select(
        "Tell me about Jane Example's ZX-81",
        [_result(1, "A general architecture overview.", rank=1)],
    )
    assert selected[0].covered_constraints == ()
    assert selected[0].selection_reason == "relevance"


def test_literal_matching_requires_token_boundaries():
    """Exact constraints must not match longer names or identifiers."""
    constraints = extract_literal_constraints("Tell me about John Elder's AI-OS")
    by_text = {constraint.normalized: constraint for constraint in constraints}

    assert literal_match_span("John Elder wrote it.", by_text["john elder"])
    assert literal_match_span("John Elderson wrote it.", by_text["john elder"]) is None
    assert literal_match_span("The AI-OS design.", by_text["ai-os"])
    assert literal_match_span("The XAI-OSX design.", by_text["ai-os"]) is None


def test_multiple_contextual_constraints_are_preserved():
    """A person and project constraint both survive alongside the concept."""
    query = "What does Jane Smith say about vector databases in Project Atlas?"
    constraints = extract_literal_constraints(query)
    normalized = {constraint.normalized for constraint in constraints}
    rows = [
        _result(1, "Vector databases support dense retrieval.", rank=1),
        _result(
            2,
            "Jane Smith discusses vector databases for Project Atlas.",
            rank=20,
        ),
    ]

    selected = _select(query, rows, max_selected_chunks=2)

    assert {"jane smith", "project atlas"}.issubset(normalized)
    assert 2 in {item.chunk_id for item in selected}
    assert {"jane smith", "project atlas"}.issubset(
        set().union(*(set(item.covered_constraints) for item in selected))
    )


def test_frequent_entity_mentions_do_not_displace_conceptual_evidence():
    """Repeated literal hits consume only one incremental-coverage anchor slot."""
    query = "Tell me about Jane Smith's vector database design"
    rows = [
        _result(
            index,
            f"Jane Smith attended unrelated event {index}.",
            rank=index,
            semantic=0.1,
        )
        for index in range(1, 8)
    ]
    rows.extend(
        [
            _result(20, "Vector database indexing uses graph traversal.", rank=8),
            _result(21, "The design balances recall and latency.", rank=9),
            _result(
                22,
                "Jane Smith designed the vector database architecture.",
                rank=20,
            ),
        ]
    )

    selected = _select(query, rows, max_selected_chunks=4)

    assert sum(item.selection_reason == "constraint_anchor" for item in selected) == 1
    assert {20, 21}.intersection(item.chunk_id for item in selected)


def test_late_match_is_present_in_emitted_anchor_excerpt():
    """Coverage is based on the match-centred emitted text, not the full chunk."""
    text = "prefix " * 800 + "John Elder built AI-OS for local reasoning."
    selected = _select(
        "Explain John Elder's AI-OS",
        [_result(1, text, rank=1)],
        max_selected_chunks=1,
        max_chunk_chars=160,
        max_context_chars=160,
    )
    assert "John Elder" in selected[0].emitted_excerpt
    assert selected[0].emitted_offset > 0
    assert set(selected[0].covered_constraints) == {"john elder", "ai-os"}


def test_duplicate_anchors_and_constraint_budget_remain_bounded():
    """Content identity deduplication and the half-slot anchor cap both hold."""
    query = 'Compare "Alpha One", "Beta Two", "Gamma Three", and "Delta Four"'
    rows = [
        _result(1, "Alpha One Beta Two", rank=1, digest="same"),
        _result(2, "Alpha One Beta Two", rank=2, digest="same"),
        _result(3, "Gamma Three", rank=3),
        _result(4, "Delta Four", rank=4),
    ]
    selected = _select(query, rows, max_selected_chunks=3)
    assert len(selected) <= 3
    assert sum(item.selection_reason == "constraint_anchor" for item in selected) <= 1
    assert len(
        {
            (item.document_version_id, item.chunk_content_sha256 or str(item.chunk_id))
            for item in selected
        }
    ) == len(selected)


def test_no_constraint_query_preserves_existing_order():
    """Ordinary conceptual retrieval is unchanged when no literal is extracted."""
    rows = [_result(1, "first conceptual passage", rank=1), _result(2, "second", rank=2)]
    selected = _select("how does this work", rows, max_selected_chunks=2)
    assert [item.chunk_id for item in selected] == [1, 2]


def test_response_policy_preserves_scoped_uncertainty_and_supported_negative():
    """Only categorical collection-level absence is rewritten."""
    assert rewrite_unsupported_absence_claims(
        "The document does not mention that detail."
    ) == "The excerpts retrieved so far do not establish that detail."
    assert rewrite_unsupported_absence_claims(
        "The retrieved excerpts do not mention that detail."
    ) == "The retrieved excerpts do not mention that detail."
    assert rewrite_unsupported_absence_claims(
        "The document states that the feature is not supported."
    ) == "The document states that the feature is not supported."


def test_response_policy_rewrites_the_observed_failure_shapes():
    """First-person and pronoun-based corpus absence claims are bounded."""
    response = (
        "I don't have any information about John Elder in my current knowledge "
        "base or the provided reference documents. "
        "The local evidence references AI-OS from a book, but it does not "
        "attribute the framework to John Elder or mention him by name."
    )

    rewritten = rewrite_unsupported_absence_claims(response)

    assert "don't have any information" not in rewritten
    assert "does not attribute" not in rewritten
    assert rewritten.count(
        "The excerpts retrieved so far do not establish that detail."
    ) == 2


def test_response_policy_rewrites_live_reference_material_wording():
    """Quoted sentence endings and modified collection nouns remain guarded."""
    response = (
        'The provided reference material does not contain any mention of '
        '"Zephyr Quill." The excerpts are from a document titled '
        '*AI-OS-Book.docx*, but it does not attribute these views to Zephyr Quill.'
    )

    result = apply_response_policy(response)

    assert result.rewrite_count == 2
    assert "does not contain" not in result.text
    assert "does not attribute" not in result.text


def test_response_policy_rewrites_live_indirect_absence_wording():
    """Long collection predicates and categorical no-record claims are bounded."""
    response = (
        "The provided reference material discusses AI-OS, but does not mention "
        "Zephyr Quill. Based on the available evidence, there is no record of "
        "what Zephyr Quill says about AI-OS."
    )

    result = apply_response_policy(response)

    assert result.rewrite_count == 2
    assert "does not mention" not in result.text
    assert "there is no record" not in result.text


def test_stream_policy_handles_arbitrary_boundaries_flush_and_cancel():
    """Unsafe raw text is withheld until a complete sentence can be rewritten."""
    buffer = ResponsePolicyStreamBuffer()
    assert buffer.add_delta("The corpus does not") == ()
    assert buffer.add_delta(" mention it. Safe follow-up.") == (
        "The excerpts retrieved so far do not establish that detail.",
        " Safe follow-up.",
    )
    assert buffer.flush() == ""

    trailing = ResponsePolicyStreamBuffer()
    assert trailing.add_delta("The source does not contain it") == ()
    assert trailing.flush() == "The excerpts retrieved so far do not establish that detail."

    cancelled = ResponsePolicyStreamBuffer()
    assert cancelled.add_delta("The files do not mention") == ()
    cancelled.discard()
    assert cancelled.flush() == ""


def test_disabled_stream_policy_preserves_immediate_non_rag_deltas():
    """Ordinary streams retain their pre-policy latency and exact delta shape."""
    buffer = ResponsePolicyStreamBuffer(enabled=False)
    assert buffer.add_delta("The source does not") == ("The source does not",)
    assert buffer.add_delta(" mention it.") == (" mention it.",)
    assert buffer.flush() == ""
    assert buffer.rewrite_count == 0
