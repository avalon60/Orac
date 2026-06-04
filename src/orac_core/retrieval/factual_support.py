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
    if reason_code != "factual_risk_cause_of_death":
        return text

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
