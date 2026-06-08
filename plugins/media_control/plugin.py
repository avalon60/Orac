"""Non-executable scaffold entry point for the future media-control plugin."""
# Author: Clive Bostock
# Date: 07-Jun-2026
# Description: Provides an importable contract while policy blocks unfinished media control.

from __future__ import annotations

from typing import Any

from model.plugin_runtime import PluginExecutionResult


class MediaControlPlugin:
    """Importable media-control scaffold denied by Orac execution policy."""

    def execute(
        self,
        prompt: str,
        meta: dict[str, Any] | None = None,
    ) -> PluginExecutionResult:
        """Return a defensive response if invoked outside the policy boundary."""
        del prompt, meta
        return PluginExecutionResult(
            plugin_id="media_control",
            content="Media control is not yet configured for execution.",
            handled=False,
            provenance={"scaffold": True},
        )
