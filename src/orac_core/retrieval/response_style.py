"""Response styling helpers for explicit internet retrieval."""
# Author: Clive Bostock
# Date: 2026-05-26
# Description: Shapes retrieval prompts and normalises verbose retrieval replies.

from __future__ import annotations

import re
from typing import Sequence

from .models import GroundingPack
from .models import RetrievalOutcome

_ALLOWED_STYLES = {"normal", "transparent", "debug"}
_MECHANICAL_SENTENCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bretrieved evidence\b", re.I),
    re.compile(r"\bgrounding pack\b", re.I),
    re.compile(r"\bfetched sources\b", re.I),
    re.compile(r"\bsearch results confirm(?:s|ed)?\b", re.I),
    re.compile(r"\bsearch results\b", re.I),
)


def normalize_retrieval_response_style(value: str | None) -> str:
    """Return a supported retrieval response style name."""
    normalized = str(value or "normal").strip().lower()
    return normalized if normalized in _ALLOWED_STYLES else "normal"


def build_retrieval_response_guidance(
    *,
    response_style: str,
    retrieval_pack: GroundingPack | None,
) -> str:
    """Build prompt guidance for the requested retrieval response style."""
    if retrieval_pack is None:
        return ""

    style = normalize_retrieval_response_style(response_style)
    if style == "debug":
        return (
            "When the user explicitly asks for retrieval detail, you may append a short "
            "Retrieval details section with the provider, query, source URLs, fetch status, "
            "and brief excerpts. Keep the main answer natural and concise."
        )
    if style == "transparent":
        return (
            "Answer naturally and keep any limitation brief. If the evidence only partially "
            "supports the answer, say so in ordinary language such as 'I found public "
            "references to it, but not enough reliable detail to confirm the full answer.' "
            "If citations are required, cite the source URLs naturally in the answer. "
            "Do not mention internal retrieval mechanics such as search results, fetched "
            "sources, grounding packs, reason codes, service names, or retrieved evidence."
        )
    return (
        "Answer naturally and directly. If the evidence is sufficient, give just the answer. "
        "If it only partially supports the answer, mention that briefly in ordinary language. "
        "If citations are required, cite the source URLs naturally in the answer. "
        "Do not mention internal retrieval mechanics such as search results, fetched sources, "
        "grounding packs, reason codes, service names, or retrieved evidence."
    )


def polish_retrieval_response_text(
    text: str,
    *,
    response_style: str,
    retrieval_pack: GroundingPack | None,
    retrieval_outcome: RetrievalOutcome | None = None,
) -> str:
    """Remove mechanical retrieval phrasing from the final answer."""
    del retrieval_pack, retrieval_outcome
    raw_text = str(text or "").strip()
    if not raw_text:
        return raw_text

    style = normalize_retrieval_response_style(response_style)
    if style == "debug":
        return raw_text

    sentences = _split_sentences(raw_text)
    kept_sentences = [
        sentence
        for sentence in sentences
        if not _contains_mechanical_phrase(sentence)
    ]
    if kept_sentences:
        return " ".join(kept_sentences).strip()

    rewritten = raw_text
    rewritten = re.sub(
        r"(?i)\bthe retrieved evidence confirms\b",
        "I found",
        rewritten,
    )
    rewritten = re.sub(
        r"(?i)\bretrieved evidence confirms\b",
        "I found",
        rewritten,
    )
    rewritten = re.sub(
        r"(?i)\bsearch results confirm(?:s|ed)?\b",
        "I found",
        rewritten,
    )
    rewritten = re.sub(
        r"(?i)\bfetched sources\b",
        "sources",
        rewritten,
    )
    rewritten = re.sub(
        r"(?i)\bgrounding pack\b",
        "evidence",
        rewritten,
    )
    rewritten = re.sub(
        r"(?i)\bretrieved evidence\b",
        "evidence",
        rewritten,
    )
    rewritten = re.sub(r"\s+", " ", rewritten).strip()
    return rewritten or raw_text


def _contains_mechanical_phrase(text: str) -> bool:
    """Return whether a sentence contains retrieval implementation phrasing."""
    lowered = str(text or "")
    return any(pattern.search(lowered) is not None for pattern in _MECHANICAL_SENTENCE_PATTERNS)


def _split_sentences(text: str) -> Sequence[str]:
    """Split plain text into coarse sentence boundaries."""
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", str(text or "").strip())
        if sentence.strip()
    ]
    return sentences or [str(text or "").strip()]
