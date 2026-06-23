"""Managed Home Assistant plugin service for startup synchronisation."""
# Author: Clive Bostock
# Date: 04-Jun-2026
# Description: Runs Home Assistant startup sync inside Orac's plugin service lifecycle.

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import threading
from typing import Any, Callable

from .client import HomeAssistantClient
from .client import HomeAssistantClientConfig
from .control import AreaInventoryRequest
from .control import AreaListRequest
from .control import ControlRequest
from .control import HomeAssistantControlError
from .repository import HomeAssistantRepository
from .light_control import LightControlError
from .light_control import LightControlRequest
from .light_control import build_light_service_data
from .light_control import light_target_display_name
from .light_state_query import LightStateQueryError
from .light_state_query import LightStateQueryRequest
from .light_state_query import render_light_state_query
from .sensor_query import DEFAULT_STALE_HOURS
from .sensor_query import SensorQueryRequest
from .sync import HomeAssistantSyncCoordinator
from .sync import SyncResult

__author__ = "Clive Bostock"
__date__ = "04-Jun-2026"
__description__ = "Runs Home Assistant startup sync inside Orac's plugin service lifecycle."

CONTROL_TIMEOUT_SECONDS = 5.0
SENSOR_QUERY_TIMEOUT_SECONDS = 5.0
LIGHT_CONTROL_TIMEOUT_SECONDS = 5.0
LIGHT_STATE_QUERY_TIMEOUT_SECONDS = 5.0

class HomeAssistantServiceError(RuntimeError):
    """Raised when the Home Assistant managed service cannot start safely."""


@dataclass
class HomeAssistantServiceState:
    """Operational state exposed through ``health`` and diagnostics."""

    started: bool = False
    stopped: bool = False
    api_reachable: bool = False
    last_error: str | None = None
    last_structural_sync_started: datetime | None = None
    last_structural_sync_completed: datetime | None = None
    last_state_sync_started: datetime | None = None
    last_state_sync_completed: datetime | None = None
    structural_sync_status: str = "not_started"
    state_sync_status: str = "not_started"


@dataclass(frozen=True)
class HomeAssistantRuntimeConfig:
    """Validated Home Assistant runtime configuration."""

    protocol: str
    host: str
    port: int
    access_token: str
    verify_ssl: bool
    websocket_path: str


