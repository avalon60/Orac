"""Deterministic parsing helpers for titled-work factual questions."""
# Author: Clive Bostock
# Date: 05-Jun-2026
# Description: Preserves suspected song, album, film, and book titles for retrieval.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re
from urllib.parse import urlparse


_WORK_TYPE_ALIASES: dict[str, str] = {
    "song": "song",
    "track": "song",
    "single": "song",
    "album": "album",
    "film": "film",
    "movie": "film",
    "book": "book",
    "novel": "book",
    "play": "play",
    "poem": "poem",
}
_WORK_TYPE_PATTERN = re.compile(
    r"\b(?P<work_type>song|track|single|album|film|movie|book|novel|play|poem)\s+"
    r"(?P<title>[^?]+?)\s*\??$",
    re.I,
)
_QUESTION_PATTERN = re.compile(
    r"^\s*(?:who|which|what|when|where|did|was|is|were|are|name)\b",
    re.I,
)
_TERMINAL_AMBIGUOUS_WORDS = {"first"}


@dataclass(frozen=True, slots=True)
class TitledWorkQuery:
    """Represents exact-title candidates extracted from a work question."""

    work_type: str
    user_provided_title: str
    title_candidates: tuple[str, ...]
    question_text: str
    claim_artist: str | None = None
    claim_album: str | None = None
    correction_negation: bool = False


@dataclass(frozen=True, slots=True)
class TitleCandidateResolution:
    """Represents source support for one exact titled-work candidate."""

    candidate_title: str
    source_support_found: bool
    supported_artist: str | None = None
    supported_album: str | None = None
    supported_year: str | None = None
    confidence: str = "low"
    evidence_urls: tuple[str, ...] = ()
    evidence_source_types: tuple[str, ...] = ()

    def as_metadata(self) -> dict[str, Any]:
        """Return a JSON-friendly representation for retrieval metadata."""
        return {
            "candidate_title": self.candidate_title,
            "source_support_found": self.source_support_found,
            "supported_artist": self.supported_artist,
            "supported_album": self.supported_album,
            "supported_year": self.supported_year,
            "confidence": self.confidence,
            "evidence_urls": self.evidence_urls,
            "evidence_source_types": self.evidence_source_types,
        }


_MUSIC_SOURCE_CONFIDENCE: tuple[tuple[str, str], ...] = (
    ("musicbrainz.org", "structured"),
    ("discogs.com", "structured"),
    ("wikidata.org", "structured"),
    ("wikipedia.org", "secondary"),
)
_LOW_CONFIDENCE_MUSIC_DOMAINS: tuple[str, ...] = (
    "azlyrics.com",
    "genius.com",
    "songfacts.com",
    "lyrics.com",
    "last.fm",
)


def parse_titled_work_question(prompt: str) -> TitledWorkQuery | None:
    """Return exact titled-work candidates for a factual work question.

    Args:
        prompt: Raw user prompt.

    Returns:
        A parsed titled-work query, or ``None`` when the prompt is not a
        supported titled-work factual question.
    """
    normalized = " ".join(str(prompt or "").split()).strip()
    if not normalized:
        return None

    parsed = _parse_question_work(normalized) or _parse_called_work(normalized) or _parse_record_claim(normalized)
    if parsed is None:
        return None

    work_type, raw_title, claim_artist, claim_album, correction_negation = parsed
    raw_title = _canonical_terminal_title(_clean_title(raw_title))
    if not raw_title:
        return None

    candidates = _title_candidates(raw_title, work_type=work_type, question_text=normalized)
    if not candidates:
        return None

    return TitledWorkQuery(
        work_type=work_type,
        user_provided_title=raw_title,
        title_candidates=candidates,
        question_text=normalized,
        claim_artist=claim_artist,
        claim_album=claim_album,
        correction_negation=correction_negation,
    )


def build_titled_work_search_query(query: TitledWorkQuery) -> str:
    """Build a search query that preserves exact title candidates."""
    quoted_titles = " OR ".join(f'"{title}"' for title in query.title_candidates)
    qualifiers = _question_qualifiers(query.question_text, work_type=query.work_type)
    suffix = " ".join(part for part in (query.work_type, qualifiers) if part)
    return " ".join(part for part in (quoted_titles, suffix) if part).strip()


def build_titled_work_query_variants(query: TitledWorkQuery) -> tuple[str, ...]:
    """Return one exact-title search query for each candidate parse."""
    qualifiers = _question_qualifiers(query.question_text, work_type=query.work_type)
    suffix = " ".join(part for part in (query.work_type, qualifiers) if part)
    return tuple(
        " ".join(part for part in (f'"{title}"', suffix) if part).strip()
        for title in query.title_candidates
    )


def titled_work_text_matches(text: str, title_candidates: tuple[str, ...]) -> bool:
    """Return whether text contains one of the exact title candidates."""
    normalized_text = _normalise_title_for_match(text)
    if not normalized_text:
        return False
    return any(
        _normalise_title_for_match(title) in normalized_text
        for title in title_candidates
        if _normalise_title_for_match(title)
    )


