"""Home Assistant plugin on-demand command entry point."""
# Author: Clive Bostock
# Date: 04-Jun-2026
# Description: Dispatches narrow Home Assistant commands to managed services.

from __future__ import annotations

import re
from typing import Any

from model.plugin_runtime import PluginExecutionResult

from .control import ControlRequest
from .control import parse_area_inventory_command
from .control import HomeAssistantControlError
from .control import parse_area_list_command
from .control import parse_control_command
from .sensor_query import HomeAssistantSensorQueryError
from .sensor_query import parse_sensor_query

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
        if _normalise_command(prompt) in _RESYNC_COMMANDS:
            return True
        try:
            return (
                parse_control_command(prompt) is not None
                or parse_area_inventory_command(prompt) is not None
                or parse_area_list_command(prompt) is not None
                or parse_sensor_query(prompt) is not None
            )
        except HomeAssistantControlError:
            return True

    def execute(
        self,
        prompt: str,
        meta: dict[str, Any] | None = None,
    ) -> PluginExecutionResult | None:
        """Execute a supported Home Assistant command."""
        normalised = _normalise_command(prompt)
        try:
            control_request = parse_control_command(prompt)
            area_inventory_request = parse_area_inventory_command(prompt)
            area_list_request = parse_area_list_command(prompt)
            sensor_query_request = parse_sensor_query(prompt)
        except HomeAssistantControlError as exc:
            return self._control_failure_response(exc.code, str(exc))

        if (
            normalised not in _RESYNC_COMMANDS
            and control_request is None
            and area_inventory_request is None
            and area_list_request is None
            and sensor_query_request is None
        ):
            return None

        if self._runtime_context is None:
            return self._failure_response("Home Assistant runtime context is unavailable.")

        if control_request is not None:
            return self._execute_control(control_request)
        if area_inventory_request is not None:
            return self._execute_area_inventory()
        if area_list_request is not None:
            return self._execute_area_list(
                area_list_request.area,
                area_list_request.requested_domain,
            )
        if sensor_query_request is not None:
            return self._execute_sensor_query(sensor_query_request)

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

    def _execute_area_list(
        self,
        area: str,
        requested_domain: str | None,
    ) -> PluginExecutionResult:
        """Dispatch and format one read-only Home Assistant area listing."""
        try:
            result = self._runtime_context.run_service_command(
                "home_assistant",
                "list_area",
                {"area": area, "requested_domain": requested_domain},
            )
        except HomeAssistantControlError as exc:
            return self._area_list_failure_response(exc.code, str(exc))
        except Exception as exc:
            self._log_error(f"Home Assistant area listing failed: {exc}")
            return self._area_list_failure_response("execution_failed", str(exc))

        devices = list(result.get("devices") or ())
        area_name = str(result.get("area_name") or area).title()
        noun = {
            None: "devices",
            "light": "lights",
            "scene": "scenes",
            "switch": "switches",
        }.get(requested_domain, "devices")
        if not devices:
            content = f"No Home Assistant {noun} were found in {area_name}."
        else:
            names = ", ".join(str(device.get("name") or "").title() for device in devices)
            content = f"Home Assistant {noun} in {area_name}: {names}."
        return PluginExecutionResult(
            plugin_id="home_assistant",
            content=content,
            provenance={
                "command": "home_assistant.area_list",
                "area": str(result.get("area_name") or area),
                "requested_domain": requested_domain,
                "entity_ids": [
                    entity_id
                    for device in devices
                    for entity_id in device.get("entity_ids", ())
                ],
                "status": "complete",
            },
        )

    def _execute_area_inventory(self) -> PluginExecutionResult:
        """Dispatch and format the known Home Assistant area inventory."""
        try:
            result = self._runtime_context.run_service_command(
                "home_assistant",
                "list_areas",
                {},
            )
        except HomeAssistantControlError as exc:
            return self._area_list_failure_response(exc.code, str(exc))
        except Exception as exc:
            self._log_error(f"Home Assistant area inventory failed: {exc}")
            return self._area_list_failure_response("execution_failed", str(exc))

        areas = [str(area).title() for area in result.get("areas") or () if str(area).strip()]
        if not areas:
            content = (
                "Home Assistant areas were not found on this system. "
                "I cannot list them without access to your Home Assistant instance's data."
            )
        else:
            content = "Home Assistant areas: " + ", ".join(sorted(areas)) + "."
        return PluginExecutionResult(
            plugin_id="home_assistant",
            content=content,
            provenance={
                "command": "home_assistant.area_inventory",
                "areas": areas,
                "status": "complete",
            },
        )

    def _execute_sensor_query(self, request) -> PluginExecutionResult:
        """Dispatch one deterministic read-only Home Assistant sensor query."""
        try:
            result = self._runtime_context.run_service_command(
                "home_assistant",
                "sensor_query",
                {
                    "intent": request.intent,
                    "areas": list(request.areas),
                    "sensor_role": request.sensor_role,
                },
            )
        except HomeAssistantSensorQueryError as exc:
            return self._sensor_query_failure_response(exc.code, str(exc))
        except Exception as exc:
            self._log_error(f"Home Assistant sensor query failed: {exc}")
            return self._sensor_query_failure_response("execution_failed", str(exc))

        return PluginExecutionResult(
            plugin_id="home_assistant",
            content=str(result.get("content") or "Home Assistant sensor query failed."),
            provenance={
                "command": "home_assistant.sensor_query",
                "intent": request.intent,
                "areas": list(result.get("areas") or request.areas),
                "entity_ids": list(result.get("entity_ids") or ()),
                "status": str(result.get("status") or "complete"),
                "source": str(result.get("source") or "unknown"),
            },
        )

    @staticmethod
    def _sensor_query_failure_response(
        code: str,
        message: str,
    ) -> PluginExecutionResult:
        """Return an explicit user-facing read-only sensor-query failure."""
        return PluginExecutionResult(
            plugin_id="home_assistant",
            content=message,
            provenance={
                "command": "home_assistant.sensor_query",
                "status": "failed",
                "failure_type": code,
                "failure_message": message,
            },
        )

    @staticmethod
    def _area_list_failure_response(code: str, message: str) -> PluginExecutionResult:
        """Return an explicit user-facing area-list failure."""
        return PluginExecutionResult(
            plugin_id="home_assistant",
            content=f"Home Assistant area listing failed: {message}",
            provenance={
                "command": "home_assistant.area_list",
                "status": "failed",
                "failure_type": code,
                "failure_message": message,
            },
        )

    def _execute_control(self, request: ControlRequest) -> PluginExecutionResult:
        """Dispatch one parsed control request to the managed service."""
        self._log_info("Home Assistant device-control command accepted.")
        try:
            result = self._runtime_context.run_service_command(
                "home_assistant",
                "control",
                {
                    "action": request.action,
                    "target": request.target,
                    "requested_domain": request.requested_domain,
                },
            )
        except HomeAssistantControlError as exc:
            return self._control_failure_response(exc.code, str(exc))
        except Exception as exc:
            self._log_error(f"Home Assistant device control failed: {exc}")
            return self._control_failure_response("execution_failed", str(exc))

        status = str(result.get("status") or "")
        entity_ids = tuple(result.get("entity_ids") or ())
        if status != "confirmed":
            return self._control_failure_response(
                "unconfirmed",
                "Home Assistant accepted the request but did not confirm the change.",
            )
        return PluginExecutionResult(
            plugin_id="home_assistant",
            content=(
                "Home Assistant confirmed "
                f"{request.action.replace('_', ' ')} for {request.target}."
            ),
            provenance={
                "command": "home_assistant.device_control",
                "action": request.action,
                "entity_ids": list(entity_ids),
                "status": "confirmed",
            },
        )

    @staticmethod
    def _control_failure_response(code: str, message: str) -> PluginExecutionResult:
        """Return an explicit user-facing control refusal or failure."""
        return PluginExecutionResult(
            plugin_id="home_assistant",
            content=f"Home Assistant control was not performed: {message}",
            provenance={
                "command": "home_assistant.device_control",
                "status": "failed",
                "failure_type": code,
                "failure_message": message,
            },
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