class HomeAssistantService:
    """Managed long-running service that performs Home Assistant startup sync."""

    def __init__(
        self,
        logger: Any | None = None,
        config_mgr: Any | None = None,
        manifest: Any | None = None,
        *,
        client_factory: Callable[[HomeAssistantClientConfig], Any] | None = None,
        repository_factory: Callable[[Any], Any] | None = None,
        sync_coordinator_factory: Callable[..., Any] | None = None,
    ) -> None:
        """Initialise the service.

        Args:
            logger: Optional Orac logger.
            config_mgr: Orac configuration manager.
            manifest: Home Assistant plugin manifest.
            client_factory: Injectable client factory for tests.
            repository_factory: Injectable repository factory for tests.
            sync_coordinator_factory: Injectable sync coordinator factory.
        """
        self._logger = logger
        self._config_mgr = config_mgr
        self._manifest = manifest
        self._client_factory = client_factory or HomeAssistantClient
        self._repository_factory = repository_factory or HomeAssistantRepository
        self._sync_coordinator_factory = (
            sync_coordinator_factory or HomeAssistantSyncCoordinator
        )
        self._state = HomeAssistantServiceState()
        self._client: Any | None = None
        self._repository: Any | None = None
        self._sync_lock = threading.Lock()

    @property
    def state(self) -> HomeAssistantServiceState:
        """Return current service state for tests and diagnostics."""
        return self._state

    def run(self, context: Any) -> None:
        """Run startup sync, then remain alive until Orac requests stop."""
        self._state = HomeAssistantServiceState()
        try:
            self.resync(context)

            while not context.stop_event.wait(0.25):
                pass
        except Exception as exc:
            self._state.last_error = str(exc)
            self._log_error(f"Home Assistant service startup failed: {exc}")
            self._close_resources()
            raise
        finally:
            if getattr(context, "stop_event", None) is not None and context.stop_event.is_set():
                self._state.stopped = True
                self._close_resources()

    def handle_command(
        self,
        context: Any,
        command: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Handle a command dispatched through the Orac plugin service manager."""
        if command == "control":
            return self._control(context, payload or {})
        if command == "light_control":
            return self._light_control(context, payload or {})
        if command == "light_state_query":
            return self._light_state_query(context, payload or {})
        if command == "list_area":
            return self._list_area(context, payload or {})
        if command == "list_areas":
            return self._list_areas(context)
        if command == "sensor_query":
            return self._sensor_query(context, payload or {})
        if command == "status":
            return self._status(context)
        if command != "resync":
            raise HomeAssistantServiceError(
                f"Unsupported Home Assistant service command '{command}'."
            )
        structural_result, state_result = self.resync(context)
        return {
            "status": "complete",
            "structural_rows": structural_result.rows_processed,
            "state_rows": state_result.rows_processed,
        }

    def _status(self, context: Any) -> dict[str, Any]:
        """Return a redacted operational status summary for diagnostics."""
        repository = None
        try:
            repository = self._repository_factory(context)
            service_running = (
                self._state.started
                and not self._state.stopped
                and not getattr(context, "stop_event", threading.Event()).is_set()
            )
            summary = repository.status_summary(
                service_running=service_running,
                api_reachable=self._state.api_reachable,
                last_error_message=self._state.last_error,
            )
            return summary.as_dict()
        finally:
            if repository is not None:
                close = getattr(repository, "close", None)
                if callable(close):
                    close()

    def _control(self, context: Any, payload: dict[str, Any]) -> dict[str, Any]:
        """Resolve and execute one isolated low-risk Home Assistant control."""
        action = str(payload.get("action") or "").strip()
        target = str(payload.get("target") or "").strip()
        requested_domain = str(payload.get("requested_domain") or "").strip() or None
        if not action or not target:
            raise HomeAssistantControlError(
                "invalid_request",
                "Home Assistant control requires an action and target.",
            )

        repository = None
        client = None
        try:
            repository = self._repository_factory(context)
            resolved = repository.resolve_control(
                ControlRequest(
                    action=action,
                    target=target,
                    requested_domain=requested_domain,
                )
            )
            runtime_config = self._load_config(context)
            client = self._client_factory(
                HomeAssistantClientConfig(
                    protocol=runtime_config.protocol,
                    host=runtime_config.host,
                    port=runtime_config.port,
                    token=runtime_config.access_token,
                    verify_ssl=runtime_config.verify_ssl,
                    timeout_seconds=CONTROL_TIMEOUT_SECONDS,
                    websocket_path=runtime_config.websocket_path,
                )
            )
            confirmed_ids: set[str] = set()
            for service_call in resolved.service_calls:
                confirmation = client.call_service(
                    service_call.domain,
                    service_call.service,
                    service_call.entity_ids,
                )
                confirmed_ids.update(
                    str(item.get("entity_id") or "").strip().lower()
                    for item in confirmation
                )
            status = (
                "confirmed"
                if set(resolved.entity_ids).issubset(confirmed_ids)
                else "unconfirmed"
            )
            return {
                "status": status,
                "action": resolved.action,
                "entity_ids": list(resolved.entity_ids),
                "service_calls": [
                    {
                        "domain": service_call.domain,
                        "service": service_call.service,
                        "entity_ids": list(service_call.entity_ids),
                    }
                    for service_call in resolved.service_calls
                ],
                "resolution": resolved.resolution,
            }
        finally:
            for resource in (repository, client):
                close = getattr(resource, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        pass

    def _light_control(self, context: Any, payload: dict[str, Any]) -> dict[str, Any]:
        """Resolve and execute one isolated light-control request."""
        try:
            request = LightControlRequest.from_payload(payload)
            if not request.target or not request.kind:
                raise HomeAssistantControlError(
                    "invalid_request",
                    "Home Assistant light control requires a target and action.",
                )
        except HomeAssistantControlError:
            raise
        except Exception as exc:
            raise HomeAssistantControlError(
                "invalid_request",
                f"Home Assistant light control request is invalid: {exc}",
            ) from exc

        repository = None
        client = None
        try:
            repository = self._repository_factory(context)
            resolved = repository.resolve_control(
                ControlRequest(
                    action="turn_on",
                    target=request.target,
                    requested_domain="light",
                )
            )
            light_entity_ids = tuple(
                entity_id
                for service_call in resolved.service_calls
                if service_call.domain == "light"
                for entity_id in service_call.entity_ids
            )
            if not light_entity_ids:
                if any(service_call.domain == "switch" for service_call in resolved.service_calls):
                    raise HomeAssistantControlError(
                        "unsupported_capability",
                        "That device is a switch, so I can turn it on or off, but I cannot set brightness or colour.",
                    )
                raise HomeAssistantControlError(
                    "unsupported_capability",
                    "That target does not appear to expose a controllable light entity.",
                )

            runtime_config = self._load_config(context)
            client = self._client_factory(
                HomeAssistantClientConfig(
                    protocol=runtime_config.protocol,
                    host=runtime_config.host,
                    port=runtime_config.port,
                    token=runtime_config.access_token,
                    verify_ssl=runtime_config.verify_ssl,
                    timeout_seconds=LIGHT_CONTROL_TIMEOUT_SECONDS,
                    websocket_path=runtime_config.websocket_path,
                )
            )

            confirmations: list[dict[str, Any]] = []
            responses: list[str] = []
            display_target = light_target_display_name(
                {"attributes": {}},
                request.target,
            )
            for entity_id in light_entity_ids:
                try:
                    live_state = client.fetch_state(entity_id)
                    service_data, response = build_light_service_data(
                        request,
                        live_state,
                        target_label=display_target if len(light_entity_ids) > 1 else None,
                    )
                    responses.append(response)
                    confirmations.extend(
                        client.call_service(
                            "light",
                            "turn_on",
                            (entity_id,),
                            data=service_data,
                        )
                    )
                except LightControlError:
                    raise
                except Exception as exc:
                    raise HomeAssistantControlError(
                        "execution_failed",
                        f"Home Assistant light control failed: {exc}",
                    ) from exc

            confirmed_ids = {
                str(item.get("entity_id") or "").strip().lower()
                for item in confirmations
            }
            status = (
                "confirmed"
                if set(light_entity_ids).issubset(confirmed_ids)
                else "unconfirmed"
            )
            return {
                "status": status,
                "entity_ids": list(light_entity_ids),
                "service_calls": [
                    {
                        "domain": "light",
                        "service": "turn_on",
                        "entity_ids": [entity_id],
                    }
                    for entity_id in light_entity_ids
                ],
                "content": responses[0] if responses else "Light control complete.",
                "resolution": resolved.resolution,
            }
        except LightControlError as exc:
            raise HomeAssistantControlError(exc.code, str(exc)) from exc
        finally:
            for resource in (repository, client):
                close = getattr(resource, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        pass

    def _light_state_query(self, context: Any, payload: dict[str, Any]) -> dict[str, Any]:
        """Resolve and execute one isolated live light-state query."""
        try:
            request = LightStateQueryRequest.from_payload(payload)
            if not request.target or not request.intent:
                raise HomeAssistantControlError(
                    "invalid_request",
                    "Home Assistant light state queries require an intent and target.",
                )
        except HomeAssistantControlError:
            raise
        except Exception as exc:
            raise HomeAssistantControlError(
                "invalid_request",
                f"Home Assistant light state query request is invalid: {exc}",
            ) from exc

        repository = None
        client = None
        try:
            repository = self._repository_factory(context)
            resolved = repository.resolve_control(
                ControlRequest(
                    action="turn_on",
                    target=request.target,
                    requested_domain=request.requested_domain,
                )
            )
            entity_ids = resolved.entity_ids
            if request.scope != "area":
                if not entity_ids:
                    raise HomeAssistantControlError(
                        "unknown_target",
                        f"Home Assistant target '{request.target}' was not found.",
                    )
                if len(entity_ids) > 1:
                    raise HomeAssistantControlError(
                        "ambiguous_target",
                        f"Home Assistant target '{request.target}' is ambiguous.",
                    )

            if request.intent in {"brightness", "color", "setting", "color_temperature", "color_temperature_check"}:
                if all(service_call.domain == "switch" for service_call in resolved.service_calls):
                    raise HomeAssistantControlError(
                        "unsupported_capability",
                        "That device is a switch, so I can report whether it is on or off, but not brightness or colour.",
                    )
                if request.scope != "area" and len(entity_ids) == 1:
                    entity_domain = entity_ids[0].split(".", 1)[0]
                    if entity_domain == "switch":
                        raise HomeAssistantControlError(
                            "unsupported_capability",
                            "That device is a switch, so I can report whether it is on or off, but not brightness or colour.",
                        )

            runtime_config = self._load_config(context)
            client = self._client_factory(
                HomeAssistantClientConfig(
                    protocol=runtime_config.protocol,
                    host=runtime_config.host,
                    port=runtime_config.port,
                    token=runtime_config.access_token,
                    verify_ssl=runtime_config.verify_ssl,
                    timeout_seconds=LIGHT_STATE_QUERY_TIMEOUT_SECONDS,
                    websocket_path=runtime_config.websocket_path,
                )
            )

            live_states: list[dict[str, Any]] = []
            for entity_id in entity_ids:
                live_states.append(client.fetch_state(entity_id))

            result = render_light_state_query(request, live_states)
            return {
                "status": result.status,
                "content": result.content,
                "entity_ids": list(result.entity_ids or entity_ids),
                "areas": list(result.areas or (request.target,)),
                "source": "live_home_assistant",
            }
        except LightStateQueryError as exc:
            raise HomeAssistantControlError(exc.code, str(exc)) from exc
        finally:
            for resource in (repository, client):
                close = getattr(resource, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        pass

    def _list_area(self, context: Any, payload: dict[str, Any]) -> dict[str, Any]:
        """Return a read-only device listing for one exact Home Assistant area."""
        area = str(payload.get("area") or "").strip()
        requested_domain = str(payload.get("requested_domain") or "").strip() or None
        if not area:
            raise HomeAssistantControlError(
                "invalid_request",
                "Home Assistant area listing requires an area name.",
            )

        repository = None
        try:
            repository = self._repository_factory(context)
            result = repository.list_area(
                AreaListRequest(area=area, requested_domain=requested_domain)
            )
            return {
                "status": "complete",
                "area_name": result.area_name,
                "requested_domain": result.requested_domain,
                "devices": [
                    {
                        "name": device.name,
                        "entity_ids": list(device.entity_ids),
                        "domains": list(device.domains),
                    }
                    for device in result.devices
                ],
            }
        finally:
            close = getattr(repository, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass

    def _list_areas(self, context: Any) -> dict[str, Any]:
        """Return the known Home Assistant areas from synchronised shadow data."""
        repository = None
        try:
            repository = self._repository_factory(context)
            areas = repository.list_areas(AreaInventoryRequest())
            return {
                "status": "complete",
                "areas": list(areas),
            }
        finally:
            close = getattr(repository, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass

    def _sensor_query(self, context: Any, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute one sensor query using current read-only HA state."""
        intent = str(payload.get("intent") or "").strip()
        areas = tuple(
            str(area).strip()
            for area in payload.get("areas", ())
            if str(area).strip()
        )
        sensor_role = str(payload.get("sensor_role") or "").strip() or None
        if not intent:
            raise HomeAssistantServiceError(
                "Home Assistant sensor query requires an intent."
            )

        repository = None
        client = None
        try:
            repository = self._repository_factory(context)
            config = context.plugin_config()
            stale_after_hours = float(
                config.config_value(
                    section="home_assistant",
                    key="sensor_stale_hours",
                    default=str(DEFAULT_STALE_HOURS),
                )
            )
            runtime_config = self._load_config(context)
            client = self._client_factory(
                HomeAssistantClientConfig(
                    protocol=runtime_config.protocol,
                    host=runtime_config.host,
                    port=runtime_config.port,
                    token=runtime_config.access_token,
                    verify_ssl=runtime_config.verify_ssl,
                    timeout_seconds=SENSOR_QUERY_TIMEOUT_SECONDS,
                    websocket_path=runtime_config.websocket_path,
                )
            )
            request = SensorQueryRequest(
                intent=intent,
                areas=areas,
                sensor_role=sensor_role,
            )
            entity_ids = repository.resolve_sensor_entities(request)
            try:
                live_states = [client.fetch_state(entity_id) for entity_id in entity_ids]
            except Exception as exc:
                self._log_error(f"Home Assistant live sensor read failed: {exc}")
                cached_result = repository.query_cached_sensors(
                    request,
                    stale_after_hours=max(0.1, stale_after_hours),
                )
                return {
                    "status": cached_result.status,
                    "source": "cached_shadow",
                    "content": cached_result.content,
                    "entity_ids": list(cached_result.entity_ids),
                    "areas": list(cached_result.areas),
                }
            result = repository.query_sensors(
                request,
                stale_after_hours=max(0.1, stale_after_hours),
                live_states=live_states,
            )
            return {
                "status": result.status,
                "source": "live_home_assistant",
                "content": f"Live Home Assistant reading: {result.content}",
                "entity_ids": list(result.entity_ids),
                "areas": list(result.areas),
            }
        finally:
            for resource in (repository, client):
                close = getattr(resource, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        pass

    def resync(self, context: Any) -> tuple[SyncResult, SyncResult]:
        """Run the managed Home Assistant structural and state synchronisation."""
        if not self._sync_lock.acquire(blocking=False):
            raise HomeAssistantServiceError("Home Assistant sync is already running.")
        try:
            self._state.stopped = False
            self._state.last_error = None
            self._state.api_reachable = False
            self._state.structural_sync_status = "running"
            self._state.state_sync_status = "not_started"
            self._log_info("Resyncing Home Assistant devices and entities.")

            self._close_resources()
            runtime_config = self._load_config(context)
            self._log_info("Home Assistant access token loaded from plugin PAT vault.")
            self._client = self._client_factory(
                HomeAssistantClientConfig(
                    protocol=runtime_config.protocol,
                    host=runtime_config.host,
                    port=runtime_config.port,
                    token=runtime_config.access_token,
                    verify_ssl=runtime_config.verify_ssl,
                    websocket_path=runtime_config.websocket_path,
                )
            )
            self._repository = self._repository_factory(context)
            self._client.check_api()
            self._state.api_reachable = True

            coordinator = self._sync_coordinator_factory(
                client=self._client,
                repository=self._repository,
            )
            structural_result, state_result = coordinator.run_initial_sync()
            self._record_structural_success(structural_result)
            self._record_state_success(state_result)
            self._state.started = True
            self._log_info("Home Assistant sync complete.")
            return structural_result, state_result
        except Exception as exc:
            self._state.last_error = str(exc)
            self._state.started = False
            if self._state.structural_sync_status == "running":
                self._state.structural_sync_status = "failed"
            if self._state.state_sync_status in {"running", "not_started"}:
                self._state.state_sync_status = "failed"
            self._log_error(f"Home Assistant sync failed: {exc}")
            self._close_resources()
            raise
        finally:
            self._sync_lock.release()

    def stop(self, context: Any) -> None:
        """Request service shutdown and close owned resources."""
        context.stop_event.set()
        self._state.stopped = True
        self._close_resources()

    def health(self, context: Any) -> bool:
        """Return whether the service is currently healthy."""
        if self._state.stopped or getattr(context, "stop_event", None).is_set():
            return False
        return (
            self._state.started
            and self._state.api_reachable
            and self._state.structural_sync_status == "complete"
            and self._state.state_sync_status == "complete"
            and self._state.last_error is None
        )

    def _load_config(self, context: Any) -> HomeAssistantRuntimeConfig:
        """Validate and return Home Assistant runtime configuration."""
        config_mgr = self._plugin_config_manager(context)
        if config_mgr is None:
            raise HomeAssistantServiceError("Home Assistant configuration manager is unavailable.")

        host = self._required_config(config_mgr, "home_assistant", "host")
        port = self._required_int_config(config_mgr, "home_assistant", "port")
        access_token = self._secret_vault(context).get().strip()
        if not access_token:
            raise HomeAssistantServiceError(
                "Home Assistant access token is missing. Create it with: "
                "bin/plugin-pat-mgr.sh --plugin home_assistant --set access_token"
            )

        protocol = self._config_value(config_mgr, "home_assistant", "protocol", "http") or "http"
        verify_ssl = self._bool_config_value(config_mgr, "home_assistant", "verify_ssl", True)
        websocket_path = (
            str(
                self._config_value(
                    config_mgr,
                    "home_assistant",
                    "websocket_path",
                    "/api/websocket",
                )
                or ""
            )
            .strip()
            or "/api/websocket"
        )
        return HomeAssistantRuntimeConfig(
            protocol=str(protocol).strip().lower(),
            host=host,
            port=port,
            access_token=access_token,
            verify_ssl=verify_ssl,
            websocket_path=websocket_path,
        )

    def _plugin_config_manager(self, context: Any) -> Any | None:
        """Return the scoped plugin configuration manager from context."""
        plugin_config = getattr(context, "plugin_config", None)
        if callable(plugin_config):
            return plugin_config()
        return None

    def _secret_vault(self, context: Any) -> Any:
        """Return the scoped Home Assistant secret vault from context."""
        vault = getattr(context, "secret_vault", None)
        if vault is None:
            raise HomeAssistantServiceError(
                "Home Assistant access token vault is unavailable. Create the token with: "
                "bin/plugin-pat-mgr.sh --plugin home_assistant --set access_token"
            )
        return vault

    def _required_config(self, config_mgr: Any, section: str, key: str) -> str:
        """Return a required non-empty string config value."""
        value = str(self._config_value(config_mgr, section, key, "") or "").strip()
        if not value:
            raise HomeAssistantServiceError(
                f"Missing required Home Assistant configuration [{section}].{key}."
            )
        return value

    def _required_int_config(self, config_mgr: Any, section: str, key: str) -> int:
        """Return a required integer config value."""
        value = self._config_value(config_mgr, section, key, None)
        if value is None or str(value).strip() == "":
            raise HomeAssistantServiceError(
                f"Missing required Home Assistant configuration [{section}].{key}."
            )
        try:
            if hasattr(config_mgr, "int_config_value"):
                return int(config_mgr.int_config_value(section, key, default=value))
            return int(value)
        except (TypeError, ValueError) as exc:
            raise HomeAssistantServiceError(
                f"Invalid Home Assistant integer configuration [{section}].{key}."
            ) from exc

    def _config_value(self, config_mgr: Any, section: str, key: str, default: Any) -> Any:
        """Return one config value from the configured manager."""
        return config_mgr.config_value(section=section, key=key, default=default)

    def _bool_config_value(self, config_mgr: Any, section: str, key: str, default: bool) -> bool:
        """Return one boolean config value from the configured manager."""
        if hasattr(config_mgr, "bool_config_value"):
            return bool(config_mgr.bool_config_value(section, key, default=default))
        value = self._config_value(config_mgr, section, key, default)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _record_structural_success(self, result: SyncResult) -> None:
        """Record structural sync success in service health state."""
        self._state.last_structural_sync_started = result.started_on
        self._state.last_structural_sync_completed = result.completed_on
        self._state.structural_sync_status = "complete"

    def _record_state_success(self, result: SyncResult) -> None:
        """Record state sync success in service health state."""
        self._state.last_state_sync_started = result.started_on
        self._state.last_state_sync_completed = result.completed_on
        self._state.state_sync_status = "complete"

    def _close_resources(self) -> None:
        """Close resources owned by the service."""
        for resource in (self._repository, self._client):
            close = getattr(resource, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass

    def _log_info(self, message: str) -> None:
        """Write an info message when a logger is available."""
        if self._logger is not None and hasattr(self._logger, "log_info"):
            self._logger.log_info(message)

    def _log_error(self, message: str) -> None:
        """Write an error message when a logger is available."""
        if self._logger is not None and hasattr(self._logger, "log_error"):
            self._logger.log_error(message)
