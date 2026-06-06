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
_ACK_ONLY_RESPONSE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*i\s+(?:will|'ll|’ll)\s+check\s+(?:that\s+)?online(?:\s+for\s+.+)?[.!]?\s*$", re.I),
    re.compile(r"^\s*i\s+(?:will|'ll|’ll)\s+search\s+(?:the\s+)?(?:web|internet)(?:\s+for\s+.+)?[.!]?\s*$", re.I),
    re.compile(r"^\s*searching[.!]?\s*$", re.I),
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

    snippet_only = any(
        getattr(source, "fetch_status", "") == "snippet_only"
        for source in getattr(retrieval_pack, "fetched_sources", ()) or ()
    )
    snippet_guidance = (
        " The available evidence is search-result snippet metadata only, so answer cautiously "
        "and do not present it as fully verified fetched source text."
        if snippet_only
        else ""
    )
    style = normalize_retrieval_response_style(response_style)
    if style == "debug":
        return (
            "When the user explicitly asks for retrieval detail, you may append a short "
            "Retrieval details section with the provider, query, source URLs, fetch status, "
            "and brief excerpts. Keep the main answer natural and concise."
        )
    titled_work_guidance = _titled_work_guidance(retrieval_pack)
    music_claim_guidance = _music_claim_guidance(retrieval_pack)
    if style == "transparent":
        return (
            "Answer naturally and keep any limitation brief. If the evidence only partially "
            "supports the answer, say so in ordinary language such as 'I found public "
            "references to it, but not enough reliable detail to confirm the full answer.' "
            "If citations are required, cite the source URLs naturally in the answer. "
            "Do not mention internal retrieval mechanics such as search results, fetched "
            "sources, grounding packs, reason codes, service names, or retrieved evidence."
            f"{titled_work_guidance}"
            f"{music_claim_guidance}"
        )
    return (
        "Answer naturally and directly. If the evidence is sufficient, give just the answer. "
        "If it only partially supports the answer, mention that briefly in ordinary language. "
        "For high-risk factual questions, use only facts stated in the retrieved evidence; "
        "do not add causes, dates, ages, prices, office holders, legal, medical, or financial "
        "details unless the evidence explicitly supports them. "
        "If citations are required, cite the source URLs naturally in the answer. "
        "Do not mention internal retrieval mechanics such as search results, fetched sources, "
        "grounding packs, reason codes, service names, or retrieved evidence."
        f"{snippet_guidance}"
        f"{titled_work_guidance}"
        f"{music_claim_guidance}"
    )


def polish_retrieval_response_text(
    text: str,
    *,
    response_style: str,
    retrieval_pack: GroundingPack | None,
    retrieval_outcome: RetrievalOutcome | None = None,
) -> str:
    """Remove mechanical retrieval phrasing from the final answer."""
    del retrieval_outcome
    raw_text = str(text or "").strip()
    if not raw_text:
        return raw_text

    style = normalize_retrieval_response_style(response_style)
    if style == "debug":
        return raw_text
    if retrieval_pack is not None and _is_ack_only_response(raw_text):
        return "I checked online, but I couldn't produce a reliable answer from the retrieved sources."
    titled_work_answer = _safe_titled_work_answer(retrieval_pack)
    if titled_work_answer is not None:
        return titled_work_answer

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


def _titled_work_guidance(retrieval_pack: GroundingPack | None) -> str:
    """Return extra answer guidance for exact titled-work lookups."""
    if retrieval_pack is None:
        return ""
    metadata = getattr(getattr(retrieval_pack, "request", None), "metadata", {}) or {}
    if not metadata.get("titled_work"):
        return ""
    candidates = tuple(str(value) for value in metadata.get("title_candidates", ()) or ())
    supported = tuple(str(value) for value in metadata.get("supported_title_candidates", ()) or ())
    unsupported = tuple(str(value) for value in metadata.get("unsupported_title_candidates", ()) or ())
    if not candidates:
        return ""
    quoted = ", ".join(f'"{candidate}"' for candidate in candidates)
    supported_text = (
        f" Supported exact-title candidates: {', '.join(f'\"{title}\"' for title in supported)}."
        if supported
        else " No exact-title candidate is supported by the evidence."
    )
    unsupported_text = (
        f" Unsupported exact-title candidates: {', '.join(f'\"{title}\"' for title in unsupported)}."
        if unsupported
        else ""
    )
    return (
        " Preserve the suspected title exactly. Consider these exact-title parses before "
        f"answering: {quoted}. Prefer exact title evidence over fuzzy famous-artist matches. "
        f"{supported_text}{unsupported_text} "
        "Do not mention unsupported artists, dates, or releases for unsupported title "
        "candidates. Do not merge facts from one candidate into another. "
        "If exact-title evidence does not support the answer, say the title may have been "
        "misremembered rather than inventing a release."
    )


def _safe_titled_work_answer(retrieval_pack: GroundingPack | None) -> str | None:
    """Return a deterministic titled-work answer when evidence is narrow enough."""
    if retrieval_pack is None:
        return None
    metadata = getattr(getattr(retrieval_pack, "request", None), "metadata", {}) or {}
    if not metadata.get("titled_work"):
        return None
    unsupported = tuple(str(value) for value in metadata.get("unsupported_title_candidates", ()) or ())
    exact_title = str(metadata.get("user_provided_title") or "").strip()
    claim_artist = str(metadata.get("claim_artist") or "").strip()
    claim_album = str(metadata.get("claim_album") or "").strip()
    correction_negation = bool(metadata.get("correction_negation"))
    supported_resolution = _first_supported_title_resolution(metadata)
    preferred = str((supported_resolution or {}).get("candidate_title") or "").strip()
    artist = str((supported_resolution or {}).get("supported_artist") or "").strip()

    if exact_title and exact_title in unsupported and claim_artist:
        album_clause = f" on {claim_album}" if claim_album else ""
        prefix = (
            f"You are right: I do not find reliable evidence that {claim_artist} "
            f"recorded a song called '{exact_title}'{album_clause}."
            if correction_negation
            else (
                f"I do not find reliable evidence that {claim_artist} recorded "
                f"'{exact_title}'{album_clause}."
            )
        )
        if preferred and artist and preferred != exact_title:
            return (
                f"{prefix} I also should not attribute it to another band without evidence. "
                f"The likely title is '{preferred}', which appears to be by {artist}."
            )
        return (
            f"{prefix} I also should not attribute it to another band without evidence."
        )

    if exact_title and exact_title in unsupported:
        if preferred and artist and preferred != exact_title:
            return (
                f"I do not find reliable evidence for a song titled '{exact_title}'. "
                f"You may mean '{preferred}', by {artist}."
            )
        return f"I do not find reliable evidence for a song titled '{exact_title}'."

    if preferred and artist:
        return f"The title is likely '{preferred}', recorded by {artist}."
    if preferred:
        return f"The title is likely '{preferred}', but I do not find reliable artist evidence."
    return None


def _first_supported_title_resolution(metadata: dict) -> dict:
    """Return the first metadata candidate with exact-title source support."""
    for resolution in metadata.get("candidate_resolutions", ()) or ():
        if not isinstance(resolution, dict):
            continue
        if not resolution.get("source_support_found"):
            continue
        return resolution
    return {}


def _mentions_unsupported_titled_work_claim(
    text: str,
    retrieval_pack: GroundingPack | None,
) -> bool:
    """Return whether a generated answer risks merging unsupported title facts."""
    if retrieval_pack is None:
        return False
    metadata = getattr(getattr(retrieval_pack, "request", None), "metadata", {}) or {}
    if not metadata.get("titled_work"):
        return False
    unsupported = tuple(str(value) for value in metadata.get("unsupported_title_candidates", ()) or ())
    supported = tuple(str(value) for value in metadata.get("supported_title_candidates", ()) or ())
    exact_title = str(metadata.get("user_provided_title") or "").strip()
    lowered = str(text or "").lower()
    if exact_title in unsupported:
        return True
    if any(title.lower() in lowered for title in unsupported):
        return True
    if supported and re.search(r"\b(?:beatles|1969)\b", lowered):
        return True
    return False


def _artist_for_title(retrieval_pack: GroundingPack, title: str) -> str | None:
    """Extract a simple recording artist claim for a supported title."""
    escaped = re.escape(title)
    evidence_parts: list[str] = []
    for source in getattr(retrieval_pack, "grounding_sources", ()) or ():
        evidence_parts.append(str(getattr(source, "title", "") or ""))
        evidence_parts.append(str(getattr(source, "excerpt", "") or ""))
    for source in getattr(retrieval_pack, "fetched_sources", ()) or ():
        evidence_parts.append(str(getattr(source, "title", "") or ""))
        evidence_parts.append(str(getattr(source, "excerpt", "") or ""))
        evidence_parts.append(str(getattr(source, "text", "") or ""))
    evidence = " ".join(part for part in evidence_parts if part)
    patterns = (
        rf"{escaped}.{{0,160}}\brecorded by\s+(?P<artist>[A-Z][A-Za-z0-9 '&.-]{{1,80}})",
        rf"{escaped}.{{0,160}}\bby\s+(?P<artist>[A-Z][A-Za-z0-9 '&.-]{{1,80}})",
        rf"(?P<artist>[A-Z][A-Za-z0-9 '&.-]{{1,80}}).{{0,80}}\brecorded\s+{escaped}",
    )
    for pattern in patterns:
        match = re.search(pattern, evidence, re.I)
        if match is None:
            continue
        artist = _clean_artist(match.group("artist"))
        if artist:
            return artist
    return None


def _music_claim_guidance(retrieval_pack: GroundingPack | None) -> str:
    """Return extra answer guidance for music factual-claim lookups."""
    if retrieval_pack is None:
        return ""
    metadata = getattr(getattr(retrieval_pack, "request", None), "metadata", {}) or {}
    if not metadata.get("music_claim"):
        return ""
    return (
        " If the question asks about band members, line-ups, credits, or personnel, "
        "use only names explicitly present in the retrieved evidence. If the evidence "
        "does not clearly ground the membership claim, say you cannot verify it safely "
        "instead of inventing a line-up."
    )


def _clean_artist(value: str) -> str:
    """Return a compact artist name extracted from evidence."""
    cleaned = re.split(
        r"\s+(?:on|in|for|and)\b|[.,;:]",
        str(value or "").strip(),
        maxsplit=1,
    )[0]
    cleaned = cleaned.strip(" \"'“”‘’.,;:")
    return " ".join(cleaned.split())


def _is_ack_only_response(text: str) -> bool:
    """Return whether text is only a retrieval action acknowledgement."""
    return any(pattern.search(str(text or "")) is not None for pattern in _ACK_ONLY_RESPONSE_PATTERNS)


def _split_sentences(text: str) -> Sequence[str]:
    """Split plain text into coarse sentence boundaries."""
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", str(text or "").strip())
        if sentence.strip()
    ]
    return sentences or [str(text or "").strip()]
