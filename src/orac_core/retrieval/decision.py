"""Retrieval decision heuristics for controlled internet access."""
# Author: Clive Bostock
# Date: 2026-05-26
# Description: Classifies prompts into explicit, suggested, auto-safe, or no retrieval.

from __future__ import annotations

from datetime import datetime
from datetime import timezone
import re
from dataclasses import dataclass
from typing import Any

from .broker import RetrievalSettings
from .models import RetrievalDecision
from .models import RetrievalTurnContext
from .triggers import detect_explicit_search_request

_ALLOWED_MODES = {"disabled", "explicit_only", "suggest_search", "auto_safe"}

_LOCAL_CONTEXT_MARKERS: tuple[str, ...] = (
    "my latest change",
    "my latest local change",
    "my latest idea",
    "latest local",
    "latest thing i tried",
    "latest message in this conversation",
    "latest test run output",
    "latest file i uploaded",
    "local change",
    "local config",
    "this repo",
    "this project",
    "this codebase",
    "this conversation",
    "this file",
    "in this repo",
    "in this project",
    "orac architecture",
    "orac plugin",
    "orac controller",
    "orac voice",
    "orac retrieval",
    "orac patch",
    "uploaded",
    "test run output",
)

_TOPIC_SIGNATURE_STOPWORDS: tuple[str, ...] = (
    "a",
    "about",
    "any",
    "are",
    "as",
    "another",
    "ceasefire",
    "could",
    "conflict",
    "current",
    "did",
    "detail",
    "details",
    "disaster",
    "disasters",
    "do",
    "election",
    "elections",
    "event",
    "events",
    "for",
    "from",
    "give",
    "health",
    "have",
    "happening",
    "how",
    "in",
    "is",
    "latest",
    "live",
    "market",
    "markets",
    "more",
    "news",
    "me",
    "of",
    "on",
    "or",
    "peace",
    "protest",
    "please",
    "protests",
    "recent",
    "new",
    "newest",
    "release",
    "regulation",
    "regulations",
    "sanction",
    "sanctions",
    "schedule",
    "score",
    "scores",
    "strike",
    "strikes",
    "say",
    "says",
    "show",
    "sort",
    "tell",
    "the",
    "that",
    "their",
    "this",
    "those",
    "today",
    "today's",
    "to",
    "try",
    "update",
    "updates",
    "up",
    "version",
    "war",
    "what",
    "what's",
    "whats",
    "when",
    "where",
    "which",
    "who",
    "why",
    "would",
    "you",
    "with",
    "now",
    "there",
)

_EXPLICIT_FRESHNESS_TRIGGER_PHRASES: tuple[str, ...] = (
    "is there any more detail in the latest news on",
    "is there any latest news on",
    "what is the latest news on",
    "what's the latest news on",
    "whats the latest news on",
    "what are the latest news on",
    "what is the latest",
    "what's the latest",
    "whats the latest",
    "what are the latest",
    "any latest news on",
    "latest news on",
    "latest news",
    "latest updates on",
    "latest update on",
    "latest updates",
    "latest update",
    "latest release of",
    "latest release",
    "latest version of",
    "latest version",
    "any news on",
    "any updates on",
    "any update on",
    "is there any update on",
    "is there any news on",
    "any more news on",
    "any more updates on",
    "more news on",
    "more updates on",
    "latest on",
)

_NEWS_TRIGGER_PHRASES: tuple[str, ...] = (
    "latest news",
    "current news",
    "breaking news",
    "latest updates",
    "live updates",
    "today's news",
    "news today",
    "what's happening now",
    "what is happening now",
)

_CURRENT_AFFAIRS_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("war", re.compile(r"\bwar\b", re.I)),
    ("conflict", re.compile(r"\bconflict\b", re.I)),
    ("invasion", re.compile(r"\binvasion\b", re.I)),
    ("strikes", re.compile(r"\bstrikes?\b", re.I)),
    ("ceasefire", re.compile(r"\bceasefire\b", re.I)),
    ("peace_talks", re.compile(r"\bpeace talks?\b", re.I)),
    ("sanctions", re.compile(r"\bsanctions?\b", re.I)),
    ("protests_unrest", re.compile(r"\bprotests?\b|\bunrest\b", re.I)),
    ("elections", re.compile(r"\belections?\b", re.I)),
    ("disasters", re.compile(r"\bdisasters?\b|\bearthquake\b|\bfloods?\b|\bhurricane\b|\bwildfires?\b", re.I)),
    ("public_health", re.compile(r"\bpublic health\b|\bpandemic\b|\boutbreak\b|\bemergency\b", re.I)),
    ("financial_shocks", re.compile(r"\bmarket shocks?\b|\bfinancial shocks?\b|\bstock market\b|\bmarket crash\b|\bcrash\b", re.I)),
    ("legal_regulatory", re.compile(r"\blegal\b|\bregulatory\b|\bregulation\b|\brulemaking\b|\bpolicy change\b", re.I)),
)

