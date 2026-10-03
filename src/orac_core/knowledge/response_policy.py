"""Apply deterministic policy to unsupported knowledge-absence claims."""

# Author: Clive Bostock
# Date: 27-Sep-2026
# Description: Rewrites over-broad absence claims before any response delivery.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from dataclasses import dataclass
import re

UNSUPPORTED_ABSENCE_REPLACEMENT = (
    "The excerpts retrieved so far do not establish that detail."
)

_SENTENCE_END = re.compile(
    r".*?(?:[.!?](?:[\"'”’*]+)?(?=\s|$)|\n+)",
    re.DOTALL,
)
_ABSENCE = re.compile(
    r"(?ix)\b(?:"
    r"(?:the\s+)?(?:provided\s+|current\s+|local\s+)?(?:reference\s+)?"
    r"(?:document|source|corpus|knowledge\s*base|files?|materials?)\s+"
    r"(?:does\s+not|doesn't|do\s+not|don't|cannot|can't|never)\s+"
    r"(?:mention|contain|include|cover|discuss|state|say|provide|have|attribute)"
    r"|(?:there\s+is|there's)\s+no\s+"
    r"(?:mention|information|detail|evidence|record)\b"
    r"|(?:no|nothing)\s+(?:in|within)\s+(?:the\s+)?"
    r"(?:document|source|corpus|knowledge\s*base|files?|materials?)\s+"
    r"(?:mentions?|covers?|supports?|establishes?)"
    r"|(?:i|we)\s+(?:do\s+not|don't)\s+have\s+any\s+"
    r"(?:information|details?|evidence)\b[^.!?]*\b(?:knowledge\s*base|"
    r"reference\s+documents?|sources?|corpus)\b"
    r"|(?:document|source|book|file|materials?)\b[^!?]*?\b(?:it|they)\s+"
    r"(?:does\s+not|doesn't|do\s+not|don't|never)\s+"
    r"(?:mention|contain|include|cover|discuss|state|say|provide|have|attribute)"
    r"|(?:document|source|book|file|corpus|knowledge\s*base|"
    r"(?:reference\s+)?materials?)\b[^!?]*?\b"
    r"(?:does\s+not|doesn't|do\s+not|don't|never)\s+"
    r"(?:mention|contain|include|cover|discuss|state|say|provide|have|attribute)"
    r")\b"
)
_SCOPED = re.compile(
    r"(?i)\b(?:retrieved|provided|selected|shown)\s+"
    r"(?:excerpts?|chunks?|passages?|evidence)\b|\bso\s+far\b|\bin\s+these\s+excerpts\b"
)
_SUPPORTED_NEGATIVE = re.compile(
    r"(?i)\b(?:document|source|excerpt|passage)\s+"
    r"(?:explicitly\s+)?(?:states?|says?|reports?|records?)\s+that\b"
)


@dataclass(frozen=True, slots=True)
class ResponsePolicyResult:
    """Sanitised response text and its content-free rewrite count."""

    text: str
    rewrite_count: int = 0


def apply_response_policy(text: str) -> ResponsePolicyResult:
    """Rewrite only categorical, unsupported collection-absence statements."""
    if not text:
        return ResponsePolicyResult(text)
    parts: list[str] = []
    rewrite_count = 0
    consumed = 0
    for match in _SENTENCE_END.finditer(text):
        result = _apply_sentence_policy(match.group(0))
        parts.append(result.text)
        rewrite_count += result.rewrite_count
        consumed = match.end()
    if consumed < len(text):
        result = _apply_sentence_policy(text[consumed:])
        parts.append(result.text)
        rewrite_count += result.rewrite_count
    return ResponsePolicyResult("".join(parts), rewrite_count)


def _apply_sentence_policy(text: str) -> ResponsePolicyResult:
    """Apply the narrow rule to one complete or trailing sentence."""
    if _SCOPED.search(text) or _SUPPORTED_NEGATIVE.search(text):
        return ResponsePolicyResult(text)
    if not _ABSENCE.search(text):
        return ResponsePolicyResult(text)
    leading = text[: len(text) - len(text.lstrip())]
    trailing = text[len(text.rstrip()) :]
    return ResponsePolicyResult(
        f"{leading}{UNSUPPORTED_ABSENCE_REPLACEMENT}{trailing}",
        1,
    )


def rewrite_unsupported_absence_claims(text: str) -> str:
    """Return policy-safe text for non-streaming compatibility callers."""
    return apply_response_policy(text).text


class ResponsePolicyStreamBuffer:
    """Hold arbitrary stream boundaries until complete sentences are policy-safe."""

    def __init__(self, *, enabled: bool = True) -> None:
        """Initialise a buffer, optionally retaining pass-through stream behaviour."""
        self._enabled = enabled
        self._pending = ""
        self.rewrite_count = 0

    def add_delta(self, delta: str) -> tuple[str, ...]:
        """Return complete, rewritten sentences produced by one model delta."""
        if not self._enabled:
            return (delta,) if delta else ()
        self._pending += delta
        emitted: list[str] = []
        consumed = 0
        for match in _SENTENCE_END.finditer(self._pending):
            segment = match.group(0)
            result = apply_response_policy(segment)
            self.rewrite_count += result.rewrite_count
            emitted.append(result.text)
            consumed = match.end()
        if consumed:
            self._pending = self._pending[consumed:]
        return tuple(emitted)

    def flush(self) -> str:
        """Rewrite and return the final unfinished sentence exactly once."""
        if not self._enabled:
            return ""
        if not self._pending:
            return ""
        result = apply_response_policy(self._pending)
        self._pending = ""
        self.rewrite_count += result.rewrite_count
        return result.text

    def discard(self) -> None:
        """Discard unfinished model text after cancellation."""
        self._pending = ""
