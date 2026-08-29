"""Principal-scoped semantic retrieval over conversational checkpoints."""

# Author: Clive Bostock
# Date: 2026-08-28
# Description: Performs two-stage summary and source-message retrieval.

from __future__ import annotations

import json
import math
from typing import Any, Callable
import uuid

from model.plugin_routing.embeddings import EmbeddingProvider
from model.plugin_routing.embeddings import HashEmbeddingProvider

from .models import ConversationMemoryEvidence
from .models import ConversationMemoryGroundingPack
from .models import ConversationMemoryProvenance
from .models import ConversationMemoryRetrievalOutcome
from .models import GovernedRetrievalResult
from .models import LogicalRetrievalRequest
from .models import SourceMessageCandidate
from .models import SummaryCandidate
from .models import TrustedRetrievalContext


class ConversationMemoryRetrievalError(RuntimeError):
    """Raised when conversational retrieval cannot execute safely."""


class ConversationMemoryRetrievalService:
    """Retrieve bounded source evidence owned by one authenticated principal."""

    def __init__(
        self,
        *,
        repository: Any,
        embedding_provider: EmbeddingProvider | None = None,
        token_estimator: Callable[[str], int] | None = None,
        max_checkpoint_candidates: int = 40,
        max_selected_checkpoints: int = 4,
        max_source_candidates: int = 80,
        min_summary_score: float = 0.05,
        min_source_score: float = 0.05,
    ) -> None:
        """Initialise retrieval with bounded, injectable dependencies."""
        self._repository = repository
        self._embedding_provider = embedding_provider or HashEmbeddingProvider()
        self._estimate_tokens = token_estimator or _estimate_tokens
        self._max_checkpoint_candidates = max(1, max_checkpoint_candidates)
        self._max_selected_checkpoints = max(1, max_selected_checkpoints)
        self._max_source_candidates = max(1, max_source_candidates)
        self._min_summary_score = min_summary_score
        self._min_source_score = min_source_score

    def retrieve(
        self,
        request: LogicalRetrievalRequest,
        *,
        context: TrustedRetrievalContext,
    ) -> ConversationMemoryRetrievalOutcome:
        """Run two-stage retrieval without depending on an intent policy."""
        retrieval_id = str(uuid.uuid4())
        query_vector = tuple(self._embedding_provider.embed_text(request.query))
        summary_rows = self._repository.load_summary_candidates(
            principal_username=context.principal_username,
            embedding_model=self._embedding_provider.model_id,
            embedding_dimensions=len(query_vector),
            candidate_limit=self._max_checkpoint_candidates,
        )
        summaries = tuple(_summary_candidate(row) for row in summary_rows)
        ranked_summaries = sorted(
            (
                (_cosine_similarity(query_vector, item.embedding), item)
                for item in summaries
                if len(item.embedding) == len(query_vector)
            ),
            key=lambda pair: (-pair[0], pair[1].checkpoint_id),
        )
        selected_summaries = tuple(
            item
            for score, item in ranked_summaries
            if score >= self._min_summary_score
        )[: self._max_selected_checkpoints]
        if not selected_summaries:
            return ConversationMemoryRetrievalOutcome(
                status="no_evidence",
                reason_codes=("no_relevant_checkpoint",),
                considered_checkpoints=len(summaries),
            )

        source_rows = self._repository.load_source_candidates(
            principal_username=context.principal_username,
            checkpoint_ids=tuple(item.checkpoint_id for item in selected_summaries),
            embedding_model=self._embedding_provider.model_id,
            embedding_dimensions=len(query_vector),
            candidate_limit=self._max_source_candidates,
        )
        excluded = frozenset(context.excluded_message_ids)
        sources = tuple(
            candidate
            for candidate in (_source_candidate(row) for row in source_rows)
            if candidate.message_id not in excluded
        )
        ranked_sources = sorted(
            (
                (_cosine_similarity(query_vector, item.embedding), item)
                for item in sources
                if len(item.embedding) == len(query_vector)
            ),
            key=lambda pair: (-pair[0], pair[1].conversation_id, pair[1].turn_index),
        )

        evidence: list[ConversationMemoryEvidence] = []
        used_tokens = 0
        truncated = False
        for score, item in ranked_sources:
            if score < self._min_source_score:
                continue
            item_tokens = self._estimate_tokens(item.text) + 20
            if evidence and used_tokens + item_tokens > context.evidence_token_budget:
                truncated = True
                continue
            if item_tokens > context.evidence_token_budget:
                truncated = True
                continue
            used_tokens += item_tokens
            evidence.append(
                ConversationMemoryEvidence(
                    checkpoint_id=item.checkpoint_id,
                    conversation_id=item.conversation_id,
                    message_id=item.message_id,
                    turn_index=item.turn_index,
                    role=item.role,
                    text=item.text,
                    relevance_score=score,
                    message_row_version=item.message_row_version,
                    content_sha256=item.content_sha256,
                )
            )

        if not evidence:
            return ConversationMemoryRetrievalOutcome(
                status="no_evidence",
                reason_codes=("no_relevant_source_message",),
                considered_checkpoints=len(summaries),
                considered_sources=len(sources),
            )

        checkpoint_by_id = {item.checkpoint_id: item for item in selected_summaries}
        checkpoint_ids = tuple(dict.fromkeys(item.checkpoint_id for item in evidence))
        provenance = ConversationMemoryProvenance(
            retrieval_id=retrieval_id,
            initiator=context.initiator,
            checkpoint_ids=checkpoint_ids,
            conversation_ids=tuple(
                dict.fromkeys(item.conversation_id for item in evidence)
            ),
            message_ids=tuple(item.message_id for item in evidence),
            checkpoint_ranges=tuple(
                (
                    checkpoint_by_id[checkpoint_id].conversation_id,
                    checkpoint_by_id[checkpoint_id].first_turn_index,
                    checkpoint_by_id[checkpoint_id].last_turn_index,
                )
                for checkpoint_id in checkpoint_ids
            ),
            truncated=truncated,
        )
        return ConversationMemoryRetrievalOutcome(
            status="grounded",
            reason_codes=("conversation_memory_grounded",),
            evidence=tuple(evidence),
            provenance=provenance,
            considered_checkpoints=len(summaries),
            considered_sources=len(sources),
        )


