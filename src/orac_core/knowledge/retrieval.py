"""Scope-bound lexical retrieval over current Core knowledge chunks."""

# Author: Clive Bostock
# Date: 18-Jul-2026
# Description: Ranks authorised searchable chunks with lexical relevance and bounded context.

from __future__ import annotations

import json
import math
import re
from typing import Any

from model.plugin_routing.embeddings import EmbeddingProvider, HashEmbeddingProvider

from .models import KnowledgeRetrievalOutcome, KnowledgeSearchResult
from .repository import KnowledgeIngestionRepository
from .scope import KnowledgeScope, KnowledgeScopeConfigurationError

_LEXICAL_TOKEN = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", re.IGNORECASE)
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "base",
        "consult",
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
        "of",
        "on",
        "query",
        "search",
        "source",
        "the",
        "to",
        "use",
        "using",
        "what",
    }
)


class KnowledgeRetrievalError(RuntimeError):
    """Raised when scoped knowledge retrieval cannot be used safely."""


class KnowledgeRetrievalService:
    """Search current Core knowledge chunks within one authorised scope."""

    def __init__(
        self,
        *,
        repository: KnowledgeIngestionRepository | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        """Initialise retrieval with injectable persistence and embeddings."""
        self._repository = repository or KnowledgeIngestionRepository()
        self._embedding_provider = embedding_provider or HashEmbeddingProvider()

    def search(
        self,
        query: str,
        *,
        target_scope_type: str,
        target_scope_key: str,
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
            scope=scope,
            max_selected_chunks=top_k,
            min_lexical_score=0.0,
        )
        if outcome.status == "failed":
            raise KnowledgeRetrievalError(", ".join(outcome.reason_codes))
        return list(outcome.results)

    def retrieve(
        self,
        query: str,
        *,
        scope: KnowledgeScope,
        max_candidate_chunks: int = 1000,
        max_selected_chunks: int = 6,
        min_lexical_score: float = 0.25,
        max_chunk_chars: int = 2200,
        max_context_chars: int = 12000,
    ) -> KnowledgeRetrievalOutcome:
        """Retrieve bounded lexical evidence from one canonical scope."""
        if not query.strip():
            raise ValueError("query is required")
        if max_candidate_chunks <= 0 or max_selected_chunks <= 0:
            raise ValueError("Knowledge retrieval limits must be positive.")
        if not 0.0 <= min_lexical_score <= 1.0:
            raise ValueError("min_lexical_score must be between 0 and 1.")

        try:
            query_vector = self._embedding_provider.embed_text(query)
        except Exception as exc:
            raise KnowledgeRetrievalError("query_embedding_failed") from exc
        dimensions = len(query_vector)
        rows = self._repository.load_searchable_chunks(
            target_scope_type=scope.scope_type,
            target_scope_key=scope.scope_key,
            embedding_model_identifier=self._embedding_provider.model_id,
            embedding_dimensions=dimensions,
            candidate_limit=max_candidate_chunks,
        )
        if len(rows) > max_candidate_chunks:
            return KnowledgeRetrievalOutcome(
                status="failed",
                reason_codes=("candidate_limit_exceeded",),
                scope=scope,
                considered_count=len(rows),
                embedding_model_identifier=self._embedding_provider.model_id,
            )

        scored: list[KnowledgeSearchResult] = []
        malformed_count = 0
        failure_codes: list[str] = []
        for row in rows:
            try:
                self._assert_compatible_row(row, dimensions)
                if (
                    str(row.get("target_scope_type") or "").upper() != scope.scope_type
                    or str(row.get("target_scope_key") or "") != scope.scope_key
                ):
                    raise KnowledgeRetrievalError("scope_mismatch")
                vector = _parse_vector(row["embedding_vector"], dimensions)
                semantic_score = _cosine_similarity(query_vector, vector)
                lexical_score = _lexical_score(
                    query,
                    str(row.get("chunk_text") or ""),
                    source_name=str(
                        row.get("original_filename")
                        or row.get("parent_source_reference")
                        or ""
                    ),
                    excluded_tokens=_scope_tokens(scope),
                )
            except (KeyError, TypeError, ValueError, KnowledgeRetrievalError) as exc:
                malformed_count += 1
                failure_codes.append(_retrieval_failure_code(exc))
                continue
            if lexical_score < min_lexical_score:
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
                    source_type=str(row.get("source_type") or ""),
                    document_title=_optional_string(row.get("document_title")),
                    original_filename=_optional_string(row.get("original_filename")),
                    content_uri=_optional_string(row.get("content_uri")),
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
                )
            )

        ordered = sorted(
            scored,
            key=lambda result: (
                result.lexical_score,
                result.semantic_score or -1.0,
                -result.chunk_no,
            ),
            reverse=True,
        )
        selected = _select_bounded_results(
            ordered,
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
            return KnowledgeRetrievalOutcome(
                status="failed" if all_rows_malformed else "no_evidence",
                reason_codes=(reason,),
                scope=scope,
                considered_count=len(rows),
                threshold_count=len(ordered),
                malformed_count=malformed_count,
                embedding_model_identifier=self._embedding_provider.model_id,
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
        )

    def _assert_compatible_row(self, row: dict[str, Any], dimensions: int) -> None:
        """Reject rows stored with another embedding model or dimension."""
        model_id = str(row.get("embedding_model_identifier") or "")
        row_dimensions = int(row.get("embedding_dimensions") or 0)
        if model_id != self._embedding_provider.model_id:
            raise KnowledgeRetrievalError(
                f"Stored vector model '{model_id}' does not match query model "
                f"'{self._embedding_provider.model_id}'."
            )
        if row_dimensions != dimensions:
            raise KnowledgeRetrievalError(
                f"Stored vector dimension {row_dimensions} does not match query "
                f"dimension {dimensions}."
            )


def _lexical_score(
    query: str,
    chunk_text: str,
    *,
    source_name: str,
    excluded_tokens: frozenset[str] = frozenset(),
) -> float:
    """Score token coverage, phrases, identifiers, and source-name matches."""
    query_tokens = [
        token.casefold()
        for token in _LEXICAL_TOKEN.findall(query)
        if token.casefold() not in _STOP_WORDS
        and token.casefold() not in excluded_tokens
    ]
    if not query_tokens:
        return 0.0
    text_lower = chunk_text.casefold()
    source_lower = source_name.casefold()
    haystack_tokens = set(_LEXICAL_TOKEN.findall(text_lower))
    matched = {token for token in query_tokens if token in haystack_tokens}
    coverage = len(matched) / len(set(query_tokens))
    phrase = " ".join(query_tokens)
    phrase_score = 0.15 if len(query_tokens) > 1 and phrase in text_lower else 0.0
    identifiers = {token for token in query_tokens if any(c in token for c in "._-")}
    identifier_score = 0.1 if identifiers & haystack_tokens else 0.0
    source_score = 0.1 if any(token in source_lower for token in query_tokens) else 0.0
    return min(1.0, coverage * 0.75 + phrase_score + identifier_score + source_score)


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


def _parse_vector(raw_vector: Any, dimensions: int) -> list[float]:
    """Parse one finite JSON numeric embedding with the expected dimension."""
    try:
        values = json.loads(str(raw_vector))
    except json.JSONDecodeError as exc:
        raise KnowledgeRetrievalError(
            "Stored knowledge vector is malformed JSON."
        ) from exc
    if not isinstance(values, list) or len(values) != dimensions:
        raise KnowledgeRetrievalError(
            "Stored knowledge vector has the wrong dimensions."
        )
    vector: list[float] = []
    for value in values:
        if not isinstance(value, (int, float)):
            raise KnowledgeRetrievalError(
                "Stored knowledge vector contains a non-numeric value."
            )
        number = float(value)
        if not math.isfinite(number):
            raise KnowledgeRetrievalError(
                "Stored knowledge vector contains a non-finite value."
            )
        vector.append(number)
    return vector


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    """Return cosine similarity for equal-length finite vectors."""
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    dot = sum(
        left_value * right_value
        for left_value, right_value in zip(left, right, strict=True)
    )
    return dot / (left_norm * right_norm)


def _optional_string(value: Any) -> str | None:
    """Return a stripped optional string."""
    text = str(value or "").strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    """Return an optional integer value."""
    return int(value) if value is not None else None


def _retrieval_failure_code(exc: Exception) -> str:
    """Map malformed row exceptions to safe diagnostic reason codes."""
    message = str(exc).casefold()
    if "model" in message:
        return "embedding_model_incompatible"
    if "dimension" in message:
        return "embedding_dimension_incompatible"
    if "non-numeric" in message:
        return "embedding_vector_non_numeric"
    if "scope" in message:
        return "retrieval_scope_mismatch"
    return "malformed_retrieval_row"