_FOLLOW_UP_PHRASES: tuple[str, ...] = (
    "more detail",
    "tell me more",
    "any more",
    "any updates",
    "latest news",
    "latest reports",
    "what else",
    "on that",
    "about that",
    "what happened next",
    "anything more recent",
    "what do the sources say",
)

_FOLLOW_UP_PRONOUN_MARKERS: tuple[str, ...] = (
    " that ",
    " this ",
    " it ",
    " those reports ",
    " these reports ",
)

_RETRIEVAL_CONTEXT_TTL_SECONDS = 6 * 60 * 60

_FRESHNESS_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "freshness_release_version",
        "That may have changed recently; I should check online.",
        re.compile(
            r"\b(?:latest|current|recent|newest|up to date|up-to-date)\b.*\b(?:release|version|build|patch|update)\b|\b(?:release|version|build|patch|update)\b.*\b(?:latest|current|recent|newest)\b",
            re.I,
        ),
    ),
    (
        "freshness_docs_api",
        "That may have changed recently; I should check online.",
        re.compile(
            r"\b(?:current|latest|recent)\b.*\b(?:docs?|documentation|api|sdk|supported|support|compatibility|behaviour|behavior)\b|\b(?:docs?|documentation|api|sdk|supported|support|compatibility|behaviour|behavior)\b.*\b(?:current|latest|recent)\b",
            re.I,
        ),
    ),
    (
        "freshness_price_availability",
        "That may have changed recently; I should check online.",
        re.compile(
            r"\b(?:price|pricing|cost|availability|available|in stock|stock|shipping|delivery)\b",
            re.I,
        ),
    ),
    (
        "freshness_news_events",
        "That may have changed recently; I should check online.",
        re.compile(
            r"\b(?:news|recent event|events?|announcement|announced|today|today's|this week|this month|breaking)\b",
            re.I,
        ),
    ),
    (
        "freshness_laws_rules",
        "That may have changed recently; I should check online.",
        re.compile(
            r"\b(?:current|latest|recent)\b.*\b(?:law|laws|regulation|regulations|rule|rules|policy|policies|legal)\b|\b(?:law|laws|regulation|regulations|rule|rules|policy|policies|legal)\b.*\b(?:current|latest|recent)\b",
            re.I,
        ),
    ),
    (
        "freshness_schedule_scores",
        "That may have changed recently; I should check online.",
        re.compile(
            r"\b(?:schedule|schedules|fixture|fixtures|score|scores|match|matches|game|games|kickoff|kick-off)\b",
            re.I,
        ),
    ),
    (
        "freshness_public_role",
        "That may have changed recently; I should check online.",
        re.compile(
            r"\b(?:who is|who's|current|latest|now)\b.*\b(?:ceo|president|minister|director|owner|chair|head|leader|role)\b|\b(?:ceo|president|minister|director|owner|chair|head|leader|role)\b.*\b(?:current|latest|now)\b",
            re.I,
        ),
    ),
    (
        "freshness_package_support",
        "That may have changed recently; I should check online.",
        re.compile(
            r"\b(?:package|library|tool|framework|module|dependency)\b.*\b(?:support|supported|compatibility|compatible|works with)\b|\b(?:support|supported|compatibility|compatible|works with)\b.*\b(?:package|library|tool|framework|module|dependency)\b",
            re.I,
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class _HeuristicMatch:
    """Internal heuristic match data."""

    reason_code: str
    user_visible_reason: str
    confidence: str
    retrieval_type: str = "internet"
    search_query: str | None = None
    requires_user_confirmation: bool = False


@dataclass(frozen=True, slots=True)
class _FollowUpMatch:
    """Internal follow-up match data."""

    reason_code: str
    search_query: str
    user_visible_reason: str
    confidence: str = "high"


class RetrievalDecisionService:
    """Classifies prompts into retrieval decisions using deterministic rules."""

    def __init__(self, *, settings: RetrievalSettings, logger: Any | None = None) -> None:
        """Initialise the retrieval decision service."""
        self._settings = settings
        self._logger = logger

    @property
    def settings(self) -> RetrievalSettings:
        """Return the configured retrieval settings."""
        return self._settings

    def decide(
        self,
        prompt: str,
        *,
        previous_context: RetrievalTurnContext | None = None,
    ) -> RetrievalDecision:
        """Return the retrieval decision for a single user turn."""
        normalized = " ".join(str(prompt or "").split())
        current_topic_signature = build_topic_signature(normalized)
        mode = normalize_internet_search_mode(self._settings.internet_search_mode)
        explicit_request = detect_explicit_search_request(
            normalized,
            max_results=self._settings.max_search_results,
            provider_name=self._settings.default_search_provider,
        )
        explicit_request_found = explicit_request is not None
        search_query = explicit_request.query if explicit_request is not None else normalized
        news_query = _match_current_news_request(normalized)
        current_affairs_reason = _match_current_affairs_request(normalized)
        follow_up_match = _classify_follow_up_request(
            normalized,
            previous_context,
            current_topic_signature=current_topic_signature,
        )

        if not normalized:
            decision = RetrievalDecision(
                should_retrieve=False,
                retrieval_type="none",
                confidence="low",
                reason_code="empty_prompt",
                user_visible_reason="",
                explicit_request=False,
                requires_user_confirmation=False,
                search_query=None,
            )
            self._log_decision(mode, decision)
            return decision

        if mode == "disabled":
            explicit_freshness_request = _is_explicit_freshness_request(explicit_request)
            current_like = (
                news_query is not None
                or current_affairs_reason is not None
                or follow_up_match is not None
                or explicit_freshness_request
                or _looks_fresh(normalized)
            )
            if (
                explicit_request_found
                or news_query is not None
                or current_affairs_reason is not None
                or follow_up_match is not None
                or _looks_fresh(normalized)
            ):
                decision = RetrievalDecision(
                    should_retrieve=False,
                    retrieval_type="internet",
                    confidence="high",
                    reason_code="disabled",
                    user_visible_reason=(
                        "Internet retrieval is disabled right now, so current information cannot be verified."
                        if current_like
                        or follow_up_match is not None
                        else "Internet retrieval is disabled right now."
                    ),
                    explicit_request=(
                        explicit_request_found
                        or news_query is not None
                        or follow_up_match is not None
                        or explicit_freshness_request
                    ),
                    requires_user_confirmation=False,
                    search_query=(
                        follow_up_match.search_query
                        if follow_up_match is not None
                        else search_query
                    ),
                )
            else:
                decision = RetrievalDecision(
                    should_retrieve=False,
                    retrieval_type="none",
                    confidence="low",
                    reason_code="disabled",
                    user_visible_reason="Internet retrieval is disabled right now.",
                    explicit_request=False,
                    requires_user_confirmation=False,
                    search_query=None,
                )
            self._log_decision(mode, decision)
            return decision

        if follow_up_match is not None:
            should_retrieve = mode in {"explicit_only", "suggest_search", "auto_safe"}
            decision = RetrievalDecision(
                should_retrieve=should_retrieve,
                retrieval_type="internet",
                confidence=follow_up_match.confidence,
                reason_code=follow_up_match.reason_code,
                user_visible_reason=(
                    "I’ll check the latest updates on that."
                    if should_retrieve
                    else "That may have changed recently; I should check online."
                ),
                explicit_request=False,
                requires_user_confirmation=False,
                search_query=follow_up_match.search_query,
            )
            self._log_decision(mode, decision)
            return decision

        if news_query is not None:
            should_retrieve = mode in {"explicit_only", "auto_safe"}
            decision = RetrievalDecision(
                should_retrieve=should_retrieve,
                retrieval_type="internet",
                confidence="high",
                reason_code="current_news_request",
                user_visible_reason=(
                    "I’ll check that online." if should_retrieve else "That may have changed recently; I should check online."
                ),
                explicit_request=True,
                requires_user_confirmation=mode == "suggest_search",
                search_query=news_query,
            )
            self._log_decision(mode, decision)
            return decision

        if explicit_request_found:
            explicit_freshness_request = _is_explicit_freshness_request(explicit_request)
            decision = RetrievalDecision(
                should_retrieve=True,
                retrieval_type="internet",
                confidence="high",
                reason_code=(
                    "explicit_freshness_request"
                    if explicit_freshness_request
                    else "explicit_request"
                ),
                user_visible_reason="I’ll check that online.",
                explicit_request=True,
                requires_user_confirmation=False,
                search_query=search_query,
            )
            self._log_decision(mode, decision)
            return decision

        if current_affairs_reason is not None:
            should_retrieve = mode == "auto_safe"
            decision = RetrievalDecision(
                should_retrieve=should_retrieve,
                retrieval_type="internet",
                confidence="high",
                reason_code=f"current_affairs_{current_affairs_reason}",
                user_visible_reason="That may have changed recently; I should check online.",
                explicit_request=False,
                requires_user_confirmation=mode in {"explicit_only", "suggest_search"},
                search_query=normalized,
            )
            self._log_decision(mode, decision)
            return decision

        match = _classify_freshness_sensitive(normalized)
        if match is not None:
            should_retrieve = mode == "auto_safe"
            requires_confirmation = mode in {"explicit_only", "suggest_search"}
            decision = RetrievalDecision(
                should_retrieve=should_retrieve,
                retrieval_type=match.retrieval_type,
                confidence=match.confidence,
                reason_code=match.reason_code,
                user_visible_reason=match.user_visible_reason,
                explicit_request=False,
                requires_user_confirmation=requires_confirmation,
                search_query=match.search_query or normalized,
            )
            self._log_decision(mode, decision)
            return decision

        if _looks_local(normalized):
            decision = RetrievalDecision(
                should_retrieve=False,
                retrieval_type="local",
                confidence="low",
                reason_code="local_project_context",
                user_visible_reason="",
                explicit_request=False,
                requires_user_confirmation=False,
                search_query=None,
            )
            self._log_decision(mode, decision)
            return decision

        decision = RetrievalDecision(
            should_retrieve=False,
            retrieval_type="none",
            confidence="low",
            reason_code="stable_general_knowledge",
            user_visible_reason="",
            explicit_request=False,
            requires_user_confirmation=False,
            search_query=None,
        )
        self._log_decision(mode, decision)
        return decision

    def _log_decision(self, mode: str, decision: RetrievalDecision) -> None:
        """Log a compact decision summary for observability."""
        message = (
            "Retrieval decision: "
            f"mode={mode} "
            f"should_retrieve={decision.should_retrieve} "
            f"confidence={decision.confidence} "
            f"reason={decision.reason_code} "
            f"explicit_request={decision.explicit_request} "
            f"confirmation_required={decision.requires_user_confirmation} "
            f"type={decision.retrieval_type}"
        )
        log_debug = getattr(self._logger, "log_debug", None)
        if callable(log_debug):
            log_debug(message)


def normalize_internet_search_mode(value: str | None) -> str:
    """Return a supported internet-search mode."""
    normalized = str(value or "explicit_only").strip().lower()
    return normalized if normalized in _ALLOWED_MODES else "explicit_only"


def _classify_freshness_sensitive(prompt: str) -> _HeuristicMatch | None:
    """Return a high-confidence match for freshness-sensitive queries."""
    lowered = str(prompt or "").lower()
    if _looks_local(lowered):
        return None
    for reason_code, user_visible_reason, pattern in _FRESHNESS_PATTERNS:
        if pattern.search(lowered) is None:
            continue
        return _HeuristicMatch(
            reason_code=reason_code,
            user_visible_reason=user_visible_reason,
            confidence="high",
            retrieval_type="internet",
            search_query=prompt,
        )
    return None


def _classify_follow_up_request(
    prompt: str,
    previous_context: RetrievalTurnContext | None,
    *,
    current_topic_signature: tuple[str, ...] = (),
) -> _FollowUpMatch | None:
    """Return a follow-up match when the prompt refers to a recent retrieval."""
    if previous_context is None:
        return None
    if not _is_recent_context(previous_context):
        return None

    previous_signature = _topic_signature_from_context(previous_context)
    if (
        current_topic_signature
        and previous_signature
        and not topic_signature_overlap(current_topic_signature, previous_signature)
    ):
        return None

    lowered = f" {str(prompt or '').lower()} "
    has_follow_up_phrase = any(phrase in lowered for phrase in _FOLLOW_UP_PHRASES)
    has_pronoun_reference = any(marker in lowered for marker in _FOLLOW_UP_PRONOUN_MARKERS)
    has_current_news_language = _match_current_news_request(prompt) is not None
    has_current_affairs_language = _match_current_affairs_request(prompt) is not None
    if not (has_follow_up_phrase or has_pronoun_reference or has_current_news_language or has_current_affairs_language):
        return None

    topic = str(previous_context.topic or "").strip() or str(previous_context.original_user_message or "").strip()
    if not topic:
        return None

    return _FollowUpMatch(
        reason_code="retrieval_follow_up",
        search_query=topic,
        user_visible_reason="I’ll check the latest updates on that.",
    )


def _match_current_news_request(prompt: str) -> str | None:
    """Return a query fragment when the prompt is a current-news request."""
    lowered = str(prompt or "").lower()
    original = str(prompt or "")
    for phrase in _NEWS_TRIGGER_PHRASES:
        index = lowered.find(phrase)
        if index < 0:
            continue
        remainder = original[index + len(phrase):].lstrip(" ,;:-")
        remainder = re.sub(r"^(?:on|about|for|regarding)\s+", "", remainder, flags=re.I)
        cleaned = " ".join(remainder.split()).strip(" .?!:-,;")
        return cleaned or original.strip(" .?!:-,;")
    return None


def _match_current_affairs_request(prompt: str) -> str | None:
    """Return a current-affairs category identifier when relevant."""
    lowered = str(prompt or "").lower()
    if not lowered.strip():
        return None
    for reason_code, pattern in _CURRENT_AFFAIRS_PATTERNS:
        if pattern.search(lowered) is None:
            continue
        return reason_code
    return None


def _is_recent_context(previous_context: RetrievalTurnContext) -> bool:
    """Return whether the prior retrieval context is recent enough to reuse."""
    created_at = previous_context.retrieval_timestamp
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age_seconds = (datetime.now(timezone.utc) - created_at.astimezone(timezone.utc)).total_seconds()
    return age_seconds <= _RETRIEVAL_CONTEXT_TTL_SECONDS


def _looks_local(prompt: str) -> bool:
    """Return whether the query is about local project context."""
    lowered = str(prompt or "").lower()
    return any(marker in lowered for marker in _LOCAL_CONTEXT_MARKERS)


def _looks_fresh(prompt: str) -> bool:
    """Return whether the prompt looks freshness-sensitive."""
    return _classify_freshness_sensitive(prompt) is not None


def _is_explicit_freshness_request(explicit_request: Any | None) -> bool:
    """Return whether a detected explicit request is freshness-oriented."""
    trigger_phrase = str(getattr(explicit_request, "trigger_phrase", "") or "").strip().lower()
    return trigger_phrase in _EXPLICIT_FRESHNESS_TRIGGER_PHRASES


def build_topic_signature(text: str) -> tuple[str, ...]:
    """Return a lightweight signature for a retrieval topic."""
    normalized = " ".join(str(text or "").lower().split())
    if not normalized:
        return ()

    signature: list[str] = []
    tokens = re.findall(r"[a-z0-9]+(?:[-/][a-z0-9]+)*", normalized)
    for token in tokens:
        parts = [part for part in re.split(r"[-/]", token) if part]
        candidates = [token, *parts] if len(parts) > 1 else [token]
        for candidate in candidates:
            if len(candidate) < 2:
                continue
            if candidate in _TOPIC_SIGNATURE_STOPWORDS:
                continue
            if candidate.isdigit():
                continue
            if candidate not in signature:
                signature.append(candidate)
    return tuple(signature)


def topic_signature_overlap(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    """Return the number of shared topic-signature terms."""
    return len(set(left).intersection(right))


def topic_signatures_related(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    """Return whether two retrieval topics appear to describe the same subject."""
    if not left or not right:
        return True
    return topic_signature_overlap(left, right) > 0


def _topic_signature_from_context(previous_context: RetrievalTurnContext) -> tuple[str, ...]:
    """Return the strongest available topic signature for a prior context."""
    signature = tuple(getattr(previous_context, "topic_signature", ()) or ())
    if signature:
        return signature
    return build_topic_signature(
        str(previous_context.topic or previous_context.original_user_message or "")
    )
