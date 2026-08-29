"""Transfer objects for governed conversational-memory retrieval."""

# Author: Clive Bostock
# Date: 2026-08-28
# Description: Defines trigger-neutral requests, authority, evidence, and provenance.

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping


class RetrievalDomain(StrEnum):
    """Logical host retrieval domains."""

    CONVERSATION = "CONVERSATION"
    PROJECT = "PROJECT"
    PLUGIN = "PLUGIN"


class RetrievalInitiator(StrEnum):
    """Trusted host classifications for retrieval initiation."""

    EXPLICIT_POLICY = "EXPLICIT_POLICY"
    DIRECT_HOST = "DIRECT_HOST"
    MODEL_TOOL = "MODEL_TOOL"
    HOST_POLICY = "HOST_POLICY"


@dataclass(frozen=True)
class LogicalRetrievalRequest:
    """A scope-free logical retrieval request."""

    query: str
    domain: RetrievalDomain

    def __post_init__(self) -> None:
        """Validate the deliberately narrow logical request."""
        query = str(self.query or "").strip()
        if not query:
            raise ValueError("retrieval query is required")
        if len(query) > 2048:
            raise ValueError("retrieval query exceeds 2,048 characters")
        object.__setattr__(self, "query", query)


@dataclass(frozen=True)
class TrustedRetrievalContext:
    """Host-derived authority and limits that are never model supplied."""

    principal_username: str
    evidence_token_budget: int
    current_conversation_id: int | None = None
    excluded_message_ids: tuple[int, ...] = ()
    correlation_id: str | None = None
    initiator: RetrievalInitiator = RetrievalInitiator.DIRECT_HOST
    project_scope: Any | None = None
    plugin_retrieval_bridge: Any | None = None

    def __post_init__(self) -> None:
        """Validate trusted runtime facts before crossing the domain boundary."""
        principal = str(self.principal_username or "").strip()
        if not principal:
            raise ValueError("authenticated principal is required")
        if self.evidence_token_budget <= 0:
            raise ValueError("evidence token budget must be positive")
        if self.current_conversation_id is not None and self.current_conversation_id <= 0:
            raise ValueError("current conversation id must be positive")
        if any(message_id <= 0 for message_id in self.excluded_message_ids):
            raise ValueError("excluded message ids must be positive")
        object.__setattr__(self, "principal_username", principal)


@dataclass(frozen=True)
class SummaryCandidate:
    """One principal-scoped immutable checkpoint candidate."""

    checkpoint_id: int
    conversation_id: int
    first_turn_index: int
    last_turn_index: int
    summary_text: str
    embedding: tuple[float, ...]
    embedding_model: str
    prompt_version: str
    source_digest: str
    created_on: Any | None = None


@dataclass(frozen=True)
class SourceMessageCandidate:
    """One authoritative source message supporting a checkpoint."""

    checkpoint_id: int
    conversation_id: int
    message_id: int
    source_position: int
    turn_index: int
    role: str
    text: str
    message_row_version: int
    content_sha256: str
    embedding: tuple[float, ...]
    created_on: Any | None = None


@dataclass(frozen=True)
class ConversationMemoryEvidence:
    """Bounded source-message evidence suitable for prompt projection."""

    checkpoint_id: int
    conversation_id: int
    message_id: int
    turn_index: int
    role: str
    text: str
    relevance_score: float
    message_row_version: int
    content_sha256: str


@dataclass(frozen=True)
class ConversationMemoryProvenance:
    """Safe lineage for one conversational-memory retrieval result."""

    retrieval_id: str
    initiator: RetrievalInitiator
    checkpoint_ids: tuple[int, ...]
    conversation_ids: tuple[int, ...]
    message_ids: tuple[int, ...]
    checkpoint_ranges: tuple[tuple[int, int, int], ...]
    truncated: bool


@dataclass(frozen=True)
class ConversationMemoryRetrievalOutcome:
    """Trigger-neutral result returned by conversational retrieval."""

    status: str
    reason_codes: tuple[str, ...]
    evidence: tuple[ConversationMemoryEvidence, ...] = ()
    provenance: ConversationMemoryProvenance | None = None
    considered_checkpoints: int = 0
    considered_sources: int = 0


@dataclass(frozen=True)
class GovernedRetrievalResult:
    """Domain-neutral result returned by the host mediation seam."""

    domain: RetrievalDomain
    status: str
    reason_codes: tuple[str, ...]
    evidence: tuple[Any, ...] = ()
    provenance: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class ConversationMemoryGroundingPack:
    """Bounded conversational evidence and provenance for prompt assembly."""

    evidence_block: str
    outcome: ConversationMemoryRetrievalOutcome
    provenance: Mapping[str, Any]
