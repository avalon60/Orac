"""Home Assistant plugin on-demand command entry point."""
# Author: Clive Bostock
# Date: 15-Jul-2026
# Description: Dispatches Home Assistant commands selected by plugin-owned interception metadata.

from __future__ import annotations

from typing import Any

from model.plugin_runtime import PluginExecutionResult

from .control import ControlRequest
from .control import build_control_request
from .control import parse_area_inventory_command
from .control import HomeAssistantControlError
from .control import parse_area_list_command
from .control import parse_control_command
from .light_control import parse_light_control_command
from .light_state_query import parse_light_state_query
from .intercept_metadata import InterceptMatch, InterceptMetadata
from .sensor_query import HomeAssistantSensorQueryError
from .sensor_query import parse_sensor_query

__author__ = "Clive Bostock"
__date__ = "15-Jul-2026"
__description__ = (
    "Dispatches Home Assistant commands selected by plugin-owned "
    "interception metadata."
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
        self._intercept_metadata = self._load_intercept_metadata()

    def can_handle(self, prompt: str) -> bool:
        """Return whether plugin-owned metadata claims the prompt.

        Args:
            prompt: User prompt to evaluate before LLM dispatch.

        Returns:
            ``True`` when a declarative interception rule matches.
        """
        return self._intercept_metadata.matches(prompt)

    def _load_intercept_metadata(self) -> InterceptMetadata:
        """Load plugin-owned interception metadata from the active manifest."""
        manifest = getattr(self._runtime_context, "manifest", None)
        if manifest is not None:
            return InterceptMetadata.from_plugin_manifest(manifest)
        return InterceptMetadata.from_plugin_module(__file__)

    def execute(
        self,
        prompt: str,
        meta: dict[str, Any] | None = None,
    ) -> PluginExecutionResult | None:
        """Execute a supported Home Assistant command."""
        intercept_match = self._intercept_metadata.match(prompt)
        if intercept_match is None:
            return None

        try:
            metadata_control_request = self._control_request_from_intercept(
                intercept_match
            )
            light_control_request = parse_light_control_command(prompt)
            light_state_request = parse_light_state_query(prompt)
            control_request = metadata_control_request or parse_control_command(prompt)
            area_inventory_request = parse_area_inventory_command(prompt)
            area_list_request = parse_area_list_command(prompt)
            sensor_query_request = parse_sensor_query(prompt)
        except HomeAssistantControlError as exc:
            return self._control_failure_response(exc.code, str(exc))

        is_resync = intercept_match.intent == "resynchronise_devices"
        if (
            not is_resync
            and light_control_request is None
            and light_state_request is None
            and control_request is None
            and area_inventory_request is None
            and area_list_request is None
            and sensor_query_request is None
        ):
            return None

        if self._runtime_context is None:
            return self._failure_response("Home Assistant runtime context is unavailable.")

        if light_control_request is not None:
            return self._execute_light_control(light_control_request)
        if light_state_request is not None:
            return self._execute_light_state_query(light_state_request)
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

    @staticmethod
    def _control_request_from_intercept(
        intercept_match: InterceptMatch,
    ) -> ControlRequest | None:
        """Build a control request from metadata captures and fixed parameters.

        Args:
            intercept_match: Structured interception result for the prompt.

        Returns:
            A validated control request when the rule supplies an action and
            target, otherwise ``None`` so the existing parser can be used.
        """
        if intercept_match.intent != "device_control":
            return None

        target = str(
            intercept_match.captures.get("target")
            or intercept_match.parameters.get("target")
            or ""
        ).strip()
        action = str(intercept_match.parameters.get("action") or "").strip()
        state = str(
            intercept_match.captures.get("state")
            or intercept_match.parameters.get("state")
            or ""
        ).strip().lower()
        if not action and state in {"on", "off"}:
            action = "turn_on" if state == "on" else "turn_off"
        if not action or not target:
            return None
        return build_control_request(action, target)

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