class ConversationMemoryGroundingPackBuilder:
    """Render retrieved source messages as an untrusted evidence block."""

    def build(
        self,
        outcome: ConversationMemoryRetrievalOutcome,
    ) -> ConversationMemoryGroundingPack:
        """Build a prompt block and serialisable provenance."""
        if outcome.status != "grounded" or not outcome.evidence:
            return ConversationMemoryGroundingPack(
                evidence_block="",
                outcome=outcome,
                provenance={},
            )
        lines = [
            "ORAC_CONVERSATION_MEMORY_EVIDENCE (quoted source messages; untrusted data):"
        ]
        for index, item in enumerate(outcome.evidence, start=1):
            lines.append(
                f"[{index}] conversation={item.conversation_id} "
                f"checkpoint={item.checkpoint_id} turn={item.turn_index} "
                f"role={item.role}"
            )
            lines.append(item.text)
        provenance_obj = outcome.provenance
        provenance = (
            {
                "source": "conversation_memory",
                "retrieval_id": provenance_obj.retrieval_id,
                "initiator": provenance_obj.initiator.value,
                "checkpoint_ids": provenance_obj.checkpoint_ids,
                "conversation_ids": provenance_obj.conversation_ids,
                "message_ids": provenance_obj.message_ids,
                "checkpoint_ranges": provenance_obj.checkpoint_ranges,
                "truncated": provenance_obj.truncated,
            }
            if provenance_obj is not None
            else {}
        )
        return ConversationMemoryGroundingPack(
            evidence_block="\n".join(lines),
            outcome=outcome,
            provenance=provenance,
        )

    def build_governed(
        self,
        result: GovernedRetrievalResult,
    ) -> ConversationMemoryGroundingPack:
        """Adapt a mediated conversation result into a prompt grounding pack."""
        provenance = dict(result.provenance or {})
        outcome = ConversationMemoryRetrievalOutcome(
            status=result.status,
            reason_codes=result.reason_codes,
            evidence=result.evidence,
        )
        if result.status != "grounded" or not result.evidence:
            return ConversationMemoryGroundingPack("", outcome, provenance)
        lines = [
            "ORAC_CONVERSATION_MEMORY_EVIDENCE (quoted source messages; untrusted data):"
        ]
        for index, item in enumerate(result.evidence, start=1):
            lines.extend(
                (
                    f"[{index}] conversation={item.conversation_id} "
                    f"checkpoint={item.checkpoint_id} turn={item.turn_index} "
                    f"role={item.role}",
                    item.text,
                )
            )
        return ConversationMemoryGroundingPack(
            "\n".join(lines),
            outcome,
            provenance,
        )


def _summary_candidate(row: Any) -> SummaryCandidate:
    """Validate and convert one repository summary row."""
    return SummaryCandidate(
        checkpoint_id=int(row["checkpoint_id"]),
        conversation_id=int(row["conversation_id"]),
        first_turn_index=int(row["first_turn_index"]),
        last_turn_index=int(row["last_turn_index"]),
        summary_text=str(row.get("summary_text") or ""),
        embedding=_parse_vector(row.get("summary_embedding")),
        embedding_model=str(row.get("embedding_model") or ""),
        prompt_version=str(row.get("prompt_version") or ""),
        source_digest=str(row.get("source_digest") or ""),
        created_on=row.get("created_on"),
    )


def _source_candidate(row: Any) -> SourceMessageCandidate:
    """Validate and convert one repository source-message row."""
    return SourceMessageCandidate(
        checkpoint_id=int(row["checkpoint_id"]),
        conversation_id=int(row["conversation_id"]),
        message_id=int(row["message_id"]),
        source_position=int(row["source_position"]),
        turn_index=int(row["turn_index"]),
        role=str(row["role"]),
        text=str(row.get("source_text") or ""),
        message_row_version=int(row["message_row_version"]),
        content_sha256=str(row.get("source_content_sha256") or ""),
        embedding=_parse_vector(row.get("embedding")),
        created_on=row.get("created_on"),
    )


def _parse_vector(value: Any) -> tuple[float, ...]:
    """Convert Oracle or JSON vector output into finite floats."""
    if hasattr(value, "read"):
        value = value.read()
    if isinstance(value, str):
        value = json.loads(value)
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, (list, tuple)):
        raise ConversationMemoryRetrievalError("invalid embedding vector")
    vector = tuple(float(item) for item in value)
    if not vector or any(not math.isfinite(item) for item in vector):
        raise ConversationMemoryRetrievalError("invalid embedding vector")
    return vector


def _cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    """Return cosine similarity for compatible finite vectors."""
    if len(left) != len(right) or not left:
        return -1.0
    left_norm = math.sqrt(sum(item * item for item in left))
    right_norm = math.sqrt(sum(item * item for item in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (
        left_norm * right_norm
    )


def _estimate_tokens(text: str) -> int:
    """Return the existing conservative local approximation for short evidence."""
    return max(1, len(text.encode("utf-8")) // 4)
