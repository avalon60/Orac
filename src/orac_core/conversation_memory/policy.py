"""Conservative explicit intent policy for conversational recall."""

# Author: Clive Bostock
# Date: 2026-08-28
# Description: Detects explicit recall wording without owning retrieval.

from __future__ import annotations

from dataclasses import dataclass
import re


_MEMORY_INTENT_PATTERN = re.compile(
    r"\b(?:what\s+did\s+we\s+(?:decide|agree)|earlier|previously|last\s+time|"
    r"do\s+you\s+remember|remember\s+when|we\s+discussed)\b",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class MemoryIntentDecision:
    """Result of evaluating one utterance for explicit recall intent."""

    retrieve: bool
    query: str | None = None
    reason_code: str = "memory_intent_not_detected"


class MemoryIntentPolicy:
    """Replaceable host policy for conservative Phase 1 recall triggering."""

    def evaluate(self, text: str) -> MemoryIntentDecision:
        """Return whether explicit wording should initiate retrieval."""
        query = str(text or "").strip()
        if not query or _MEMORY_INTENT_PATTERN.search(query) is None:
            return MemoryIntentDecision(retrieve=False)
        return MemoryIntentDecision(
            retrieve=True,
            query=query,
            reason_code="explicit_memory_intent",
        )
