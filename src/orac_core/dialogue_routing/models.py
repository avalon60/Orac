"""Typed contracts for observable normal-dialogue route selection."""

# Author: Clive Bostock
# Date: 18-Jul-2026
# Description: Defines route evidence independently from retrieval and execution.

from __future__ import annotations

from dataclasses import dataclass

from orac_core.knowledge.scope import KnowledgeScope
from orac_core.retrieval.models import SearchRequest


@dataclass(frozen=True, slots=True)
class DialogueRouteDecision:
    """One deterministic, testable route-selection outcome."""

    route_type: str
    reason_codes: tuple[str, ...]
    knowledge_scopes: tuple[KnowledgeScope, ...] = ()
    external_search_request: SearchRequest | None = None
    fallback_reason: str | None = None
    user_visible_message: str | None = None
