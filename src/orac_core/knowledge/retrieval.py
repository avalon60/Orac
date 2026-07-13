"""Scope-bound retrieval over Core knowledge chunks."""

# Author: Clive Bostock
# Date: 13-Jul-2026
# Description: Scores searchable knowledge chunks through approved Core views.

from __future__ import annotations

import json
import math
from typing import Any

from model.plugin_routing.embeddings import EmbeddingProvider, HashEmbeddingProvider

from .models import KnowledgeSearchResult
from .repository import KnowledgeIngestionRepository


class KnowledgeRetrievalError(RuntimeError):
    """Raised when searchable knowledge vectors cannot be used safely."""


class KnowledgeRetrievalService:
    """Search current Core knowledge chunks within an authorised scope."""

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
        target_scope_type: str | None,
        target_scope_key: str | None,
        top_k: int = 5,
        allow_cross_scope: bool = False,
    ) -> list[KnowledgeSearchResult]:
        """Return top matching chunks for a query within the requested scope."""
        if not query.strip():
            raise ValueError("query is required")
        if top_k <= 0:
            return []

        scope_type = _normalise_scope_type(target_scope_type)
        scope_key = target_scope_key.strip() if target_scope_key else None
        if not allow_cross_scope and (scope_type is None or not scope_key):
            raise KnowledgeRetrievalError(
                "Knowledge retrieval requires target_scope_type and target_scope_key."
            )

        query_vector = self._embedding_provider.embed_text(query)
        dimensions = len(query_vector)
        rows = self._repository.load_searchable_chunks(
            target_scope_type=scope_type,
            target_scope_key=scope_key,
            embedding_model_identifier=self._embedding_provider.model_id,
            embedding_dimensions=dimensions,
            allow_cross_scope=allow_cross_scope,
        )
        scored: list[KnowledgeSearchResult] = []
        for row in rows:
            self._assert_compatible_row(row, dimensions)
            vector = _parse_vector(row["embedding_vector"], dimensions)
            score = _cosine_similarity(query_vector, vector)
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
                    score=score,
                    target_scope_type=str(row["target_scope_type"]),
                    target_scope_key=str(row["target_scope_key"]),
                    embedding_model_identifier=str(row["embedding_model_identifier"]),
                    embedding_dimensions=int(row["embedding_dimensions"]),
                    chunk_text=str(row["chunk_text"]),
                )
            )

        return sorted(scored, key=lambda result: result.score, reverse=True)[:top_k]

    def _assert_compatible_row(self, row: dict[str, Any], dimensions: int) -> None:
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


def _normalise_scope_type(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    scope_type = value.strip().upper()
    if scope_type not in {"PROJECT", "PLUGIN"}:
        raise KnowledgeRetrievalError("target_scope_type must be PROJECT or PLUGIN.")
    return scope_type


def _parse_vector(raw_vector: Any, dimensions: int) -> list[float]:
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
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    dot = sum(
        left_value * right_value
        for left_value, right_value in zip(left, right, strict=True)
    )
    return dot / (left_norm * right_norm)
