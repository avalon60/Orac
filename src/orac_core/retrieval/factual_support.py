"""Post-processing helpers for high-risk retrieved factual answers."""
# Author: Clive Bostock
# Date: 02-Jun-2026
# Description: Keeps high-risk factual answers aligned with retrieved evidence.

from __future__ import annotations

import re
from typing import Any

from .models import GroundingPack


_CAUSE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:official )?cause of death (?:was|is|as)\s+(?P<cause>[^.!?\n]+)",
        re.I,
    ),
    re.compile(
        r"\b(?:died|dies) (?:of|from|due to)\s+(?P<cause>[^.!?\n]+)",
        re.I,
    ),
    re.compile(
        r"\b(?:coroner|medical examiner|post[- ]mortem)[^.!?\n]{0,120}\b(?:found|gave|recorded|confirmed)[^.!?\n]{0,80}\b(?P<cause>dilated cardiomyopathy[^.!?\n]+|myocarditis[^.!?\n]+|fatty liver[^.!?\n]+)",
        re.I,
    ),
)

_MUSIC_MEMBERSHIP_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:who\s+(?:were|are)\s+the\s+members|who\s+(?:was|is)\s+in|who\s+is\s+in|who\s+were\s+in|members?\s+of|line[- ]?up|lineup|original\s+members?|founding\s+members?)\b",
        re.I,
    ),
)
_MUSIC_MEMBERSHIP_FALLBACK = (
    "I found results, but they did not appear relevant enough to verify that safely."
)
_MUSIC_MEMBERSHIP_EVIDENCE_MARKERS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:member|members|line[- ]?up|lineup|formed|consists of|consisted of|comprised|comprises|includes|include|original members?|founding members?)\b",
        re.I,
    ),
)
_PROPER_NAME_PATTERN = re.compile(
    r"\b(?:[A-Z][a-z]+(?:['-][A-Z][a-z]+)?(?:\s+[A-Z][a-z]+(?:['-][A-Z][a-z]+)?){1,3})\b"
)


def enforce_high_risk_factual_grounding(
    text: str,
    *,
    user_query: str,
    retrieval_decision: Any | None,
    retrieval_pack: GroundingPack | None,
) -> str:
    """Return an answer constrained to retrieved facts for high-risk prompts."""
    if retrieval_pack is None or retrieval_decision is None:
        return text

    reason_code = str(getattr(retrieval_decision, "reason_code", "") or "")
    cause_of_death_route = reason_code == "factual_risk_cause_of_death" or (
        reason_code == "person_age_or_status"
        and bool(_subject_from_cause_query(user_query))
    )
    if not cause_of_death_route:
        if reason_code != "factual_risk_music_claim":
            return text
        return _constrain_music_membership_answer(
            text,
            user_query=user_query,
            retrieval_pack=retrieval_pack,
        )

    subject = _subject_from_cause_query(user_query)
    causes = _extract_causes(retrieval_pack)
    if not subject or not causes:
        return text

    if len(causes) > 1:
        strongest = causes[0]
        return (
            f"I found conflicting source claims about {subject}'s cause of death. "
            f"The strongest retrieved source says {subject} died of {strongest}."
        )

    answer = f"{subject} died of {causes[0]}."
    source_url = _first_source_url(retrieval_pack)
    if source_url and getattr(retrieval_pack, "require_citations", False):
        answer = f"{answer} Source: {source_url}"
    return answer


def _constrain_music_membership_answer(
    text: str,
    *,
    user_query: str,
    retrieval_pack: GroundingPack,
) -> str:
    """Return a music-membership answer constrained to explicit evidence."""
    if _looks_like_music_refusal(text):
        return text

    subject = _subject_from_music_membership_query(user_query)
    evidence_text = _evidence_text(retrieval_pack)
    if not subject or not _music_membership_evidence_is_explicit(evidence_text, subject):
        return _music_membership_fallback(subject)

    supported_phrases = _supported_name_phrases(text, evidence_text, subject=subject)
    if not supported_phrases:
        return _music_membership_fallback(subject)
    return text


def _extract_causes(retrieval_pack: GroundingPack) -> list[str]:
    """Extract distinct cause-of-death statements from retrieved evidence."""
    evidence_text = _evidence_text(retrieval_pack)
    causes: list[str] = []
    seen: set[str] = set()
    for pattern in _CAUSE_PATTERNS:
        for match in pattern.finditer(evidence_text):
            cause = _clean_cause(match.group("cause"))
            lowered = cause.lower()
            if cause and lowered not in seen:
                causes.append(cause)
                seen.add(lowered)
    return causes


