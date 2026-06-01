"""Explicit search trigger detection for internet retrieval."""
# Author: Clive Bostock
# Date: 2026-05-26
# Description: Detects direct user requests that should enter retrieval mode.

from __future__ import annotations

import re

from .models import SearchRequest


_OPTIONAL_POLITE_PREFIX = r"(?:please\s+)?"

_DIRECT_TRIGGER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "search the web for",
        re.compile(rf"^\s*{_OPTIONAL_POLITE_PREFIX}search(?: the)? web for\s+(?P<query>.+)$", re.I),
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

_TRAILING_TRIGGER_PATTERN = re.compile(
    r"(?:[,.;:?!]\s*)?(?P<trigger>search(?: the)? (?:internet|web|online)|check online|look (?:it|this) up online)\??\s*$",
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


def _clean_query(query: str) -> str:
    """Normalise a trigger-derived search query."""
    cleaned = re.sub(r"^(?:question|q)\s*:\s*", "", str(query or "").strip(), flags=re.I)
    return " ".join(cleaned.strip(" .?!:-,;").split())
