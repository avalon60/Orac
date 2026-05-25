"""Service wrapper for Orac plugin execution coordination."""
# Author: Clive Bostock
# Date: 2026-05-25
# Description: Keeps controller code behind a narrow plugin execution seam.

from __future__ import annotations

from dataclasses import replace
from typing import Any

from model.plugin_routing.handoff import PluginRoutingHandoff
from model.plugin_runtime import PluginExecutionResult


class PluginExecutionService:
    """Coordinates plugin execution through the policy-aware plugin router."""

    def __init__(self, *, plugin_router: Any | None, logger: Any) -> None:
        """Initialise the service with the existing router dependency.

        Args:
            plugin_router: Policy-aware plugin router used for plugin
                selection and invocation.
            logger: Project logger used for debug messages.
        """
        self._plugin_router = plugin_router
        self._logger = logger

    def execute(
        self,
        *,
        prompt: str,
        meta: dict[str, Any] | None,
        handoff: PluginRoutingHandoff | None,
        auth_user: str,
    ) -> PluginExecutionResult | None:
        """Return a handled plugin result, or ``None`` for LLM fallback."""
        if self._plugin_router is None:
            self._logger.log_debug(
                "Plugin execution unavailable; falling back to conversational flow."
            )
            return None

        result = self._plugin_router.route(prompt, meta, handoff, auth_user)
        if result is None or not result.handled:
            return None

        if result.provenance:
            return result

        return replace(
            result,
            provenance={
                "source": "plugin_execution",
                "plugin_id": result.plugin_id,
                "status": "allowed",
            },
        )
