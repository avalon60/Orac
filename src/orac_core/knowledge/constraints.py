"""Extract and match bounded literal constraints for knowledge retrieval."""

# Author: Clive Bostock
# Date: 27-Sep-2026
# Description: Provides deterministic entity and identifier constraint handling.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

MAX_LITERAL_CONSTRAINTS = 4

_QUOTED = re.compile(r"(?:\"([^\"]{2,120})\"|‘([^’]{2,120})’|“([^”]{2,120})”)")
_POSSESSIVE = re.compile(
    r"\b([\w][\w.-]*(?:[ \t]+[\w][\w.-]*){1,4})[’']s\b",
    re.UNICODE,
)
_FILENAME = re.compile(r"\b[\w][\w .()\[\]-]{0,80}\.[A-Za-z0-9]{1,8}\b", re.UNICODE)
_VERSION = re.compile(r"\bv?\d+(?:\.\d+){1,4}(?:[-+][\w.-]+)?\b", re.IGNORECASE)
_IDENTIFIER = re.compile(
    r"(?<!\w)(?:[A-Za-z][\w]*[._/-][\w./-]+|[A-Za-z]+-\d[\w.-]*)(?!\w)",
    re.UNICODE,
)
_ACRONYM = re.compile(r"\b(?:[A-Z]{2,8}|(?:[A-Z]\.){2,8})\b")
_CONSERVATIVE_NAME = re.compile(
    r"\b([A-Za-z][\w.-]{1,30}(?:[ \t]+[A-Za-z][\w.-]{1,30}){1,3})\b",
    re.UNICODE,
)
_FILLER = frozenset(
    {
        "about", "can", "could", "do", "does", "explain", "for", "from", "i",
        "in", "me", "of", "on", "please", "say", "says", "tell", "the", "to",
        "what", "who", "with", "would", "you",
    }
)
_NAME_CONTEXT = frozenset(
    {"about", "does", "for", "from", "in", "on", "say", "says", "with"}
)


@dataclass(frozen=True, slots=True)
class LiteralConstraint:
    """One exact query constraint with a deterministic confidence class."""

    text: str
    normalized: str
    kind: str
    high_confidence: bool = True


def normalize_literal(value: str) -> str:
    """Return a Unicode- and punctuation-stable form for literal matching."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = normalized.replace("’", "'").replace("`", "'")
    return " ".join(normalized.split()).strip(" \t\r\n.,;:!?\"'()[]{}")


def extract_literal_constraints(
    query: str,
    *,
    limit: int = MAX_LITERAL_CONSTRAINTS,
) -> tuple[LiteralConstraint, ...]:
    """Extract at most ``limit`` ordered, distinct exact constraints.

    The extractor deliberately favours explicit punctuation and technical shape.
    Capitalisation alone is never sufficient for the conservative name fallback.
    """
    if limit <= 0:
        return ()
    found: list[LiteralConstraint] = []
    seen: set[str] = set()

    def add(raw: str, kind: str, *, high_confidence: bool = True) -> None:
        text = " ".join(raw.split()).strip()
        normalized = normalize_literal(text)
        if not normalized or normalized == "s" or normalized in seen:
            return
        if all(token in _FILLER for token in normalized.split()):
            return
        if any(
            normalized != existing
            and re.search(
                rf"(?<!\w){re.escape(normalized)}(?!\w)",
                existing,
                re.IGNORECASE,
            )
            for existing in seen
        ):
            return
        seen.add(normalized)
        found.append(LiteralConstraint(text, normalized, kind, high_confidence))

    for match in _QUOTED.finditer(query):
        add(next(group for group in match.groups() if group is not None), "quoted")
    for match in _POSSESSIVE.finditer(query):
        phrase = match.group(1)
        words = phrase.split()
        while words and words[0].casefold() in _FILLER:
            words.pop(0)
        if len(words) >= 2:
            add(" ".join(words), "possessive_name")
    for pattern, kind in (
        (_FILENAME, "filename"),
        (_VERSION, "version"),
        (_IDENTIFIER, "identifier"),
        (_ACRONYM, "acronym"),
    ):
        for match in pattern.finditer(query):
            add(match.group(0), kind)
    for match in _CONSERVATIVE_NAME.finditer(query):
        words = match.group(1).split()
        context_seen = False
        while words and words[0].casefold() in _FILLER:
            context_seen = words.pop(0).casefold() in _NAME_CONTEXT or context_seen
        lexical_shape = any(
            any(character in word for character in "-._/")
            or (word[:1].isupper() and word[1:].islower())
            for word in words
        )
        if len(words) >= 2 and context_seen and lexical_shape:
            add(" ".join(words), "multiword_name", high_confidence=False)
    return tuple(found[: min(limit, MAX_LITERAL_CONSTRAINTS)])


def literal_match_span(text: str, constraint: LiteralConstraint) -> tuple[int, int] | None:
    """Return the original-text span of a punctuation-tolerant literal match."""
    words = re.findall(r"\w+(?:[._/-]\w+)*", constraint.normalized, re.UNICODE)
    if not words:
        return None
    separator = r"(?:[\s\u00a0]+|[\s\u00a0]*['’._/-][\s\u00a0]*)"
    pattern = (
        r"(?<!\w)"
        + separator.join(re.escape(word) for word in words)
        + r"(?!\w)"
    )
    match = re.search(pattern, unicodedata.normalize("NFKC", text), re.IGNORECASE)
    return match.span() if match else None


def matched_literal_constraints(
    text: str,
    constraints: tuple[LiteralConstraint, ...],
) -> tuple[str, ...]:
    """Return normalized constraints actually present in ``text``."""
    return tuple(
        constraint.normalized
        for constraint in constraints
        if literal_match_span(text, constraint) is not None
    )


def general_lexical_terms(query: str) -> frozenset[str]:
    """Return useful non-filler query terms for topical-overlap checks."""
    return frozenset(
        token
        for token in re.findall(r"\w+(?:[._-]\w+)*", normalize_literal(query))
        if len(token) > 1 and token not in _FILLER and token != "s"
    )
