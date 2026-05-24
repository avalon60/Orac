"""Home Assistant plugin runtime placeholders."""
# Author: Clive Bostock
# Date: 2026-05-20
# Description: Provides lifecycle-safe Home Assistant plugin placeholders.

from __future__ import annotations

from typing import Any


class HomeAssistantPlugin:
    """Placeholder on-demand Home Assistant plugin entry point."""

    def __init__(self, logger=None, config_mgr=None, data_access=None) -> None:
        self._logger = logger
        self._config_mgr = config_mgr
        self._data_access = data_access

    def can_handle(self, prompt: str) -> bool:
        """Return whether this placeholder should handle a prompt."""
        return False


class HomeAssistantService:
    """Lifecycle placeholder for the Home Assistant long-running service."""

    def __init__(self, logger=None, config_mgr=None, manifest=None) -> None:
        self._logger = logger
        self._config_mgr = config_mgr
        self._manifest = manifest
        self._started = False

    def run(self, context: Any) -> None:
        """Run until Orac requests cancellation through the service context."""
        self._started = True
        if self._logger is not None:
            self._logger.log_info(
                "Home Assistant service placeholder started; no websocket "
                "connection is attempted in this pass."
            )
        while not context.stop_event.wait(0.1):
            pass

    def stop(self, context: Any) -> None:
        """Observe Orac-owned cancellation without spawning unmanaged work."""
        context.stop_event.set()

    def health(self, context: Any) -> bool:
        """Return placeholder health based on cancellation state."""
        return self._started and not context.stop_event.is_set()
