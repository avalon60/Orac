"""Home Assistant plugin on-demand command entry point."""
# Author: Clive Bostock
# Date: 04-Jun-2026
# Description: Dispatches narrow Home Assistant commands to managed services.

from __future__ import annotations

import re
from typing import Any

from model.plugin_runtime import PluginExecutionResult

__author__ = "Clive Bostock"
__date__ = "04-Jun-2026"
__description__ = "Dispatches narrow Home Assistant commands to managed services."

_RESYNC_COMMANDS = {
    "resync devices",
    "sync devices",
    "resync home assistant",
}


class HomeAssistantPlugin:
    """On-demand Home Assistant command plugin."""

    def __init__(
        self,
        logger=None,
        config_mgr=None,
        data_access=None,
        runtime_context=None,
    ) -> None:
        """Initialise the Home Assistant command plugin."""
        self._logger = logger
        self._config_mgr = config_mgr
        self._data_access = data_access
        self._runtime_context = runtime_context

    def can_handle(self, prompt: str) -> bool:
        """Return whether the prompt is a supported Home Assistant command."""
        return _normalise_command(prompt) in _RESYNC_COMMANDS

    def execute(
        self,
        prompt: str,
        meta: dict[str, Any] | None = None,
    ) -> PluginExecutionResult | None:
        """Execute a supported Home Assistant command."""
        if not self.can_handle(prompt):
            return None

        if self._runtime_context is None:
            return self._failure_response("Home Assistant runtime context is unavailable.")

        self._log_info("Home Assistant resync command accepted.")
        try:
            self._runtime_context.run_service_command(
                "home_assistant",
                "resync",
                {"source": "voice_command"},
            )
        except Exception as exc:
            self._log_error(f"Home Assistant resync command failed: {exc}")
            return self._failure_response(str(exc))

        return PluginExecutionResult(
            plugin_id="home_assistant",
            content=(
                "Resyncing Home Assistant devices and entities. "
                "Home Assistant sync complete."
            ),
            provenance={"command": "home_assistant.resync"},
        )

    @staticmethod
    def _failure_response(error_message: str) -> PluginExecutionResult:
        """Return a user-facing failure response for the resync command."""
        return PluginExecutionResult(
            plugin_id="home_assistant",
            content=(
                "Resyncing Home Assistant devices and entities. "
                "Home Assistant sync failed. Check the logs for details."
            ),
            provenance={
                "command": "home_assistant.resync",
                "status": "failed",
                "failure_message": error_message,
            },
        )

    def _log_info(self, message: str) -> None:
        """Write an info message when a logger is available."""
        if self._logger is not None and hasattr(self._logger, "log_info"):
            self._logger.log_info(message)

    def _log_error(self, message: str) -> None:
        """Write an error message when a logger is available."""
        if self._logger is not None and hasattr(self._logger, "log_error"):
            self._logger.log_error(message)


def _normalise_command(prompt: str) -> str:
    """Return a conservative command normalisation for exact phrase matching."""
    text = re.sub(r"[^a-z0-9\s]", " ", str(prompt or "").lower())
    return re.sub(r"\s+", " ", text).strip()
