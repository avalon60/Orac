"""Classify low-information social turns without phrase-specific routing."""

# Author: Clive Bostock
# Date: 04-Oct-2026
# Description: Provides a conservative deterministic social-turn classifier.

from __future__ import annotations

import re

_SOCIAL_WORDS = frozenset(
    {
        "ahoy", "bye", "cheers", "evening", "goodbye", "hello", "hey", "hi",
        "hiya", "morning", "night", "ok", "okay", "thanks", "thank", "welcome",
        "yo", "you",
    }
)
_INFORMATIONAL_MARKERS = re.compile(
    r"\b(?:what|when|where|which|who|why|how|explain|show|find|search|look\s+up|"
    r"tell\s+me|can\s+you|could\s+you|would\s+you|please|open|run|turn|set|create|"
    r"delete|update|change|document|project|knowledge|web|internet)\b",
    re.IGNORECASE,
)


def is_social_noninformational_turn(text: str) -> bool:
    """Return whether text is clearly social and requires no external evidence.

    The classifier is deliberately conservative. It accepts only short turns made
    entirely from a small social vocabulary after punctuation is removed.
    """
    value = str(text or "").strip()
    if not value or len(value) > 80 or _INFORMATIONAL_MARKERS.search(value):
        return False
    words = re.findall(r"[A-Za-z']+", value.lower())
    return 1 <= len(words) <= 6 and all(word in _SOCIAL_WORDS for word in words)
