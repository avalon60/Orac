"""Deterministic factual-risk detection for retrieval gating."""
# Author: Clive Bostock
# Date: 02-Jun-2026
# Description: Detects high-risk factual prompts that must be verified.

from __future__ import annotations

from dataclasses import dataclass
import re

from .person_status import is_stable_historical_person


@dataclass(frozen=True, slots=True)
class FactualRiskMatch:
    """Describes a high-risk factual prompt requiring retrieval."""

    reason_code: str
    search_query: str
    confidence: str = "high"


_LOCAL_CONTEXT_MARKERS: tuple[str, ...] = (
    "this repo",
    "this project",
    "this codebase",
    "this conversation",
    "this file",
    "local change",
    "local config",
    "orac patch",
    "patch you just made",
    "test failure",
)

_FILLER_PREFIX_PATTERN = re.compile(
    r"^(?:please\s+)?(?:can you\s+|could you\s+|would you\s+)?",
    re.I,
)

_PERSON_DEATH_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "factual_risk_cause_of_death",
        re.compile(r"^\s*what did (?P<subject>.+?) die of\??\s*$", re.I),
        "{subject} cause of death",
    ),
    (
        "factual_risk_cause_of_death",
        re.compile(r"^\s*how did (?P<subject>.+?) (?:die|pass away)\??\s*$", re.I),
        "{subject} cause of death",
    ),
    (
        "factual_risk_cause_of_death",
        re.compile(r"^\s*(?P<subject>.+?) cause of death\??\s*$", re.I),
        "{subject} cause of death",
    ),
    (
        "factual_risk_cause_of_death",
        re.compile(r"^\s*(?:what was )?(?:the )?cause of death of (?P<subject>.+?)\??\s*$", re.I),
        "{subject} cause of death",
    ),
    (
        "factual_risk_date_of_death",
        re.compile(r"^\s*(?:the\s+)?(?:death|obituary) of (?P<subject>.+?)\??\s*$", re.I),
        "{subject} death obituary",
    ),
    (
        "factual_risk_date_of_death",
        re.compile(r"^\s*when did (?P<subject>.+?) (?:die|pass away)\??\s*$", re.I),
        "{subject} date of death",
    ),
    (
        "factual_risk_date_of_death",
        re.compile(r"^\s*(?P<subject>.+?) (?:death|died|obituary|date of death)\??\s*$", re.I),
        "{subject} death obituary",
    ),
    (
        "factual_risk_alive_status",
        re.compile(r"^\s*(?:is|was|did|has) (?P<subject>.+?) (?:dead|die|died|passed away)\??\s*$", re.I),
        "{subject} alive dead status",
    ),
)

_PERSON_AGE_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "factual_risk_person_age",
        re.compile(r"^\s*how old (?:is|was) (?P<subject>.+?)\??\s*$", re.I),
        "{subject} age date of birth date of death",
    ),
    (
        "factual_risk_person_age",
        re.compile(r"^\s*(?P<subject>.+?) age\??\s*$", re.I),
        "{subject} age date of birth date of death",
    ),
    (
        "factual_risk_person_age",
        re.compile(r"^\s*when was (?P<subject>.+?) born\??\s*$", re.I),
        "{subject} date of birth date of death",
    ),
    (
        "factual_risk_person_age",
        re.compile(r"^\s*(?P<subject>.+?) date of birth\??\s*$", re.I),
        "{subject} date of birth date of death",
    ),
)

_QUESTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "factual_risk_current_role",
        re.compile(
            r"\b(?:who is|who's|who owns|current|latest|new|now)\b.*\b(?:ceo|cto|cfo|president|prime minister|minister|director|owner|chair|head|leader|manager|office holder|role)\b",
            re.I,
        ),
    ),
    (
        "factual_risk_price_availability",
        re.compile(
            r"\b(?:how much|price|pricing|cost|available|availability|in stock|still available|can i still buy|can i still purchase)\b",
            re.I,
        ),
    ),
    (
        "factual_risk_law_policy",
        re.compile(
            r"\b(?:current|latest|today|now|still)\b.*\b(?:law|laws|rule|rules|regulation|regulations|policy|policies|tax|allowance|threshold|capital gains|vat|hmrc)\b|\b(?:tax|allowance|threshold|capital gains|vat|hmrc)\b|\b(?:law|laws|rules?|regulations?|policies)\b.*\b(?:current|latest|today|now|still)\b",
            re.I,
        ),
    ),
    (
        "factual_risk_medical_legal_financial",
        re.compile(
            r"\b(?:medical|medicine|diagnosis|treatment|symptoms?|legal|lawyer|solicitor|financial|finance|investment|mortgage|pension|tax advice|safety|dangerous|safe to)\b",
            re.I,
        ),
    ),
    (
        "factual_risk_current_latest",
        re.compile(
            r"\b(?:current|latest|today|now|recent|still|newest)\b.*\b(?:version|release|available|availability|price|role|office|holder|model|package|ollama|ords)\b|\b(?:version|release|available|availability|price|role|office|holder|model|package|ollama|ords)\b.*\b(?:current|latest|today|now|recent|still|newest)\b",
            re.I,
        ),
    ),
)


def should_force_retrieval(user_query: str) -> bool:
    """Return whether a prompt must be verified by retrieval before answering."""
    return detect_factual_risk(user_query) is not None


def detect_factual_risk(user_query: str) -> FactualRiskMatch | None:
    """Return a factual-risk match when model memory should not be trusted."""
    normalized = " ".join(str(user_query or "").split()).strip()
    if not normalized:
        return None
    if _looks_local(normalized):
        return None

    for reason_code, pattern, template in (*_PERSON_DEATH_PATTERNS, *_PERSON_AGE_PATTERNS):
        match = pattern.match(normalized)
        if match is None:
            continue
        subject = _clean_subject(match.group("subject"))
        if not subject:
            continue
        if is_stable_historical_person(subject):
            return None
        return FactualRiskMatch(
            reason_code=reason_code,
            search_query=_clean_query(template.format(subject=subject)),
        )

    for reason_code, pattern in _QUESTION_PATTERNS:
        if pattern.search(normalized) is None:
            continue
        return FactualRiskMatch(
            reason_code=reason_code,
            search_query=_build_general_search_query(normalized, reason_code),
        )

    return None


def _build_general_search_query(prompt: str, reason_code: str) -> str:
    """Return a compact search query for a factual-risk prompt."""
    cleaned = _clean_query(prompt)
    lowered = cleaned.lower()
    current_match = re.match(
        r"^(?:what(?:'s| is)?|which is|name)\s+(?:the\s+)?(?P<topic>(?:current|latest|newest)\s+.+)$",
        cleaned,
        re.I,
    )
    if current_match is not None:
        return _clean_query(current_match.group("topic"))
    if reason_code == "factual_risk_current_role" and "current" not in lowered:
        return f"current {cleaned}"
    if reason_code == "factual_risk_price_availability" and not re.search(
        r"\b(?:price|cost|availability|available)\b",
        lowered,
    ):
        return f"{cleaned} price availability"
    return cleaned


def _clean_subject(value: str) -> str:
    """Clean a person/entity subject extracted from a prompt."""
    cleaned = _FILLER_PREFIX_PATTERN.sub("", str(value or "").strip())
    cleaned = re.sub(r"^(?:the|a|an)\s+", "", cleaned, flags=re.I)
    return _clean_query(cleaned)


def _clean_query(value: str) -> str:
    """Normalise a generated search query."""
    cleaned = str(value or "").strip(" .?!:-,;")
    return " ".join(cleaned.split())


def _looks_local(prompt: str) -> bool:
    """Return whether the prompt refers to local project/conversation state."""
    lowered = f" {str(prompt or '').lower()} "
    return any(marker in lowered for marker in _LOCAL_CONTEXT_MARKERS)
