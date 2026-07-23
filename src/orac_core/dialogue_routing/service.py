"""Select explicit internet and authorised local-knowledge dialogue routes."""

# Author: Clive Bostock
# Date: 18-Jul-2026
# Description: Applies explicit route controls and canonical knowledge scope resolution.

from __future__ import annotations

import re

from orac_core.knowledge.scope import KnowledgeScopeAuthorizer
from orac_core.retrieval import detect_explicit_search_directive

from .models import DialogueRouteDecision

_KNOWLEDGE_QUESTION = re.compile(
    r"\b(?:how|what|where|why|when|which|configure|configuration|document|"
    r"documentation|guardrail|decision|decided|processing profile)\b",
    re.IGNORECASE,
)
_EXPLICIT_NAMED_KNOWLEDGE_SOURCE = re.compile(
    r"\b(?:use|search|query|consult)\s+(?:the\s+)?"
    r"(?P<name>[a-z0-9][a-z0-9 ._:-]{0,80}?)\s+knowledge\s+"
    r"(?:base|source)\b",
    re.IGNORECASE,
)
_EXPLICIT_UNNAMED_KNOWLEDGE_SOURCE = re.compile(
    r"\b(?:use|search|query|consult)\s+(?:the\s+)?knowledge\s+" r"(?:base|source)\b",
    re.IGNORECASE,
)

_KNOWLEDGE_DENIED_MESSAGE = "I can’t use that knowledge source for this user."
_KNOWLEDGE_UNAVAILABLE_MESSAGE = "That knowledge source is unavailable right now."


class DialogueRoutingService:
    """Resolve route-selection controls without performing side effects."""

    def __init__(self, *, scope_authorizer: KnowledgeScopeAuthorizer) -> None:
        """Initialise routing with the canonical scope authority."""
        self._scope_authorizer = scope_authorizer

    def explicit_route(self, prompt: str) -> DialogueRouteDecision | None:
        """Return a user-selected internet route before plugin interception."""
        request = detect_explicit_search_directive(prompt)
        if request is None:
            return None
        return DialogueRouteDecision(
            route_type="internet",
            reason_codes=("explicit_internet_route_directive",),
            external_search_request=request,
        )

    def knowledge_route(
        self,
        prompt: str,
        *,
        authenticated_username: str,
    ) -> DialogueRouteDecision | None:
        """Resolve an explicit or aliased knowledge source without fallthrough."""
        lowered = prompt.casefold()
        unnamed_match = _EXPLICIT_UNNAMED_KNOWLEDGE_SOURCE.search(prompt)
        named_match = (
            None
            if unnamed_match is not None
            else _EXPLICIT_NAMED_KNOWLEDGE_SOURCE.search(prompt)
        )
        explicit_knowledge_request = named_match is not None
        requested: tuple[str, ...]
        if named_match is not None:
            requested = (named_match.group("name").strip(),)
        elif unnamed_match is not None:
            explicit_knowledge_request = True
            requested = ()
        elif _KNOWLEDGE_QUESTION.search(prompt) is not None:
            requested = tuple(
                alias
                for alias in sorted(
                    self._scope_authorizer.aliases,
                    key=len,
                    reverse=True,
                )
                if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", lowered)
            )
        else:
            requested = ()
        if not requested and not explicit_knowledge_request:
            return None
        resolution = self._scope_authorizer.resolve_for_user(
            authenticated_username,
            requested,
        )
        if resolution.status != "authorised":
            route_type, message = self._terminal_mapping(resolution.reason_code)
            return DialogueRouteDecision(
                route_type=route_type,
                reason_codes=(resolution.reason_code,),
                fallback_reason=resolution.reason_code,
                user_visible_message=message,
            )
        return DialogueRouteDecision(
            route_type="knowledge",
            reason_codes=(resolution.reason_code,),
            knowledge_scopes=resolution.scopes,
        )

    def explicit_knowledge_route(
        self,
        prompt: str,
        *,
        authenticated_username: str,
    ) -> DialogueRouteDecision | None:
        """Resolve only explicit knowledge-source syntax before plugin routing."""
        if (
            _EXPLICIT_NAMED_KNOWLEDGE_SOURCE.search(prompt) is None
            and _EXPLICIT_UNNAMED_KNOWLEDGE_SOURCE.search(prompt) is None
        ):
            return None
        return self.knowledge_route(
            prompt,
            authenticated_username=authenticated_username,
        )

    def _terminal_mapping(self, reason_code: str) -> tuple[str, str]:
        """Map scope failures to safe terminal routes and user-facing text."""
        if reason_code in {
            "RAG_USAGE_NOT_GRANTED",
            "RAG_USAGE_EXPIRED",
            "RAG_USAGE_PRINCIPAL_UNKNOWN",
            "RAG_USAGE_PRINCIPAL_INACTIVE",
        }:
            return "knowledge_denied", _KNOWLEDGE_DENIED_MESSAGE
        if reason_code in {
            "knowledge_scope_inactive",
            "scope_registry_unavailable",
            "RAG_USAGE_SCOPE_INACTIVE",
            "RAG_USAGE_SCOPE_INELIGIBLE",
            "RAG_USAGE_AUTHORIZATION_UNAVAILABLE",
        }:
            return "knowledge_unavailable", _KNOWLEDGE_UNAVAILABLE_MESSAGE
        if reason_code == "knowledge_scope_limit_exceeded":
            return (
                "clarification",
                "Please narrow the request to at most "
                f"{self._scope_authorizer.max_scopes_per_request} authorised "
                "knowledge scopes.",
            )
        if reason_code == "knowledge_scope_required":
            return "clarification", "Which authorised knowledge scope should I use?"
        return (
            "clarification",
            "Which authorised project or plugin knowledge source should I use?",
        )