def music_source_type(url: str, source_name: str = "") -> str:
    """Return a coarse confidence type for a music evidence source.

    Args:
        url: Source URL.
        source_name: Optional provider/source label.

    Returns:
        One of ``structured``, ``secondary``, ``official``, ``low``, or
        ``unknown``.
    """
    combined = f"{url} {source_name}".lower()
    host = urlparse(str(url or "")).netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    for domain, source_type in _MUSIC_SOURCE_CONFIDENCE:
        if domain in host or domain in combined:
            return source_type
    if any(domain in host or domain in combined for domain in _LOW_CONFIDENCE_MUSIC_DOMAINS):
        return "low"
    if re.search(r"\bofficial\b", combined):
        return "official"
    return "unknown"


def is_reliable_music_source(url: str, source_name: str = "") -> bool:
    """Return whether a source is acceptable for music factual grounding."""
    return music_source_type(url, source_name) in {"structured", "official", "secondary"}


def _parse_question_work(
    normalized: str,
) -> tuple[str, str, str | None, str | None, bool] | None:
    """Parse direct titled-work questions."""
    if _QUESTION_PATTERN.search(normalized) is None:
        return None
    match = _WORK_TYPE_PATTERN.search(normalized)
    if match is None:
        return None
    return (
        _WORK_TYPE_ALIASES[match.group("work_type").lower()],
        match.group("title"),
        None,
        None,
        False,
    )


def _parse_called_work(
    normalized: str,
) -> tuple[str, str, str | None, str | None, bool] | None:
    """Parse correction statements such as ``song called X``."""
    pattern = re.compile(
        r"^(?P<artist>.+?)\s+"
        r"(?P<negation>never\s+recorded|did\s+not\s+record|didn't\s+record|recorded)\s+"
        r"(?:a\s+|the\s+)?(?P<work_type>song|track|single)\s+called\s+"
        r"(?P<title>.+?)\s*$",
        re.I,
    )
    match = pattern.match(normalized)
    if match is None:
        return None
    return (
        _WORK_TYPE_ALIASES[match.group("work_type").lower()],
        match.group("title"),
        _clean_title(match.group("artist")),
        None,
        "recorded" in match.group("negation").lower()
        and match.group("negation").lower() != "recorded",
    )


def _parse_record_claim(
    normalized: str,
) -> tuple[str, str, str | None, str | None, bool] | None:
    """Parse claim checks such as ``Did X record TITLE on ALBUM``."""
    pattern = re.compile(
        r"^did\s+(?P<artist>.+?)\s+record\s+(?P<title>.+?)"
        r"(?:\s+on\s+(?P<album>.+?))?\s*$",
        re.I,
    )
    match = pattern.match(normalized)
    if match is None:
        return None
    return (
        "song",
        match.group("title"),
        _clean_title(match.group("artist")),
        _clean_title(match.group("album") or "") or None,
        False,
    )


def _title_candidates(
    raw_title: str,
    *,
    work_type: str,
    question_text: str,
) -> tuple[str, ...]:
    """Return candidate title parses, preserving original title text."""
    candidates: list[str] = []
    title = _clean_title(raw_title)
    words = title.split()
    if len(words) > 1 and words[-1].lower() in _TERMINAL_AMBIGUOUS_WORDS:
        without_terminal = _clean_title(" ".join(words[:-1]))
        if without_terminal:
            candidates.append(without_terminal)
        title = _canonical_terminal_title(title)
    candidates.append(title)
    if (
        work_type == "song"
        and _looks_like_recording_question(question_text)
        and words
        and words[-1].lower() not in _TERMINAL_AMBIGUOUS_WORDS
    ):
        for terminal in sorted(_TERMINAL_AMBIGUOUS_WORDS):
            candidates.append(_clean_title(f"{title} {terminal.title()}"))
    deduped: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in deduped:
            deduped.append(candidate)
    return tuple(deduped)


def _looks_like_recording_question(prompt: str) -> bool:
    """Return whether a question asks about a recording performer."""
    return bool(
        re.search(r"\b(?:band|artist|singer|recorded|performed|sang)\b", prompt, re.I)
    )


def _question_qualifiers(prompt: str, *, work_type: str) -> str:
    """Return compact search qualifiers inferred from the question wording."""
    lowered = str(prompt or "").lower()
    qualifiers: list[str] = []
    if re.search(r"\b(?:band|artist|singer|recorded|performed|sang)\b", lowered):
        qualifiers.extend(("recorded", "artist"))
    if re.search(r"\b(?:wrote|author|writer)\b", lowered):
        qualifiers.append("writer")
    if "first" in lowered:
        qualifiers.append("first")
    if work_type in {"song", "album"}:
        qualifiers.extend(("MusicBrainz", "Discogs"))
    deduped: list[str] = []
    for qualifier in qualifiers:
        if qualifier not in deduped:
            deduped.append(qualifier)
    return " ".join(deduped)


def _clean_title(value: str) -> str:
    """Clean suspected title text without changing internal casing."""
    cleaned = str(value or "").strip(" \t\r\n\"'“”‘’.,;:!?")
    return " ".join(cleaned.split())


def _canonical_terminal_title(value: str) -> str:
    """Return title text with known terminal disambiguators title-cased."""
    words = _clean_title(value).split()
    if words and words[-1].lower() in _TERMINAL_AMBIGUOUS_WORDS:
        words[-1] = words[-1].title()
    return " ".join(words)


def _normalise_title_for_match(value: str) -> str:
    """Normalise title text for exact phrase matching."""
    lowered = str(value or "").lower()
    lowered = re.sub(r"[^\w\s]+", " ", lowered, flags=re.U)
    return " ".join(lowered.split())
