"""Plugin marker for Orac Gateway discovery."""
# Author: Clive Bostock
# Date: 28-Sep-2026
# Description: Provides the on-demand marker required by the plugin manifest.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from typing import Any

from model.plugin_runtime import PluginExecutionResult


class OracGatewayPlugin:
    """Identify the gateway while its work remains in the managed service."""

    def execute(
        self,
        prompt: str,
        meta: dict[str, Any] | None = None,
    ) -> PluginExecutionResult | None:
        """Decline direct execution because inference uses the HTTP service."""
        del prompt, meta
        return None

    def handle(self, _request: object) -> dict[str, str]:
        """Reject direct dialogue execution in favour of the HTTP service."""
        return {
            "status": "unsupported",
            "message": "Orac Gateway is available through its managed HTTP service.",
        }
