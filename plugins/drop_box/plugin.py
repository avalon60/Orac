"""Non-conversational entry module for the drop-box ingestion plugin."""
# Author: Clive Bostock
# Date: 27-Jun-2026
# Description: Provides a minimal module for plugin package consistency.

from __future__ import annotations

from model.plugin_runtime import PluginExecutionResult

__author__ = "Clive Bostock"
__date__ = "27-Jun-2026"
__description__ = "Provides a minimal module for plugin package consistency."


class DropBoxPlugin:
    """Non-conversational plugin placeholder.

    The drop-box plugin is service-only in phase 1. Orac should manage scanning
    through ``DropBoxService`` instead of routing user turns here.
    """

    def can_handle(self, prompt: str) -> bool:
        """Return false because phase 1 has no conversational command surface."""
        return False

    def execute(self, prompt: str, meta: dict | None = None) -> PluginExecutionResult | None:
        """Return ``None`` because no on-demand execution is supported."""
        return None
