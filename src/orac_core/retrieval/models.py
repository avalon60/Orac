"""Provider-neutral retrieval models for explicit internet search."""
# Author: Clive Bostock
# Date: 2026-05-26
# Description: Defines the search, fetch, and grounding data structures.

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class SearchRequest:
    """Describes one explicit user-initiated search request."""

    query: str
    max_results: int = 5
    provider_name: str | None = None
    trigger_phrase: str | None = None
    created_at: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Represents one structured search result from a provider."""

    title: str
    url: str
    snippet: str | None = None
    content: str | None = None
    source_name: str | None = None
    engine: str | None = None
    rank: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FetchedSource:
    """Represents one conservatively fetched source document."""

    url: str
    title: str | None = None
    source_name: str | None = None
    fetched_at: datetime = field(default_factory=_utc_now)
    content_type: str | None = None
    text: str = ""
    excerpt: str = ""
    byte_count: int | None = None
    source_rank: int | None = None
    fetch_status: str = "ok"
    fetch_error: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class GroundingSource:
    """Represents one compact evidence item for prompt grounding."""

    title: str
    url: str
    source_name: str | None = None
    fetched_at: datetime = field(default_factory=_utc_now)
    excerpt: str = ""
    source_rank: int | None = None


@dataclass(frozen=True, slots=True)
class GroundingPack:
    """Collects retrieved evidence for safe prompt grounding."""

    request: SearchRequest
    search_results: tuple[SearchResult, ...]
    fetched_sources: tuple[FetchedSource, ...]
    grounding_sources: tuple[GroundingSource, ...]
    warning: str
    evidence_block: str
    created_at: datetime = field(default_factory=_utc_now)
    require_citations: bool = True


@dataclass(frozen=True, slots=True)
class RetrievalOutcome:
    """Reports the result of one explicit retrieval attempt."""

    requested: bool
    status: str
    message: str
    grounding_pack: GroundingPack | None = None
    request: SearchRequest | None = None


@dataclass(frozen=True, slots=True)
class RetrievalDecision:
    """Describes whether a turn should enter internet retrieval."""

    should_retrieve: bool
    retrieval_type: str
    confidence: str
    reason_code: str
    user_visible_reason: str
    explicit_request: bool
    requires_user_confirmation: bool
    search_query: str | None = None


@dataclass(frozen=True, slots=True)
class RetrievalTurnContext:
    """Summarises the most recent retrieval-backed turn for follow-ups."""

    topic: str
    original_user_message: str
    retrieval_status: str
    topic_signature: tuple[str, ...] = field(default_factory=tuple)
    retrieval_timestamp: datetime = field(default_factory=_utc_now)
    source_count: int | None = None
    result_count: int | None = None
    current_news_related: bool = False
    current_affairs_related: bool = False
    explicit_request: bool = False
    automatic_request: bool = False