def _evidence_text(retrieval_pack: GroundingPack) -> str:
    """Return plain retrieved text for fact extraction."""
    parts: list[str] = []
    for source in getattr(retrieval_pack, "grounding_sources", ()) or ():
        parts.append(str(getattr(source, "excerpt", "") or ""))
    for source in getattr(retrieval_pack, "fetched_sources", ()) or ():
        parts.append(str(getattr(source, "excerpt", "") or ""))
        parts.append(str(getattr(source, "text", "") or ""))
    return " ".join(part for part in parts if part.strip())


def _clean_cause(value: str) -> str:
    """Normalise an extracted cause string."""
    cause = " ".join(str(value or "").strip(" .,:;").split())
    cause = re.sub(r"\s+(?:according to|the coroner said|was confirmed).*$", "", cause, flags=re.I)
    return cause


def _subject_from_cause_query(user_query: str) -> str:
    """Extract the subject from common cause-of-death questions."""
    normalized = " ".join(str(user_query or "").strip(" .?!").split())
    patterns = (
        r"^what did (?P<subject>.+?) die of$",
        r"^(?P<subject>.+?) cause of death$",
        r"^(?:what was )?(?:the )?cause of death of (?P<subject>.+?)$",
    )
    for pattern in patterns:
        match = re.match(pattern, normalized, re.I)
        if match is None:
            continue
        subject = " ".join(match.group("subject").strip(" .?!").split())
        if subject:
            return subject
    return ""


def _first_source_url(retrieval_pack: GroundingPack) -> str:
    """Return the first grounding source URL, if present."""
    for source in getattr(retrieval_pack, "grounding_sources", ()) or ():
        url = str(getattr(source, "url", "") or "").strip()
        if url:
            return url
    return ""


def _subject_from_music_membership_query(user_query: str) -> str:
    """Extract the band or group name from a membership query."""
    normalized = " ".join(str(user_query or "").strip(" .?!").split())
    patterns = (
        r"^who\s+(?:were|are)\s+the\s+members\s+of\s+(?:the\s+group\s+|the\s+band\s+|the\s+act\s+)?(?P<subject>.+?)$",
        r"^who\s+(?:were|are)\s+members\s+of\s+(?:the\s+group\s+|the\s+band\s+|the\s+act\s+)?(?P<subject>.+?)$",
        r"^who\s+(?:was|is)\s+in\s+(?:the\s+group\s+|the\s+band\s+|the\s+act\s+)?(?P<subject>.+?)$",
        r"^who\s+is\s+in\s+(?:the\s+group\s+|the\s+band\s+|the\s+act\s+)?(?P<subject>.+?)$",
        r"^members?\s+of\s+(?:the\s+group\s+|the\s+band\s+|the\s+act\s+)?(?P<subject>.+?)$",
    )
    for pattern in patterns:
        match = re.match(pattern, normalized, re.I)
        if match is None:
            continue
        subject = " ".join(match.group("subject").strip(" .?!").split())
        if subject:
            return subject
    return ""


def _music_membership_evidence_is_explicit(evidence_text: str, subject: str) -> bool:
    """Return whether retrieved evidence explicitly grounds a membership claim."""
    lowered = evidence_text.lower()
    if subject.lower() not in lowered:
        return False
    return any(pattern.search(evidence_text) is not None for pattern in _MUSIC_MEMBERSHIP_EVIDENCE_MARKERS)


def _supported_name_phrases(text: str, evidence_text: str, *, subject: str) -> list[str]:
    """Return supported proper-name phrases from the candidate answer."""
    evidence_lower = evidence_text.lower()
    subject_lower = subject.lower()
    supported: list[str] = []
    for phrase in _PROPER_NAME_PATTERN.findall(str(text or "")):
        lowered = phrase.lower()
        if lowered == subject_lower:
            continue
        if lowered not in evidence_lower:
            return []
        supported.append(phrase)
    return supported


def _looks_like_music_refusal(text: str) -> bool:
    """Return whether the answer is already a conservative refusal."""
    lowered = " ".join(str(text or "").lower().split())
    return any(
        marker in lowered
        for marker in (
            "i found results, but they did not appear relevant enough to verify that safely.",
            "i do not find reliable evidence",
            "i cannot verify",
            "i can't verify",
            "i do not have reliable evidence",
        )
    )


def _music_membership_fallback(subject: str) -> str:
    """Return a conservative fallback for unverifiable music membership claims."""
    if subject:
        return (
            f"I do not find reliable evidence for the members of {subject}. "
            f"{_MUSIC_MEMBERSHIP_FALLBACK}"
        )
    return _MUSIC_MEMBERSHIP_FALLBACK
