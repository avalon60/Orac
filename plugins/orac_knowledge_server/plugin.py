"""Plugin discovery marker for the read-only Orac MCP service."""
# Author: Clive Bostock
# Date: 11-Oct-2026
# Description: Keeps conversational execution separate from the MCP service.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from typing import Any


class OracKnowledgeServerPlugin:
    """Decline direct execution; the managed service owns MCP transport."""

    def execute(self, prompt: str, meta: dict[str, Any] | None = None) -> None:
        """Return no conversational action for this service-only plugin."""
        del prompt, meta
        return None
