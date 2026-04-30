"""Plugin execution orchestration for candidate plugins."""
# Author: Clive Bostock
# Date: 2026-04-30
# Description: Tries routed plugin candidates in order and returns the first
#   handled result.

from __future__ import annotations

from typing import Any

from model.plugin_routing.handoff import PluginRoutingHandoff
from model.plugin_runtime import (
    PluginDataAccess,
    PluginExecutionResult,
    PluginRuntimeError,
    instantiate_plugin,
    load_plugin_class,
)


class PluginRouter:
    """Attempts execution for candidate plugins without owning discovery or indexing."""

    def __init__(self, plugin_manager, logger, config_mgr, context_manager):
        self._plugin_manager = plugin_manager
        self._logger = logger
        self._config_mgr = config_mgr
        self._context_manager = context_manager

    def route(
        self,
        prompt: str,
        meta: dict[str, Any] | None,
        handoff: PluginRoutingHandoff | None,
        auth_user: str,
    ) -> PluginExecutionResult | None:
        """Returns the first successful plugin execution result, or None."""
        if handoff is None or not handoff.candidates or self._plugin_manager is None:
            return None

        meta = meta or {}

        for candidate in handoff.candidates:
            manifest = self._plugin_manager.get_manifest(candidate.plugin_id)
            if manifest is None:
                self._logger.log_debug(
                    f"Plugin execution skipped because manifest '{candidate.plugin_id}' was not found."
                )
                continue
            if not manifest.entry_point:
                self._logger.log_debug(
                    f"Plugin execution skipped for '{candidate.plugin_id}' because no entry_point is defined."
                )
                continue

            try:
                plugin_class = load_plugin_class(manifest)
                data_access = PluginDataAccess(
                    manifest=manifest,
                    context_manager=self._context_manager,
                    auth_user=auth_user,
                    logger=self._logger,
                )
                plugin_instance = instantiate_plugin(
                    plugin_class,
                    logger=self._logger,
                    config_mgr=self._config_mgr,
                    data_access=data_access,
                )
                if hasattr(plugin_instance, "can_handle") and not plugin_instance.can_handle(prompt):
                    self._logger.log_debug(
                        f"Plugin '{candidate.plugin_id}' declined prompt after execution-time handle check."
                    )
                    continue
                result = plugin_instance.execute(prompt, meta)
            except PluginRuntimeError as exc:
                self._log_exception(f"Plugin runtime failed for '{candidate.plugin_id}' (non-fatal)", exc)
                continue
            except Exception as exc:
                self._log_exception(f"Plugin execution failed for '{candidate.plugin_id}' (non-fatal)", exc)
                continue

            if result is not None and result.handled:
                self._logger.log_info(f"Plugin '{candidate.plugin_id}' handled request directly.")
                return result

        self._logger.log_debug("No plugin candidate handled the request directly; falling back to conversational flow.")
        return None

    def _log_exception(self, prefix: str, exc: BaseException) -> None:
        self._logger.log_error(f"{prefix}: {exc}")
