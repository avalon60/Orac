"""Scope-bound lexical retrieval over current Core knowledge chunks."""

# Author: Clive Bostock
# Date: 07-Sep-2026
# Description: Ranks authorised searchable chunks with hybrid relevance and bounded context.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from decimal import Decimal
import json
import re
import time
from typing import Any
import uuid

from model.plugin_routing.embeddings import EmbeddingProvider

from .models import KnowledgeRetrievalOutcome, KnowledgeSearchResult
from .constraints import LiteralConstraint
from .constraints import extract_literal_constraints
from .constraints import general_lexical_terms
from .constraints import literal_match_span
from .constraints import matched_literal_constraints
from .repository import KnowledgeRetrievalRepository
from .repository import KnowledgeEmbeddingRepository
from .scope import KnowledgeScope, KnowledgeScopeConfigurationError

_LEXICAL_TOKEN = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", re.IGNORECASE)
_DOTTED_LEADER = re.compile(r"\.{5,}\s*\d+\s*$")
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "about",
        "are",
        "base",
        "consult",
        "can",
        "do",
        "does",
        "explain",
        "for",
        "how",
        "i",
        "in",
        "is",
        "it",
        "knowledge",
        "me",
        "of",
        "on",
        "query",
        "search",
        "s",
        "source",
        "tell",
        "the",
        "to",
        "use",
        "using",
        "what",
        "you",
    }
)


class KnowledgeRetrievalError(RuntimeError):
    """Raised when scoped knowledge retrieval cannot be used safely."""


