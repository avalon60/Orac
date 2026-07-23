"""Home Assistant plugin on-demand command entry point."""
# Author: Clive Bostock
# Date: 15-Jul-2026
# Description: Dispatches Home Assistant commands selected by core routing metadata.

from __future__ import annotations

from typing import Any

from model.plugin_resources import resource_reader_for_manifest
from model.plugin_routing.interception import mutable_mapping
from model.plugin_runtime import PluginExecutionResult

from .control import AreaListRequest
from .control import ControlRequest
from .control import build_control_request
from .control import HomeAssistantControlError
from .interceptor import HomeAssistantDialogInterceptor
from .light_control import LightControlRequest
from .light_state_query import LightStateQueryRequest
from .sensor_query import HomeAssistantSensorQueryError
from .sensor_query import SensorQueryRequest

__author__ = "Clive Bostock"
__date__ = "15-Jul-2026"
__description__ = (
    "Dispatches Home Assistant commands selected by core routing metadata."
)


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
        """Deprecated compatibility check using the shared core interceptor.

        Args:
            prompt: User prompt to evaluate before LLM dispatch.

        Returns:
            ``True`` when a declarative interception rule matches.
        """
        return self._legacy_plugin_route(prompt) is not None

    def execute(
        self,
        prompt: str,
        meta: dict[str, Any] | None = None,
    ) -> PluginExecutionResult | None:
        """Execute a supported Home Assistant command."""
        route = self._route_from_meta(meta) or self._legacy_plugin_route(prompt)
        if route is None:
            return None

        try:
            intent_name = route["intent_name"]
            arguments = route["arguments"]
            light_control_request = self._light_control_from_arguments(arguments)
            light_state_request = self._light_state_from_arguments(arguments)
            control_request = self._control_request_from_arguments(arguments)
            area_list_request = self._area_list_from_arguments(arguments)
            sensor_query_request = self._sensor_query_from_arguments(arguments)
        except HomeAssistantControlError as exc:
            return self._control_failure_response(exc.code, str(exc))

        if self._runtime_context is None:
            return self._failure_response("Home Assistant runtime context is unavailable.")

        if intent_name == "control_light" and light_control_request is not None:
            return self._execute_light_control(light_control_request)
        if intent_name == "query_light_state" and light_state_request is not None:
            return self._execute_light_state_query(light_state_request)
        if intent_name in {"control_device", "activate_scene"} and control_request is not None:
            return self._execute_control(control_request)
        if intent_name == "list_area_inventory" and area_list_request is None:
            return self._execute_area_inventory()
        if intent_name == "list_area_inventory" and area_list_request is not None:
            return self._execute_area_list(
                area_list_request.area,
                area_list_request.requested_domain,
            )
        if intent_name == "query_sensor_state" and sensor_query_request is not None:
            return self._execute_sensor_query(sensor_query_request)
        if intent_name != "resync_home_assistant":
            return None

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

    def _route_from_meta(
        self,
        meta: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Return selected route metadata supplied by core routing."""
        plugin_route = (meta or {}).get("plugin_route")
        if not isinstance(plugin_route, dict):
            return None
        if plugin_route.get("plugin_id") not in {None, "home_assistant"}:
            return None
        intent_name = str(plugin_route.get("intent_name") or "").strip()
        if not intent_name:
            return None
        raw_arguments = plugin_route.get("arguments", {})
        arguments = raw_arguments if isinstance(raw_arguments, dict) else {}
        return {
            "intent_name": intent_name,
            "arguments": dict(arguments),
        }

    def _legacy_plugin_route(self, prompt: str) -> dict[str, Any] | None:
        """Return a compatibility route for direct legacy callers only."""
        manifest = getattr(self._runtime_context, "manifest", None)
        if manifest is None:
            return None
        interceptor = HomeAssistantDialogInterceptor(
            manifest=manifest,
            resources=resource_reader_for_manifest(manifest),
            logger=self._logger,
        )
        interceptor.prepare()
        match = interceptor.intercept(prompt)
        if match is None:
            return None
        return {
            "intent_name": match.route_id,
            "arguments": mutable_mapping(match.arguments),
        }

    @staticmethod
    def _control_request_from_arguments(
        arguments: dict[str, Any],
    ) -> ControlRequest | None:
        """Build a validated control request from selected route arguments."""
        target = str(arguments.get("target") or "").strip()
        action = str(arguments.get("action") or "").strip()
        if not action or not target:
            return None
        return build_control_request(action, target)

    @staticmethod
    def _light_control_from_arguments(
        arguments: dict[str, Any],
    ) -> LightControlRequest | None:
        """Build a light-control request from selected route arguments."""
        payload = arguments.get("light_control")
        return LightControlRequest.from_payload(payload) if isinstance(payload, dict) else None

    @staticmethod
    def _light_state_from_arguments(
        arguments: dict[str, Any],
    ) -> LightStateQueryRequest | None:
        """Build a light-state request from selected route arguments."""
        payload = arguments.get("light_state_query")
        return LightStateQueryRequest.from_payload(payload) if isinstance(payload, dict) else None

    @staticmethod
    def _area_list_from_arguments(
        arguments: dict[str, Any],
    ) -> AreaListRequest | None:
        """Build an area-list request from selected route arguments."""
        payload = arguments.get("area_listing")
        if not isinstance(payload, dict):
            return None
        if payload.get("mode") != "area":
            return None
        area = str(payload.get("area") or "").strip()
        if not area:
            return None
        requested_domain = str(payload.get("requested_domain") or "").strip() or None
        return AreaListRequest(area=area, requested_domain=requested_domain)

    @staticmethod
    def _sensor_query_from_arguments(
        arguments: dict[str, Any],
    ) -> SensorQueryRequest | None:
        """Build a sensor-query request from selected route arguments."""
        payload = arguments.get("sensor_query")
        if not isinstance(payload, dict):
            return None
        intent = str(payload.get("intent") or "").strip()
        if not intent:
            return None
        areas = tuple(str(area).strip() for area in payload.get("areas") or () if str(area).strip())
        sensor_role = str(payload.get("sensor_role") or "").strip() or None
        return SensorQueryRequest(
            intent=intent,
            areas=areas,
            sensor_role=sensor_role,
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
        action_text = request.action.replace("_", " ")
        if status == "confirmed":
            content = f"Home Assistant confirmed {action_text} for {request.target}."
        elif status == "accepted_unverified":
            content = (
                f"Home Assistant control was not confirmed: {action_text} for "
                f"{request.target} was accepted, but the resulting state could not "
                "be verified."
            )
        else:
            return self._control_failure_response(
                "unconfirmed_result",
                "Home Assistant did not confirm the requested control change.",
            )
        return PluginExecutionResult(
            plugin_id="home_assistant",
            content=content,
            provenance={
                "command": "home_assistant.device_control",
                "action": request.action,
                "entity_ids": list(entity_ids),
                "status": status or "accepted",
            },
        )

    def _execute_light_control(self, request) -> PluginExecutionResult:
        """Dispatch one parsed rich light-control request to the managed service."""
        self._log_info("Home Assistant light-control command accepted.")
        try:
            result = self._runtime_context.run_service_command(
                "home_assistant",
                "light_control",
                request.to_payload(),
            )
        except HomeAssistantControlError as exc:
            return self._control_failure_response(exc.code, str(exc))
        except Exception as exc:
            self._log_error(f"Home Assistant light control failed: {exc}")
            return self._control_failure_response("execution_failed", str(exc))

        status = str(result.get("status") or "")
        entity_ids = tuple(result.get("entity_ids") or ())
        content = (
            str(result.get("content") or "Home Assistant confirmed the light change.")
            if status == "confirmed"
            else str(result.get("content") or "Home Assistant accepted the light change.")
        )
        return PluginExecutionResult(
            plugin_id="home_assistant",
            content=content,
            provenance={
                "command": "home_assistant.light_control",
                "entity_ids": list(entity_ids),
                "status": status or "accepted",
            },
        )

    def _execute_light_state_query(self, request) -> PluginExecutionResult:
        """Dispatch one parsed live light-state query to the managed service."""
        self._log_info("Home Assistant light-state query accepted.")
        try:
            result = self._runtime_context.run_service_command(
                "home_assistant",
                "light_state_query",
                request.to_payload(),
            )
        except HomeAssistantControlError as exc:
            return self._light_state_failure_response(exc.code, str(exc))
        except Exception as exc:
            self._log_error(f"Home Assistant light-state query failed: {exc}")
            return self._light_state_failure_response("execution_failed", str(exc))

        return PluginExecutionResult(
            plugin_id="home_assistant",
            content=str(result.get("content") or "Home Assistant light-state query failed."),
            provenance={
                "command": "home_assistant.light_state_query",
                "intent": request.intent,
                "entity_ids": list(result.get("entity_ids") or ()),
                "areas": list(result.get("areas") or ()),
                "status": str(result.get("status") or "complete"),
                "source": str(result.get("source") or "unknown"),
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
    def _light_state_failure_response(code: str, message: str) -> PluginExecutionResult:
        """Return an explicit user-facing light-state query failure."""
        return PluginExecutionResult(
            plugin_id="home_assistant",
            content=f"Home Assistant light-state query failed: {message}",
            provenance={
                "command": "home_assistant.light_state_query",
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
