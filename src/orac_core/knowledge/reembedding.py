"""Resumable native-vector rebuild workflow for existing knowledge chunks."""

# Author: Clive Bostock
# Date: 2026-09-01
# Description: Re-embeds normalized chunks without parsing source documents.

from __future__ import annotations

from dataclasses import dataclass

from .embeddings import OllamaKnowledgeEmbeddingProvider
from .repository import KnowledgeEmbeddingRepository


@dataclass(frozen=True)
class KnowledgeReembeddingResult:
    """Safe operator result for one bounded re-embedding invocation."""

    reembedding_run_id: int
    embedding_profile_id: int
    batches_processed: int
    chunks_processed: int
    status: dict[str, object]


class KnowledgeReembeddingService:
    """Build and optionally activate native embeddings from stored chunk text."""

    def __init__(
        self,
        *,
        repository: KnowledgeEmbeddingRepository,
        embedding_provider: OllamaKnowledgeEmbeddingProvider,
    ) -> None:
        """Initialise the service with profile-bound dependencies."""
        self._repository = repository
        self._provider = embedding_provider

    def run(
        self,
        *,
        reembedding_run_id: int | None = None,
        batch_size: int = 16,
        max_batches: int = 1000,
        activate: bool = False,
    ) -> KnowledgeReembeddingResult:
        """Resume a bounded run and atomically activate only after validation."""
        if not 1 <= batch_size <= 500:
            raise ValueError("batch_size must be between 1 and 500")
        if max_batches <= 0:
            raise ValueError("max_batches must be positive")
        profile_id = self._repository.ensure_profile(self._provider.profile)
        run_id = reembedding_run_id or self._repository.begin_run(profile_id)
        batches = 0
        processed = 0
        while batches < max_batches:
            rows = self._repository.open_run_chunks(
                reembedding_run_id=run_id,
                chunk_limit=batch_size,
            )
            if not rows:
                break
            vectors = self._provider.embed_texts(
                [str(row["chunk_text"]) for row in rows]
            )
            for row, vector in zip(rows, vectors, strict=True):
                self._repository.store_native_embedding(
                    embedding_profile_id=profile_id,
                    reembedding_run_id=run_id,
                    chunk_id=int(row["chunk_id"]),
                    embedding_text_sha256=str(row["chunk_content_sha256"]),
                    vector=vector,
                )
                processed += 1
            batches += 1
        remaining = self._repository.open_run_chunks(
            reembedding_run_id=run_id,
            chunk_limit=1,
        )
        if not remaining:
            self._repository.validate_run(run_id)
            if activate:
                self._repository.activate_run(run_id)
        status = self._repository.run_status(run_id)
        return KnowledgeReembeddingResult(
            reembedding_run_id=run_id,
            embedding_profile_id=profile_id,
            batches_processed=batches,
            chunks_processed=processed,
            status=status,
        )
