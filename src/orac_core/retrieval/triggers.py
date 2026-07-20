"""Explicit search trigger detection for internet retrieval."""
# Author: Clive Bostock
# Date: 2026-05-26
# Description: Detects direct user requests that should enter retrieval mode.

from __future__ import annotations

import re

from .models import SearchRequest


_OPTIONAL_POLITE_PREFIX = r"(?:please\s+)?"

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
    "orac's plugin",
    "orac controller",
    "orac voice",
    "orac retrieval",
    "orac patch",
    "patch you just made",
    "test failure",
    "uploaded",
    "test run output",
)

_DIRECT_TRIGGER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "search the web for",
        re.compile(rf"^\s*{_OPTIONAL_POLITE_PREFIX}search(?: the)? web for\s+(?P<query>.+)$", re.I),
    ),
    (
        "do an internet search for",
        re.compile(rf"^\s*{_OPTIONAL_POLITE_PREFIX}do an internet search for\s+(?P<query>.+)$", re.I),
    ),
    (
        "search online for",
        re.compile(rf"^\s*{_OPTIONAL_POLITE_PREFIX}search(?: the)? online for\s+(?P<query>.+)$", re.I),
    ),
    (
        "search the internet for",
        re.compile(rf"^\s*{_OPTIONAL_POLITE_PREFIX}search(?: the)? internet for\s+(?P<query>.+)$", re.I),
    ),
    ("look up", re.compile(r"^\s*look up\s+(?P<query>.+)$", re.I)),
    ("check online for", re.compile(r"^\s*check online(?: for)?\s+(?P<query>.+)$", re.I)),
    ("find online for", re.compile(r"^\s*find online(?: for)?\s+(?P<query>.+)$", re.I)),
)

_LATEST_TRIGGER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "latest",
        re.compile(
            r"^\s*(?:latest|what(?:'s| is) the latest(?: on| about)?|what is new on|what's new on)\s+(?P<query>.+)$",
            re.I,
        ),
    ),
    (
        "latest",
        re.compile(
            r"^\s*(?:what(?:'s| is)|which is|name)\s+(?P<query>.+\blatest\b.+)$",
            re.I,
        ),
    ),
)

_NATURAL_FRESHNESS_TRIGGER_PREFIXES: tuple[str, ...] = (
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

_TRAILING_TRIGGER_PATTERN = re.compile(
    r"(?:[,.;:?!]\s*)?(?P<trigger>search(?: the)? (?:internet|web|online)|check online|look (?:it|this) up online)[.?!]?\s*$",
    re.I,
)


def detect_explicit_search_request(
    prompt: str,
    *,
    max_results: int = 5,
    provider_name: str | None = None,
) -> SearchRequest | None:
    """Return a search request when the prompt clearly asks for web retrieval."""
    normalized = " ".join(str(prompt or "").split())
    if not normalized:
        return None
    if _looks_local(normalized):
        return None

    for trigger_phrase, pattern in _DIRECT_TRIGGER_PATTERNS:
        match = pattern.match(normalized)
        if match is None:
            continue
        query = _clean_query(match.group("query"))
        if not query:
            return None
        return SearchRequest(
            query=query,
            max_results=max_results,
            provider_name=provider_name,
            trigger_phrase=trigger_phrase,
        )

    trailing_match = _TRAILING_TRIGGER_PATTERN.search(normalized)
    if trailing_match is not None:
        query = _clean_query(normalized[: trailing_match.start()])
        if not query:
            return None
        return SearchRequest(
            query=query,
            max_results=max_results,
            provider_name=provider_name,
            trigger_phrase=trailing_match.group("trigger").lower(),
        )

    natural_freshness_request = _match_natural_freshness_request(
        normalized,
        max_results=max_results,
        provider_name=provider_name,
    )
    if natural_freshness_request is not None:
        return natural_freshness_request

    for trigger_phrase, pattern in _LATEST_TRIGGER_PATTERNS:
        match = pattern.match(normalized)
        if match is None:
            continue
        query = _clean_query(match.group("query"))
        if not query:
            return None
        return SearchRequest(
            query=query,
            max_results=max_results,
            provider_name=provider_name,
            trigger_phrase=trigger_phrase,
        )
    return None


def detect_explicit_search_directive(
    prompt: str,
    *,
    max_results: int = 5,
    provider_name: str | None = None,
) -> SearchRequest | None:
    """Return only an explicit user command selecting internet retrieval."""
    normalized = " ".join(str(prompt or "").split())
    if not normalized or _looks_local(normalized):
        return None
    for trigger_phrase, pattern in _DIRECT_TRIGGER_PATTERNS:
        match = pattern.match(normalized)
        if match is None:
            continue
        query = _clean_query(match.group("query"))
        if query:
            return SearchRequest(
                query=query,
                max_results=max_results,
                provider_name=provider_name,
                trigger_phrase=trigger_phrase,
            )
    trailing_match = _TRAILING_TRIGGER_PATTERN.search(normalized)
    if trailing_match is None:
        return None
    query = _clean_query(normalized[: trailing_match.start()])
    if not query:
        return None
    return SearchRequest(
        query=query,
        max_results=max_results,
        provider_name=provider_name,
        trigger_phrase=trailing_match.group("trigger").lower(),
    )


def _clean_query(query: str) -> str:
    """Normalise a trigger-derived search query."""
    cleaned = re.sub(r"^(?:question|q)\s*:\s*", "", str(query or "").strip(), flags=re.I)
    return " ".join(cleaned.strip(" .?!:-,;").split())


def _match_natural_freshness_request(
    prompt: str,
    *,
    max_results: int,
    provider_name: str | None,
) -> SearchRequest | None:
    """Return a search request for explicit freshness wording."""
    normalized = " ".join(str(prompt or "").split())
    lowered = normalized.lower()
    for trigger_phrase in _NATURAL_FRESHNESS_TRIGGER_PREFIXES:
        if not lowered.startswith(trigger_phrase):
            continue
        boundary_index = len(trigger_phrase)
        if len(lowered) > boundary_index and lowered[boundary_index] not in " \t,.;:!?-":
            continue
        query = normalized[boundary_index:].lstrip(" \t,.;:!?-")
        query = re.sub(r"^(?:on|about|for|regarding|of|in)\s+", "", query, flags=re.I)
        cleaned_query = _clean_query(query) or _clean_query(normalized)
        if not cleaned_query:
            continue
        return SearchRequest(
            query=cleaned_query,
            max_results=max_results,
            provider_name=provider_name,
            trigger_phrase=trigger_phrase,
        )
    return None


def _looks_local(prompt: str) -> bool:
    """Return whether the prompt is about local project or conversation context."""
    lowered = f" {str(prompt or '').lower()} "
    return any(marker in lowered for marker in _LOCAL_CONTEXT_MARKERS)