class KnowledgeRetrievalService:
    """Search current Core knowledge chunks within one authorised scope."""

    def __init__(
        self,
        *,
        repository: KnowledgeRetrievalRepository | None = None,
        embedding_repository: KnowledgeEmbeddingRepository | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        """Initialise retrieval with injectable persistence and embeddings."""
        self._repository = repository or KnowledgeRetrievalRepository()
        self._embedding_repository = (
            embedding_repository or KnowledgeEmbeddingRepository()
        )
        if embedding_provider is None:
            raise ValueError(
                "Production knowledge retrieval requires a semantic embedding provider."
            )
        self._embedding_provider = embedding_provider

    def search(
        self,
        query: str,
        *,
        target_scope_type: str,
        target_scope_key: str,
        principal_username: str,
        top_k: int = 5,
    ) -> list[KnowledgeSearchResult]:
        """Compatibility wrapper returning matches for one canonical scope."""
        try:
            scope = KnowledgeScope(target_scope_type, target_scope_key)
        except KnowledgeScopeConfigurationError as exc:
            raise KnowledgeRetrievalError(
                "Knowledge retrieval requires a canonical PROJECT or PLUGIN scope."
            ) from exc
        outcome = self.retrieve(
            query,
            principal_username=principal_username,
            scope=scope,
            max_selected_chunks=top_k,
            min_lexical_score=0.25,
        )
        if outcome.status == "failed":
            raise KnowledgeRetrievalError(", ".join(outcome.reason_codes))
        return list(outcome.results)

    def retrieve(
        self,
        query: str,
        *,
        principal_username: str,
        scope: KnowledgeScope,
        max_candidate_chunks: int = 1000,
        max_selected_chunks: int = 6,
        min_lexical_score: float = 0.25,
        max_chunk_chars: int = 2200,
        max_context_chars: int = 12000,
    ) -> KnowledgeRetrievalOutcome:
        """Retrieve bounded lexical evidence from one canonical scope."""
        return self._retrieve(
            query,
            principal_username=principal_username,
            scope=scope,
            max_candidate_chunks=max_candidate_chunks,
            max_selected_chunks=max_selected_chunks,
            min_lexical_score=min_lexical_score,
            max_chunk_chars=max_chunk_chars,
            max_context_chars=max_context_chars,
            plugin_id=None,
            correlation_id=None,
            automatic_projects=False,
            timeout_seconds=None,
        )

    def retrieve_authorised_projects(
        self,
        query: str,
        *,
        principal_username: str,
        lexical_query: str | None = None,
        max_candidate_chunks: int = 100,
        max_selected_chunks: int = 6,
        min_lexical_score: float = 0.25,
        max_chunk_chars: int = 2200,
        max_context_chars: int = 12000,
        timeout_seconds: float = 10.0,
    ) -> KnowledgeRetrievalOutcome:
        """Search content across all projects currently authorised for a user."""
        if timeout_seconds <= 0:
            raise ValueError("Knowledge retrieval timeout must be positive.")
        return self._retrieve(
            query,
            principal_username=principal_username,
            scope=None,
            max_candidate_chunks=max_candidate_chunks,
            max_selected_chunks=max_selected_chunks,
            min_lexical_score=min_lexical_score,
            max_chunk_chars=max_chunk_chars,
            max_context_chars=max_context_chars,
            plugin_id=None,
            correlation_id=None,
            automatic_projects=True,
            timeout_seconds=timeout_seconds,
            lexical_query=lexical_query,
        )

    def retrieve_for_plugin(
        self,
        query: str,
        *,
        principal_username: str,
        plugin_id: str,
        max_selected_chunks: int = 5,
        correlation_id: str | None = None,
    ) -> KnowledgeRetrievalOutcome:
        """Retrieve from the plugin scope derived by the trusted host bridge."""
        try:
            scope = KnowledgeScope("PLUGIN", plugin_id)
        except KnowledgeScopeConfigurationError as exc:
            raise KnowledgeRetrievalError("plugin_scope_invalid") from exc
        return self._retrieve(
            query,
            principal_username=principal_username,
            scope=scope,
            max_candidate_chunks=1000,
            max_selected_chunks=max_selected_chunks,
            min_lexical_score=0.25,
            max_chunk_chars=2200,
            max_context_chars=12000,
            plugin_id=plugin_id,
            correlation_id=correlation_id,
            automatic_projects=False,
            timeout_seconds=None,
        )

    def _retrieve(
        self,
        query: str,
        *,
        principal_username: str,
        scope: KnowledgeScope | None,
        max_candidate_chunks: int,
        max_selected_chunks: int,
        min_lexical_score: float,
        max_chunk_chars: int,
        max_context_chars: int,
        plugin_id: str | None,
        correlation_id: str | None,
        automatic_projects: bool,
        timeout_seconds: float | None,
        lexical_query: str | None = None,
    ) -> KnowledgeRetrievalOutcome:
        """Run the shared authorised retrieval and ranking implementation."""
        if not query.strip():
            raise ValueError("query is required")
        if max_candidate_chunks <= 0 or max_selected_chunks <= 0:
            raise ValueError("Knowledge retrieval limits must be positive.")
        if not 0.0 <= min_lexical_score <= 1.0:
            raise ValueError("min_lexical_score must be between 0 and 1.")

        active_profile = self._embedding_repository.active_profile()
        if active_profile is None:
            raise KnowledgeRetrievalError("knowledge_embedding_profile_inactive")
        profile = getattr(self._embedding_provider, "profile", None)
        if profile is None or not getattr(
            self._embedding_provider,
            "production_allowed",
            False,
        ):
            raise KnowledgeRetrievalError("knowledge_embedding_provider_nonsemantic")
        if (
            str(active_profile.get("profile_version") or "") != profile.profile_version
            or str(active_profile.get("model_digest") or "").lower()
            != profile.model_digest.lower()
            or int(active_profile.get("dimensions") or 0) != profile.dimensions
            or str(active_profile.get("storage_layout_code") or "")
            != profile.storage_layout_code
        ):
            raise KnowledgeRetrievalError("knowledge_embedding_profile_mismatch")
        try:
            embed_query = getattr(self._embedding_provider, "embed_query")
            query_vector = embed_query(query)
        except Exception as exc:
            raise KnowledgeRetrievalError("query_embedding_failed") from exc
        dimensions = len(query_vector)
        if dimensions != int(active_profile["dimensions"]):
            raise KnowledgeRetrievalError("query_embedding_dimensions_invalid")
        lexical_tokens = _lexical_query_tokens(lexical_query or query, scope)
        lexical_phrase = " ".join(lexical_tokens)
        constraints = extract_literal_constraints(lexical_query or query)
        retrieval_deadline = time.monotonic() + float(timeout_seconds or 10.0)
        requested_retrieval_id = str(uuid.uuid4())
        if automatic_projects:
            retrieval_id, resolution, rows = (
                self._repository.open_authorised_project_candidates(
                    principal_username=principal_username,
                    embedding_profile_id=int(active_profile["embedding_profile_id"]),
                    query_vector=query_vector,
                    lexical_tokens=lexical_tokens,
                    lexical_phrase=lexical_phrase,
                    semantic_limit=50,
                    lexical_limit=50,
                    retrieval_id=requested_retrieval_id,
                    min_lexical_score=min_lexical_score,
                    timeout_seconds=float(timeout_seconds or 10.0),
                )
            )
        elif plugin_id is None:
            if scope is None:
                raise KnowledgeRetrievalError("knowledge_scope_required")
            retrieval_id, resolution, rows = (
                self._repository.open_hybrid_search_candidates(
                    principal_username=principal_username,
                    target_scope_type=scope.scope_type,
                    target_scope_key=scope.scope_key,
                    embedding_profile_id=int(active_profile["embedding_profile_id"]),
                    query_vector=query_vector,
                    lexical_tokens=lexical_tokens,
                    lexical_phrase=lexical_phrase,
                    semantic_limit=50,
                    lexical_limit=50,
                    retrieval_id=requested_retrieval_id,
                    min_lexical_score=min_lexical_score,
                    timeout_seconds=max(0.001, retrieval_deadline - time.monotonic()),
                )
            )
        else:
            if scope is None:
                raise KnowledgeRetrievalError("plugin_scope_invalid")
            retrieval_id, resolution, rows = (
                self._repository.open_plugin_hybrid_candidates(
                    principal_username=principal_username,
                    plugin_id=plugin_id,
                    embedding_profile_id=int(active_profile["embedding_profile_id"]),
                    query_vector=query_vector,
                    lexical_tokens=lexical_tokens,
                    lexical_phrase=lexical_phrase,
                    semantic_limit=50,
                    lexical_limit=50,
                    retrieval_id=requested_retrieval_id,
                    correlation_id=correlation_id,
                    min_lexical_score=min_lexical_score,
                    timeout_seconds=max(0.001, retrieval_deadline - time.monotonic()),
                )
            )
        if retrieval_id != requested_retrieval_id:
            raise KnowledgeRetrievalError("retrieval_contract_invalid")
        if resolution.get("status") != "APPROVED":
            return KnowledgeRetrievalOutcome(
                status="failed",
                reason_codes=(
                    str(resolution.get("reason_code") or "RETRIEVAL_NOT_AUTHORISED"),
                ),
                scope=scope,
                embedding_model_identifier=self._embedding_provider.model_id,
                retrieval_id=retrieval_id,
            )
        bounded_candidate_limit = min(max_candidate_chunks, 100)
        if len(rows) > bounded_candidate_limit:
            self._repository.record_outcome(
                retrieval_id=retrieval_id,
                outcome_code="FAILED",
                reason_code="RETRIEVAL_LIMIT_EXCEEDED",
                chunk_count=len(rows),
            )
            return KnowledgeRetrievalOutcome(
                status="failed",
                reason_codes=("candidate_limit_exceeded",),
                scope=scope,
                considered_count=len(rows),
                embedding_model_identifier=self._embedding_provider.model_id,
                retrieval_id=retrieval_id,
            )

        recovery_retrieval_id: str | None = None
        recovery_candidate_count = 0
        recovery_duration_ms: int | None = None
        initial_order = sorted(
            rows,
            key=lambda row: (
                _is_navigation_heavy(str(row.get("chunk_text") or "")),
                -_rrf_score(
                    _optional_int(row.get("semantic_rank")),
                    _optional_int(row.get("lexical_rank")),
                ),
                int(row.get("chunk_id") or 0),
            ),
        )
        lead_document_version_id = (
            int(initial_order[0].get("document_version_id") or 0)
            if initial_order
            else 0
        )
        recovery_topical_terms = general_lexical_terms(lexical_query or query).difference(
            term
            for item in constraints
            if item.kind in {"possessive_name", "multiword_name"}
            for term in general_lexical_terms(item.normalized)
        )
        recovery_constraints = tuple(
            constraint.normalized
            for constraint in constraints
            if constraint.high_confidence
            and not any(
                literal_match_span(str(row.get("chunk_text") or ""), constraint)
                is not None
                and (
                    float(row.get("semantic_score") or 0.0)
                    >= float(active_profile.get("semantic_threshold") or 0.0)
                    or (
                        int(row.get("document_version_id") or 0)
                        == lead_document_version_id
                        and bool(
                            recovery_topical_terms.intersection(
                                general_lexical_terms(
                                    str(row.get("chunk_text") or "")
                                )
                            )
                        )
                    )
                )
                for row in rows
            )
        )
        if recovery_constraints:
            recovery_retrieval_id = str(uuid.uuid4())
            recovery_started_at = time.monotonic()
            recovery_rows: list[dict[str, Any]] = []
            recovery_reason = "LITERAL_RECOVERY_EMPTY"
            try:
                recovery_limit = min(16, max_selected_chunks * 2)
                if automatic_projects:
                    _, recovery_resolution, recovery_rows = (
                        self._repository.open_authorised_project_candidates(
                            principal_username=principal_username,
                            embedding_profile_id=int(
                                active_profile["embedding_profile_id"]
                            ),
                            query_vector=query_vector,
                            lexical_tokens=lexical_tokens,
                            lexical_phrase=lexical_phrase,
                            semantic_limit=1,
                            lexical_limit=recovery_limit,
                            retrieval_id=recovery_retrieval_id,
                            constraints=recovery_constraints,
                            min_lexical_score=min_lexical_score,
                            parent_retrieval_id=retrieval_id,
                            timeout_seconds=max(
                                0.001, retrieval_deadline - time.monotonic()
                            ),
                        )
                    )
                elif plugin_id is None:
                    assert scope is not None
                    _, recovery_resolution, recovery_rows = (
                        self._repository.open_hybrid_search_candidates(
                            principal_username=principal_username,
                            target_scope_type=scope.scope_type,
                            target_scope_key=scope.scope_key,
                            embedding_profile_id=int(
                                active_profile["embedding_profile_id"]
                            ),
                            query_vector=query_vector,
                            lexical_tokens=lexical_tokens,
                            lexical_phrase=lexical_phrase,
                            semantic_limit=1,
                            lexical_limit=recovery_limit,
                            retrieval_id=recovery_retrieval_id,
                            constraints=recovery_constraints,
                            min_lexical_score=min_lexical_score,
                            parent_retrieval_id=retrieval_id,
                            timeout_seconds=max(
                                0.001, retrieval_deadline - time.monotonic()
                            ),
                        )
                    )
                else:
                    _, recovery_resolution, recovery_rows = (
                        self._repository.open_plugin_hybrid_candidates(
                            principal_username=principal_username,
                            plugin_id=plugin_id,
                            embedding_profile_id=int(
                                active_profile["embedding_profile_id"]
                            ),
                            query_vector=query_vector,
                            lexical_tokens=lexical_tokens,
                            lexical_phrase=lexical_phrase,
                            semantic_limit=1,
                            lexical_limit=recovery_limit,
                            retrieval_id=recovery_retrieval_id,
                            correlation_id=correlation_id,
                            constraints=recovery_constraints,
                            min_lexical_score=min_lexical_score,
                            parent_retrieval_id=retrieval_id,
                            timeout_seconds=max(
                                0.001, retrieval_deadline - time.monotonic()
                            ),
                        )
                    )
                if recovery_resolution.get("status") == "APPROVED":
                    recovery_rows = recovery_rows[:recovery_limit]
                    recovery_candidate_count = len(recovery_rows)
                    recovery_reason = (
                        "LITERAL_RECOVERY_RETURNED"
                        if recovery_rows
                        else "LITERAL_RECOVERY_EMPTY"
                    )
                    initial_ids = {int(row["chunk_id"]) for row in rows}
                    rows.extend(
                        row
                        for row in recovery_rows
                        if int(row["chunk_id"]) not in initial_ids
                    )
                else:
                    recovery_reason = "LITERAL_RECOVERY_REJECTED"
            except Exception as exc:
                recovery_reason = (
                    "LITERAL_RECOVERY_TIMEOUT"
                    if isinstance(exc, TimeoutError)
                    or "timeout" in type(exc).__name__.casefold()
                    else "LITERAL_RECOVERY_FAILED"
                )
            finally:
                recovery_duration_ms = max(
                    0, int((time.monotonic() - recovery_started_at) * 1000)
                )
                try:
                    self._repository.record_outcome(
                        retrieval_id=recovery_retrieval_id,
                        outcome_code="COMPLETED",
                        reason_code=recovery_reason,
                        chunk_count=recovery_candidate_count,
                        duration_ms=recovery_duration_ms,
                        selected_chunk_ids=(),
                    )
                except Exception:
                    pass

        scored: list[KnowledgeSearchResult] = []
        malformed_count = 0
        failure_codes: list[str] = []
        for row in rows:
            try:
                self._assert_compatible_row(
                    row,
                    dimensions,
                    int(active_profile["embedding_profile_id"]),
                )
                row_scope = KnowledgeScope(
                    str(row.get("target_scope_type") or ""),
                    str(row.get("target_scope_key") or ""),
                )
                if automatic_projects and row_scope.scope_type != "PROJECT":
                    raise KnowledgeRetrievalError("scope_mismatch")
                if not automatic_projects and row_scope != scope:
                    raise KnowledgeRetrievalError("scope_mismatch")
                semantic_score = float(row.get("semantic_score") or 0.0)
                lexical_score = float(row.get("lexical_score") or 0.0)
                semantic_rank = _optional_int(row.get("semantic_rank"))
                lexical_rank = _optional_int(row.get("lexical_rank"))
                fused_score = _rrf_score(semantic_rank, lexical_rank)
                extractor_metadata_json = _optional_json_object_text(
                    row.get("extractor_metadata_json"),
                    field_name="extractor_metadata_json",
                )
                chunk_metadata_json = _optional_json_object_text(
                    row.get("chunk_metadata_json"),
                    field_name="chunk_metadata_json",
                )
            except (KeyError, TypeError, ValueError, KnowledgeRetrievalError) as exc:
                malformed_count += 1
                failure_codes.append(_retrieval_failure_code(exc))
                continue
            scored.append(
                KnowledgeSearchResult(
                    ingestion_request_id=int(row["ingestion_request_id"]),
                    document_id=int(row["document_id"]),
                    document_version_id=int(row["document_version_id"]),
                    source_object_id=int(row["source_object_id"]),
                    source_reference=str(row["source_reference"]),
                    parent_source_reference=row.get("parent_source_reference"),
                    chunk_id=int(row["chunk_id"]),
                    chunk_no=int(row["chunk_no"]),
                    lexical_score=lexical_score,
                    semantic_score=semantic_score,
                    target_scope_type=str(row["target_scope_type"]),
                    target_scope_key=str(row["target_scope_key"]),
                    embedding_model_identifier=str(row["embedding_model_identifier"]),
                    embedding_dimensions=int(row["embedding_dimensions"]),
                    chunk_text=str(row["chunk_text"]),
                    fused_score=fused_score,
                    source_type=str(row.get("source_type") or ""),
                    document_title=_optional_string(row.get("document_title")),
                    original_filename=_optional_string(row.get("original_filename")),
                    span_start=_optional_int(row.get("span_start")),
                    span_end=_optional_int(row.get("span_end")),
                    chunk_content_sha256=_optional_string(
                        row.get("chunk_content_sha256")
                    ),
                    embedding_provider_code=_optional_string(
                        row.get("embedding_provider_code")
                    ),
                    embedding_model_revision=_optional_string(
                        row.get("embedding_model_revision")
                    ),
                    processing_profile_code=_optional_string(
                        row.get("processing_profile_code")
                    ),
                    classification_tags=_classification_tags(
                        row.get("classification_tags_json")
                    ),
                    source_format_code=_optional_string(row.get("source_format_code")),
                    normalised_text_sha256=_optional_string(
                        row.get("normalised_text_sha256")
                    ),
                    output_mime_type=_optional_string(row.get("output_mime_type")),
                    extractor_code=_optional_string(row.get("extractor_code")),
                    extractor_version=_optional_string(row.get("extractor_version")),
                    extractor_metadata_json=extractor_metadata_json,
                    chunk_metadata_json=chunk_metadata_json,
                    source_artefact_id=_optional_int(row.get("source_artefact_id")),
                    source_artefact_role_code=_optional_string(
                        row.get("source_artefact_role_code")
                    ),
                    source_artefact_logical_name=_optional_string(
                        row.get("source_artefact_logical_name")
                    ),
                    source_artefact_media_type=_optional_string(
                        row.get("source_artefact_media_type")
                    ),
                    source_artefact_sha256=_optional_string(
                        row.get("source_artefact_sha256")
                    ),
                    source_artefact_ordinal=_optional_int(
                        row.get("source_artefact_ordinal")
                    ),
                    source_sheet_name=_optional_string(row.get("source_sheet_name")),
                    source_table_name=_optional_string(row.get("source_table_name")),
                    source_member_cell_range=_optional_string(
                        row.get("source_member_cell_range")
                    ),
                    source_header_rows_json=_optional_string(
                        row.get("source_header_rows_json")
                    ),
                    source_hidden_sheet=_optional_string(
                        row.get("source_hidden_sheet")
                    ),
                    source_row_start=_optional_int(row.get("source_row_start")),
                    source_row_end=_optional_int(row.get("source_row_end")),
                    source_chunk_cell_range=_optional_string(
                        row.get("source_chunk_cell_range")
                    ),
                    extraction_id=_optional_int(row.get("extraction_id")),
                    chunk_set_id=_optional_int(row.get("chunk_set_id")),
                    semantic_rank=semantic_rank,
                    lexical_rank=lexical_rank,
                    navigation=_navigation_classification(str(row["chunk_text"])),
                    literal_constraints=tuple(
                        constraint.normalized for constraint in constraints
                    ),
                    covered_constraints=matched_literal_constraints(
                        str(row["chunk_text"]), constraints
                    ),
                )
            )

        ordered = sorted(
            scored,
            key=lambda result: (
                _is_navigation_heavy(result.chunk_text),
                -result.fused_score,
                -(result.semantic_score or -1.0),
                -result.lexical_score,
                result.chunk_id,
            ),
        )
        ordered = [
            replace(result, preselection_rank=rank)
            for rank, result in enumerate(ordered, start=1)
        ]
        selected = _select_constraint_aware_results(
            ordered,
            query=lexical_query or query,
            constraints=constraints,
            semantic_threshold=float(active_profile.get("semantic_threshold") or 0.0),
            max_selected_chunks=max_selected_chunks,
            max_chunk_chars=max_chunk_chars,
            max_context_chars=max_context_chars,
        )
        if not selected:
            all_rows_malformed = bool(rows and malformed_count == len(rows))
            reason = (
                failure_codes[0]
                if all_rows_malformed and len(set(failure_codes)) == 1
                else (
                    "malformed_retrieval_rows"
                    if all_rows_malformed
                    else "no_evidence_above_threshold"
                )
            )
            self._repository.record_outcome(
                retrieval_id=retrieval_id,
                outcome_code="COMPLETED",
                reason_code="RETRIEVAL_CHUNKS_RETURNED",
                returned_byte_size=0,
                chunk_count=0,
                selected_chunk_ids=(),
            )
            return KnowledgeRetrievalOutcome(
                status="failed" if all_rows_malformed else "no_evidence",
                reason_codes=(reason,),
                scope=scope,
                considered_count=len(rows),
                threshold_count=len(ordered),
                malformed_count=malformed_count,
                embedding_model_identifier=self._embedding_provider.model_id,
                retrieval_id=retrieval_id,
                literal_constraints=tuple(item.normalized for item in constraints),
                uncovered_constraints=tuple(item.normalized for item in constraints),
                recovery_retrieval_id=recovery_retrieval_id,
                recovery_candidate_count=recovery_candidate_count,
                recovery_duration_ms=recovery_duration_ms,
            )
        covered_constraints = tuple(
            constraint.normalized
            for constraint in constraints
            if any(
                constraint.normalized in result.covered_constraints
                for result in selected
            )
        )
        uncovered_constraints = tuple(
            constraint.normalized
            for constraint in constraints
            if constraint.normalized not in covered_constraints
        )
        self._repository.record_outcome(
            retrieval_id=retrieval_id,
            outcome_code="COMPLETED",
            reason_code="RETRIEVAL_CHUNKS_RETURNED",
            returned_byte_size=sum(
                len(item.chunk_text.encode("utf-8")) for item in selected
            ),
            chunk_count=len(selected),
            selected_chunk_ids=tuple(item.chunk_id for item in selected),
        )
        return KnowledgeRetrievalOutcome(
            status="grounded",
            reason_codes=("local_evidence_selected",),
            scope=scope,
            considered_count=len(rows),
            threshold_count=len(ordered),
            malformed_count=malformed_count,
            embedding_model_identifier=self._embedding_provider.model_id,
            results=tuple(selected),
            retrieval_id=retrieval_id,
            literal_constraints=tuple(item.normalized for item in constraints),
            covered_constraints=covered_constraints,
            uncovered_constraints=uncovered_constraints,
            method=(
                "bounded_hybrid_plus_literal_recovery"
                if recovery_retrieval_id is not None
                else "bounded_hybrid"
            ),
            recovery_retrieval_id=recovery_retrieval_id,
            recovery_candidate_count=recovery_candidate_count,
            recovery_duration_ms=recovery_duration_ms,
            diagnostics={
                "selected_chunk_ids": tuple(item.chunk_id for item in selected),
                "selected_ordinals": tuple(
                    item.final_rank or 0 for item in selected
                ),
            },
        )

    def _assert_compatible_row(
        self,
        row: dict[str, Any],
        dimensions: int,
        embedding_profile_id: int,
    ) -> None:
        """Reject rows returned from another active profile or dimension."""
        row_dimensions = int(row.get("embedding_dimensions") or 0)
        row_profile_id = int(row.get("embedding_profile_id") or 0)
        if row_profile_id != embedding_profile_id:
            raise KnowledgeRetrievalError(
                "Oracle returned a candidate from another embedding profile."
            )
        if row_dimensions != dimensions:
            raise KnowledgeRetrievalError(
                f"Stored vector dimension {row_dimensions} does not match query "
                f"dimension {dimensions}."
            )


def _lexical_query_tokens(
    query: str,
    scope: KnowledgeScope | None,
) -> list[str]:
    """Return the bounded lexical descriptor sent to the Oracle branch."""
    excluded = _scope_tokens(scope) if scope is not None else frozenset()
    tokens: list[str] = []
    seen: set[str] = set()
    for raw_token in _LEXICAL_TOKEN.findall(query):
        token = raw_token.casefold()
        if token in _STOP_WORDS or token in excluded or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
        if len(tokens) == 64:
            break
    return tokens


def _rrf_score(
    semantic_rank: int | None,
    lexical_rank: int | None,
) -> float:
    """Fuse independent Oracle branch ranks deterministically on the host."""
    semantic = 0.65 / (60 + semantic_rank) if semantic_rank else 0.0
    lexical = 0.35 / (60 + lexical_rank) if lexical_rank else 0.0
    return 61.0 * (semantic + lexical)


def _scope_tokens(scope: KnowledgeScope) -> frozenset[str]:
    """Return canonical scope words that must not count as topical evidence."""
    scope_words = re.split(r"[^a-z0-9]+", scope.scope_key.casefold())
    return frozenset(word for word in scope_words if word)


def _select_bounded_results(
    results: list[KnowledgeSearchResult],
    *,
    max_selected_chunks: int,
    max_chunk_chars: int,
    max_context_chars: int,
) -> list[KnowledgeSearchResult]:
    """Deduplicate chunks and enforce per-chunk and total evidence budgets."""
    selected: list[KnowledgeSearchResult] = []
    seen: set[tuple[int, str]] = set()
    used_chars = 0
    for result in results:
        identity = (
            result.document_version_id,
            result.chunk_content_sha256 or str(result.chunk_id),
        )
        if identity in seen:
            continue
        chunk_chars = min(len(result.chunk_text), max_chunk_chars)
        if used_chars + chunk_chars > max_context_chars:
            continue
        seen.add(identity)
        selected.append(result)
        used_chars += chunk_chars
        if len(selected) >= max_selected_chunks:
            break
    return selected


def _select_constraint_aware_results(
    results: list[KnowledgeSearchResult],
    *,
    query: str,
    constraints: tuple[LiteralConstraint, ...],
    semantic_threshold: float,
    max_selected_chunks: int,
    max_chunk_chars: int,
    max_context_chars: int,
) -> list[KnowledgeSearchResult]:
    """Select relevance slots plus bounded literal anchors deterministically."""
    if not constraints:
        promoted = _promote_continuation_neighbors(
            results,
            selection_window=max_selected_chunks,
        )
        selected = _select_bounded_results(
            promoted,
            max_selected_chunks=max_selected_chunks,
            max_chunk_chars=max_chunk_chars,
            max_context_chars=max_context_chars,
        )
        return [
            replace(
                item,
                final_rank=rank,
                emitted_excerpt=item.chunk_text[:max_chunk_chars],
                emitted_offset=0,
            )
            for rank, item in enumerate(selected, start=1)
        ]

    lead = next((item for item in results if not _is_navigation_heavy(item.chunk_text)), None)
    lead_document_id = lead.document_version_id if lead is not None else None
    topical_terms = general_lexical_terms(query).difference(
        term
        for constraint in constraints
        if constraint.kind in {"possessive_name", "multiword_name"}
        for term in general_lexical_terms(constraint.normalized)
    )
    anchor_candidates: list[KnowledgeSearchResult] = []
    for result in results:
        covered = matched_literal_constraints(result.chunk_text, constraints)
        if not covered:
            continue
        chunk_terms = general_lexical_terms(result.chunk_text)
        semantic_suitable = (
            result.semantic_score is not None
            and result.semantic_score >= semantic_threshold
        )
        same_document_topical = (
            lead_document_id is not None
            and result.document_version_id == lead_document_id
            and bool(topical_terms.intersection(chunk_terms))
        )
        if semantic_suitable or same_document_topical:
            anchor_candidates.append(replace(result, covered_constraints=covered))

    anchor_limit = min(len(constraints), max(1, max_selected_chunks // 2))
    anchors: list[KnowledgeSearchResult] = []
    covered_so_far: set[str] = set()
    remaining = list(anchor_candidates)
    while remaining and len(anchors) < anchor_limit:
        best = min(
            remaining,
            key=lambda item: (
                -len(set(item.covered_constraints).difference(covered_so_far)),
                item.preselection_rank or 10**9,
                -item.fused_score,
                item.chunk_id,
            ),
        )
        incremental = set(best.covered_constraints).difference(covered_so_far)
        if not incremental:
            break
        anchors.append(best)
        covered_so_far.update(incremental)
        remaining.remove(best)

    anchor_ids = {item.chunk_id for item in anchors}
    remaining_slots = max_selected_chunks - len(anchors)
    ordinary = [item for item in results if item.chunk_id not in anchor_ids]
    ordinary.sort(
        key=lambda item: (
            bool(matched_literal_constraints(item.chunk_text, constraints))
            and not bool(
                topical_terms.intersection(general_lexical_terms(item.chunk_text))
            )
            and (
                item.semantic_score is None
                or item.semantic_score < semantic_threshold
            ),
            item.preselection_rank or 10**9,
            item.chunk_id,
        )
    )
    promoted = _promote_continuation_neighbors(
        ordinary,
        selection_window=remaining_slots,
    )
    candidates = [*anchors, *promoted]
    selected: list[KnowledgeSearchResult] = []
    seen: set[tuple[int, str]] = set()
    used_chars = 0
    for result in candidates:
        is_anchor = result.chunk_id in anchor_ids
        excerpt, offset = _emitted_excerpt(
            result.chunk_text,
            constraints=constraints if is_anchor else (),
            max_chars=max_chunk_chars,
        )
        identity = (
            result.document_version_id,
            result.chunk_content_sha256 or str(result.chunk_id),
        )
        if identity in seen or used_chars + len(excerpt) > max_context_chars:
            continue
        emitted_coverage = matched_literal_constraints(excerpt, constraints)
        if is_anchor and not emitted_coverage:
            continue
        selected.append(
            replace(
                result,
                selection_reason="constraint_anchor" if is_anchor else "relevance",
                covered_constraints=emitted_coverage,
                emitted_excerpt=excerpt,
                emitted_offset=offset,
            )
        )
        seen.add(identity)
        used_chars += len(excerpt)
        if len(selected) >= max_selected_chunks:
            break
    return [
        replace(item, final_rank=rank)
        for rank, item in enumerate(selected, start=1)
    ]


def _emitted_excerpt(
    text: str,
    *,
    constraints: tuple[LiteralConstraint, ...],
    max_chars: int,
) -> tuple[str, int]:
    """Return a deterministic prefix or match-centred anchor excerpt."""
    if len(text) <= max_chars:
        return text, 0
    match = next(
        (
            literal_match_span(text, constraint)
            for constraint in constraints
            if literal_match_span(text, constraint) is not None
        ),
        None,
    )
    if match is None:
        return text[:max_chars], 0
    midpoint = (match[0] + match[1]) // 2
    start = max(0, min(len(text) - max_chars, midpoint - max_chars // 2))
    return text[start : start + max_chars], start


def _promote_continuation_neighbors(
    results: list[KnowledgeSearchResult],
    *,
    selection_window: int,
) -> list[KnowledgeSearchResult]:
    """Promote relevant neighbours when top chunks split a sentence."""
    by_position = {
        (result.document_version_id, result.chunk_no): result for result in results
    }
    promoted: list[KnowledgeSearchResult] = []
    promoted_ids: set[int] = set()
    for result in results[:selection_window]:
        stripped = result.chunk_text.lstrip()
        page_number_continuation = bool(re.match(r"\d+\s+[a-z]", stripped))
        starts_mid_sentence = stripped[:1].islower() or page_number_continuation
        if starts_mid_sentence and result.chunk_no > 1:
            predecessor = by_position.get(
                (result.document_version_id, result.chunk_no - 1)
            )
            if (
                predecessor is not None
                and predecessor.fused_score
                >= (0.5 if page_number_continuation else 0.65)
                and predecessor.chunk_id not in promoted_ids
            ):
                promoted.append(predecessor)
                promoted_ids.add(predecessor.chunk_id)
        if result.chunk_id not in promoted_ids:
            promoted.append(result)
            promoted_ids.add(result.chunk_id)
        if stripped and stripped[-1] not in ".!?" and result.chunk_no > 0:
            successor = by_position.get(
                (result.document_version_id, result.chunk_no + 1)
            )
            if (
                successor is not None
                and successor.fused_score >= 0.5
                and successor.chunk_id not in promoted_ids
            ):
                promoted.append(successor)
                promoted_ids.add(successor.chunk_id)
    promoted.extend(
        result for result in results if result.chunk_id not in promoted_ids
    )
    return promoted


def _is_navigation_heavy(text: str) -> bool:
    """Identify Markdown navigation/front-matter chunks without query-specific rules.

    Navigation remains stored, embedded, and searchable as lineage-bearing content,
    but substantive prose is selected first when both kinds clear the unchanged
    semantic/lexical gates. This prevents Pandoc contents pages from consuming the
    complete bounded evidence pack merely because they repeat every section title.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return True
    upper_text = text.upper()
    if "TABLE OF CONTENTS" in upper_text:
        return True
    dotted_lines = sum(bool(_DOTTED_LEADER.search(line)) for line in lines)
    return dotted_lines >= 2 and dotted_lines * 2 >= len(lines)


def _navigation_classification(text: str) -> str:
    """Return a bounded navigation diagnostic without changing ranking policy."""
    upper_text = text.upper()
    if "TABLE OF CONTENTS" in upper_text:
        return "TABLE_OF_CONTENTS"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    dotted_lines = sum(bool(_DOTTED_LEADER.search(line)) for line in lines)
    if lines and dotted_lines >= 2 and dotted_lines * 2 >= len(lines):
        return "DOTTED_LEADERS"
    return "CONTENT"


def _optional_string(value: Any) -> str | None:
    """Return a stripped optional string."""
    text = str(value or "").strip()
    return text or None


def _optional_json_object_text(value: Any, *, field_name: str) -> str | None:
    """Return deterministic JSON text from native Oracle JSON or text.

    Args:
        value: Null, serialized JSON, or a native JSON mapping.
        field_name: Projection name used in validation errors.

    Returns:
        Compact, deterministic JSON object text, or ``None`` for null.

    Raises:
        KnowledgeRetrievalError: If the value is not a valid JSON object.
    """
    if value is None:
        return None
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
        if not isinstance(parsed, Mapping):
            raise TypeError("JSON metadata must be an object")
        return json.dumps(
            dict(parsed),
            allow_nan=False,
            default=_json_metadata_scalar,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise KnowledgeRetrievalError(f"{field_name} projection is malformed.") from exc


def _json_metadata_scalar(value: Any) -> int | float:
    """Convert supported Oracle native JSON scalars for JSON serialization.

    Args:
        value: A scalar not handled natively by :func:`json.dumps`.

    Returns:
        The equivalent standard JSON numeric value.

    Raises:
        TypeError: If the value is not a finite Oracle JSON decimal.
    """
    if not isinstance(value, Decimal) or not value.is_finite():
        raise TypeError("Unsupported native JSON metadata scalar")
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _optional_int(value: Any) -> int | None:
    """Return an optional integer value."""
    return int(value) if value is not None else None


def _classification_tags(value: Any) -> tuple[str, ...]:
    """Return a validated tuple from a relational-tag JSON projection."""
    if value is None or str(value).strip() == "":
        return ()
    parsed = value if isinstance(value, list) else json.loads(str(value))
    if not isinstance(parsed, list) or any(
        not isinstance(item, str) for item in parsed
    ):
        raise KnowledgeRetrievalError("Classification tag projection is malformed.")
    return tuple(parsed)


def _retrieval_failure_code(exc: Exception) -> str:
    """Map malformed row exceptions to safe diagnostic reason codes."""
    message = str(exc).casefold()
    if "profile" in message:
        return "embedding_profile_incompatible"
    if "model" in message:
        return "embedding_model_incompatible"
    if "dimension" in message:
        return "embedding_dimension_incompatible"
    if "scope" in message:
        return "retrieval_scope_mismatch"
    return "malformed_retrieval_row"
