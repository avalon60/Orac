"""Managed Home Assistant plugin service for startup synchronisation."""
# Author: Clive Bostock
# Date: 04-Jun-2026
# Description: Runs Home Assistant startup sync inside Orac's plugin service lifecycle.

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from fnmatch import fnmatchcase
import threading
import time
from typing import Any, Callable

from model.plugin_runtime import PluginServiceCommandAuthority

from .client import HomeAssistantClient
from .client import HomeAssistantClientConfig
from .capabilities import CapabilitySnapshot
from .capabilities import PrimitiveCapability
from .capabilities import prepare_capability_operation
from .capabilities import update_capability_state
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
CONTROL_VERIFICATION_TIMEOUT_SECONDS = 2.0
CONTROL_VERIFICATION_INTERVAL_SECONDS = 0.25

_CONFIRMATION_REQUIRED_PRIMITIVES = frozenset(
    {
        PrimitiveCapability.OPEN,
        PrimitiveCapability.CLOSE,
        PrimitiveCapability.STOP,
        PrimitiveCapability.SET_POSITION,
        PrimitiveCapability.LOCK,
        PrimitiveCapability.UNLOCK,
        PrimitiveCapability.TRIGGER_ACTION,
        PrimitiveCapability.SET_VALUE,
        PrimitiveCapability.SELECT_OPTION,
    }
)

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
    capability_generation: str | None = None
    capability_entity_count: int = 0
    capability_binding_count: int = 0
    capability_action_count: int = 0
    capability_unmapped_action_count: int = 0
    event_listener_status: str = "not_started"
    last_event_at: datetime | None = None
    event_error_count: int = 0


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
        sleep: Callable[[float], None] | None = None,
        control_verification_timeout_seconds: float = CONTROL_VERIFICATION_TIMEOUT_SECONDS,
        control_verification_interval_seconds: float = CONTROL_VERIFICATION_INTERVAL_SECONDS,
    ) -> None:
        """Initialise the service.

        Args:
            logger: Optional Orac logger.
            config_mgr: Orac configuration manager.
            manifest: Home Assistant plugin manifest.
            client_factory: Injectable client factory for tests.
            repository_factory: Injectable repository factory for tests.
            sync_coordinator_factory: Injectable sync coordinator factory.
            sleep: Injectable sleep function for bounded polling tests.
            control_verification_timeout_seconds: Maximum control verification wait.
            control_verification_interval_seconds: Delay between verification reads.
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
        self._capability_snapshot: CapabilitySnapshot | None = None
        self._snapshot_lock = threading.Lock()
        self._event_thread: threading.Thread | None = None
        self._refresh_requested = threading.Event()
        self._sync_lock = threading.Lock()
        self._sleep = sleep or time.sleep
        self._control_verification_timeout_seconds = max(
            0.0,
            float(control_verification_timeout_seconds),
        )
        self._control_verification_interval_seconds = max(
            0.0,
            float(control_verification_interval_seconds),
        )

    @property
    def state(self) -> HomeAssistantServiceState:
        """Return current service state for tests and diagnostics."""
        return self._state

    def run(self, context: Any) -> None:
        """Run startup sync, then remain alive until Orac requests stop."""
        self._state = HomeAssistantServiceState()
        try:
            self.resync(context)
            self._start_event_listener(context)
            refresh_seconds = self._structural_refresh_seconds(context)
            next_refresh = (
                time.monotonic() + refresh_seconds
                if refresh_seconds is not None
                else None
            )

            while not context.stop_event.wait(0.25):
                refresh_due = (
                    next_refresh is not None and time.monotonic() >= next_refresh
                )
                if self._refresh_requested.is_set() or refresh_due:
                    self._refresh_requested.clear()
                    self.resync(context)
                    self._start_event_listener(context)
                    refresh_seconds = self._structural_refresh_seconds(context)
                    next_refresh = (
                        time.monotonic() + refresh_seconds
                        if refresh_seconds is not None
                        else None
                    )
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
        if command == "capability_inventory":
            return self._capability_inventory(context, payload or {})
        if command == "execute_capability":
            return self._execute_capability(context, payload or {})
        if command != "resync":
            raise HomeAssistantServiceError(
                f"Unsupported Home Assistant service command '{command}'."
            )
        structural_result, state_result = self.resync(context)
        self._start_event_listener(context)
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
            result = summary.as_dict()
            result.update(
                {
                    "capability_generation": self._state.capability_generation,
                    "capability_entity_count": self._state.capability_entity_count,
                    "capability_binding_count": self._state.capability_binding_count,
                    "capability_action_count": self._state.capability_action_count,
                    "capability_unmapped_action_count": (
                        self._state.capability_unmapped_action_count
                    ),
                    "event_listener_status": self._state.event_listener_status,
                    "last_event_at": (
                        self._state.last_event_at.isoformat()
                        if self._state.last_event_at
                        else None
                    ),
                    "event_error_count": self._state.event_error_count,
                }
            )
            return result
        finally:
            if repository is not None:
                close = getattr(repository, "close", None)
                if callable(close):
                    close()

    def _capability_inventory(
        self,
        context: Any,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Return a bounded semantic inventory without raw HA service schemas."""
        with self._snapshot_lock:
            snapshot = self._capability_snapshot
        if snapshot is None:
            raise HomeAssistantServiceError(
                "Home Assistant capabilities are unavailable until sync completes."
            )
        config = self._plugin_config_manager(context)
        default_size = int(
            self._config_value(
                config,
                "home_assistant",
                "capability_page_size",
                50,
            )
        )
        maximum_size = int(
            self._config_value(
                config,
                "home_assistant",
                "capability_max_page_size",
                200,
            )
        )
        try:
            offset = max(0, int(payload.get("offset", 0)))
            limit = max(1, min(int(payload.get("limit", default_size)), maximum_size))
        except (TypeError, ValueError) as exc:
            raise HomeAssistantServiceError(
                "Home Assistant capability pagination is invalid."
            ) from exc
        visible_ids = sorted(
            entity_id
            for entity_id, entity in snapshot.entities.items()
            if not entity.disabled and not entity.hidden
            and self._entity_policy_allows(context, entity_id, "visible")
        )
        visible_set = frozenset(visible_ids)
        page = visible_ids[offset : offset + limit]
        page_devices = sorted(
            {
                snapshot.entities[entity_id].device_id
                for entity_id in page
                if snapshot.entities[entity_id].device_id
            }
        )

        def capability_visible(entity_id: str, primitive: PrimitiveCapability) -> bool:
            operation = (
                "read" if primitive == PrimitiveCapability.READ_STATE else "control"
            )
            return self._entity_policy_allows(context, entity_id, operation)

        return {
            "status": "complete",
            "generation": snapshot.generation,
            "offset": offset,
            "limit": limit,
            "next_offset": offset + limit if offset + limit < len(visible_ids) else None,
            "total": len(visible_ids),
            "entities": [
                {
                    "entity_id": entity_id,
                    "name": snapshot.entities[entity_id].name,
                    "domain": snapshot.entities[entity_id].domain,
                    "device_id": snapshot.entities[entity_id].device_id,
                    "area_id": snapshot.entities[entity_id].area_id,
                    "capabilities": [
                        {
                            "name": binding.primitive.value,
                            "parameters": dict(binding.parameters),
                            "available": binding.available,
                        }
                        for binding in snapshot.bindings.get(entity_id, ())
                        if capability_visible(entity_id, binding.primitive)
                    ],
                }
                for entity_id in page
            ],
            "devices": [
                {
                    "device_id": device_id,
                    "name": snapshot.devices[device_id].name,
                    "area_id": snapshot.devices[device_id].area_id,
                    "entity_ids": [
                        entity_id
                        for entity_id in snapshot.devices[device_id].entity_ids
                        if entity_id in visible_set
                    ],
                    "capabilities": [
                        capability.value
                        for capability, entity_ids in sorted(
                            snapshot.devices[device_id].capabilities.items(),
                            key=lambda item: item[0].value,
                        )
                        if entity_ids
                        and all(
                            entity_id in visible_set
                            and capability_visible(entity_id, capability)
                            for entity_id in entity_ids
                        )
                    ],
                }
                for device_id in page_devices
            ],
        }

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
            primitive = {
                "turn_on": PrimitiveCapability.TURN_ON,
                "turn_off": PrimitiveCapability.TURN_OFF,
                "activate": PrimitiveCapability.TRIGGER_ACTION,
            }.get(resolved.action)
            if primitive is not None:
                self._require_capability(resolved.entity_ids, primitive)
            self._require_entity_policy(context, resolved.entity_ids, "control")
            runtime_config = self._load_config(context)
            client = self._client_factory(
                HomeAssistantClientConfig(
                    protocol=runtime_config.protocol,
                    host=runtime_config.host,
                    port=runtime_config.port,
                    token=runtime_config.access_token,
                    verify_ssl=runtime_config.verify_ssl,
                    timeout_seconds=self._runtime_float(
                        context,
                        "control_timeout_seconds",
                        CONTROL_TIMEOUT_SECONDS,
                    ),
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
                confirmed_ids.update(_service_response_entity_ids(confirmation))
            status = self._control_status_after_service_call(
                client,
                resolved,
                confirmed_ids,
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

    def _control_status_after_service_call(
        self,
        client: Any,
        resolved: Any,
        confirmed_ids: set[str],
    ) -> str:
        """Return confirmed, accepted_unverified, or fail for a control call."""
        if resolved.action == "activate":
            if set(resolved.entity_ids).issubset(confirmed_ids):
                return "accepted_unverified"
            return "accepted_unverified"
        if resolved.action == "toggle":
            return (
                "accepted_unverified"
                if set(resolved.entity_ids).issubset(confirmed_ids)
                else "accepted_unverified"
            )
        if resolved.action not in {"turn_on", "turn_off"}:
            return "accepted_unverified"

        expected_state = "on" if resolved.action == "turn_on" else "off"
        verification = self._poll_control_state(
            client,
            resolved.entity_ids,
            expected_state,
        )
        if verification == "confirmed":
            return "confirmed"
        if verification == "state_mismatch":
            raise HomeAssistantControlError(
                "state_mismatch",
                "Home Assistant accepted the request, but the observed target "
                f"state did not become {expected_state}.",
            )
        return "accepted_unverified"

    def _poll_control_state(
        self,
        client: Any,
        entity_ids: tuple[str, ...],
        expected_state: str,
    ) -> str:
        """Poll Home Assistant briefly until controlled entities match state."""
        attempts = self._control_verification_attempts()
        last_observed: dict[str, str] = {}
        saw_readable_state = False
        for attempt in range(attempts):
            observed = self._read_entity_states(client, entity_ids)
            if observed:
                last_observed = observed
                readable_states = {
                    state for state in observed.values() if state in {"on", "off"}
                }
                saw_readable_state = saw_readable_state or bool(readable_states)
                if all(observed.get(entity_id) == expected_state for entity_id in entity_ids):
                    return "confirmed"
            if attempt < attempts - 1:
                self._sleep(self._control_verification_interval_seconds)

        if saw_readable_state and all(
            last_observed.get(entity_id) in {"on", "off"}
            and last_observed.get(entity_id) != expected_state
            for entity_id in entity_ids
        ):
            return "state_mismatch"
        return "accepted_unverified"

    def _control_verification_attempts(self) -> int:
        """Return a deterministic bounded polling count for control verification."""
        interval = self._control_verification_interval_seconds
        timeout = self._control_verification_timeout_seconds
        if timeout <= 0 or interval <= 0:
            return 1
        return max(1, int(timeout / interval) + 1)

    def _require_capability(
        self,
        entity_ids: tuple[str, ...],
        primitive: PrimitiveCapability,
    ) -> None:
        """Require a discovered primitive binding for every target entity.

        A missing snapshot retains compatibility for injected legacy services
        that have not completed structural discovery. Once a snapshot exists,
        service execution fails closed when Home Assistant did not advertise the
        requested action for every resolved entity.
        """
        if self._capability_snapshot is None:
            return
        unsupported = [
            entity_id
            for entity_id in entity_ids
            if not any(
                binding.primitive == primitive
                and binding.available
                and binding.action_id is not None
                for binding in self._capability_snapshot.bindings.get(entity_id, ())
            )
        ]
        if unsupported:
            raise HomeAssistantControlError(
                "unsupported_capability",
                "Home Assistant does not advertise the "
                f"'{primitive.value}' capability for: {', '.join(unsupported)}.",
            )

    @staticmethod
    def _read_entity_states(client: Any, entity_ids: tuple[str, ...]) -> dict[str, str]:
        """Return currently readable entity states, ignoring transient read errors."""
        observed: dict[str, str] = {}
        for entity_id in entity_ids:
            try:
                state = client.fetch_state(entity_id)
            except Exception:
                continue
            value = str(state.get("state") or "").strip().lower()
            if value:
                observed[entity_id] = value
        return observed

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

            primitive = {
                "brightness_pct": PrimitiveCapability.SET_LEVEL,
                "brightness_step": PrimitiveCapability.SET_LEVEL,
                "color_name": PrimitiveCapability.SET_COLOUR,
                "color_temp_kelvin": PrimitiveCapability.SET_COLOUR_TEMPERATURE,
                "color_temp_preset": PrimitiveCapability.SET_COLOUR_TEMPERATURE,
                "color_temp_step": PrimitiveCapability.SET_COLOUR_TEMPERATURE,
            }.get(request.kind)
            if primitive is not None:
                self._require_capability(light_entity_ids, primitive)
            self._require_entity_policy(context, light_entity_ids, "control")

            runtime_config = self._load_config(context)
            client = self._client_factory(
                HomeAssistantClientConfig(
                    protocol=runtime_config.protocol,
                    host=runtime_config.host,
                    port=runtime_config.port,
                    token=runtime_config.access_token,
                    verify_ssl=runtime_config.verify_ssl,
                    timeout_seconds=self._runtime_float(
                        context,
                        "light_control_timeout_seconds",
                        LIGHT_CONTROL_TIMEOUT_SECONDS,
                    ),
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
            self._require_entity_policy(context, entity_ids, "read")
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
                    timeout_seconds=self._runtime_float(
                        context,
                        "light_state_query_timeout_seconds",
                        LIGHT_STATE_QUERY_TIMEOUT_SECONDS,
                    ),
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
            visible_devices = []
            for device in result.devices:
                visible_entity_ids = tuple(
                    entity_id
                    for entity_id in device.entity_ids
                    if self._entity_policy_allows(context, entity_id, "visible")
                )
                if visible_entity_ids:
                    visible_devices.append((device, visible_entity_ids))
            return {
                "status": "complete",
                "area_name": result.area_name,
                "requested_domain": result.requested_domain,
                "devices": [
                    {
                        "name": device.name,
                        "entity_ids": list(entity_ids),
                        "domains": sorted(
                            {entity_id.partition(".")[0] for entity_id in entity_ids}
                        ),
                    }
                    for device, entity_ids in visible_devices
                ],
            }
        finally:
            close = getattr(repository, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass

    def _execute_capability(
        self,
        context: Any,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute one host-authorised semantic primitive from the snapshot."""
        authority = payload.get("_orac_authority")
        if (
            not isinstance(authority, PluginServiceCommandAuthority)
            or authority.plugin_id != "home_assistant"
            or authority.policy_status != "allowed"
            or not authority.principal_username
            or "home_assistant.generic_control" not in authority.capabilities
        ):
            raise HomeAssistantControlError(
                "policy_denied",
                "The Orac host did not authorise this Home Assistant operation.",
            )
        with self._snapshot_lock:
            snapshot = self._capability_snapshot
        if snapshot is None:
            raise HomeAssistantControlError(
                "capabilities_unavailable",
                "Home Assistant capabilities are unavailable until sync completes.",
            )
        try:
            primitive = PrimitiveCapability(str(payload.get("capability") or ""))
            raw_parameters = payload.get("parameters")
            parameters = raw_parameters if isinstance(raw_parameters, dict) else {}
            operations = prepare_capability_operation(
                snapshot,
                str(payload.get("target_id") or ""),
                primitive,
                parameters,
                max_entities=int(
                    self._config_value(
                        self._plugin_config_manager(context),
                        "home_assistant",
                        "max_entities_per_operation",
                        25,
                    )
                ),
            )
        except (TypeError, ValueError) as exc:
            raise HomeAssistantControlError("unsupported_capability", str(exc)) from exc
        if self._confirmation_required(context, primitive) and not authority.trusted_confirmation:
            raise HomeAssistantControlError(
                "confirmation_required",
                f"Home Assistant capability '{primitive.value}' requires confirmation.",
            )
        entity_ids = tuple(
            entity_id
            for operation in operations
            for entity_id in operation.entity_ids
        )
        self._require_entity_policy(
            context,
            entity_ids,
            "read" if primitive == PrimitiveCapability.READ_STATE else "control",
        )

        runtime_config = self._load_config(context)
        client = self._client_factory(
            HomeAssistantClientConfig(
                protocol=runtime_config.protocol,
                host=runtime_config.host,
                port=runtime_config.port,
                token=runtime_config.access_token,
                verify_ssl=runtime_config.verify_ssl,
                timeout_seconds=self._runtime_float(
                    context,
                    "control_timeout_seconds",
                    CONTROL_TIMEOUT_SECONDS,
                ),
                websocket_path=runtime_config.websocket_path,
            )
        )
        try:
            results: list[dict[str, Any]] = []
            for operation in operations:
                if operation.action_id is None:
                    results.extend(
                        client.fetch_state(entity_id)
                        for entity_id in operation.entity_ids
                    )
                    continue
                domain, service = operation.action_id.split(".", 1)
                results.extend(
                    client.call_service(
                        domain,
                        service,
                        operation.entity_ids,
                        data=dict(operation.service_data),
                    )
                )
            return {
                "status": "complete",
                "capability": primitive.value,
                "target_id": str(payload.get("target_id") or "").strip().lower(),
                "entity_ids": [
                    entity_id
                    for operation in operations
                    for entity_id in operation.entity_ids
                ],
                "result_count": len(results),
                "generation": snapshot.generation,
                "values": (
                    [self._semantic_state_value(item) for item in results]
                    if primitive == PrimitiveCapability.READ_STATE
                    else []
                ),
            }
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()

    @staticmethod
    def _semantic_state_value(state: dict[str, Any]) -> dict[str, Any]:
        """Return a small allowlisted read-state result for model use."""
        attributes = state.get("attributes")
        attributes = attributes if isinstance(attributes, dict) else {}
        return {
            "entity_id": str(state.get("entity_id") or "").strip().lower(),
            "state": state.get("state"),
            "unit_of_measurement": attributes.get("unit_of_measurement"),
            "device_class": attributes.get("device_class"),
            "friendly_name": attributes.get("friendly_name"),
            "last_changed": state.get("last_changed"),
            "last_updated": state.get("last_updated"),
        }

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
                    timeout_seconds=self._runtime_float(
                        context,
                        "sensor_query_timeout_seconds",
                        SENSOR_QUERY_TIMEOUT_SECONDS,
                    ),
                    websocket_path=runtime_config.websocket_path,
                )
            )
            request = SensorQueryRequest(
                intent=intent,
                areas=areas,
                sensor_role=sensor_role,
            )
            entity_ids = repository.resolve_sensor_entities(request)
            self._require_entity_policy(context, entity_ids, "read")
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
                target_service_discovery_limit=int(
                    self._config_value(
                        self._plugin_config_manager(context),
                        "home_assistant",
                        "target_service_discovery_limit",
                        250,
                    )
                ),
            )
            structural_result, state_result = coordinator.run_initial_sync()
            snapshot = getattr(coordinator, "capability_snapshot", None)
            if snapshot is not None:
                with self._snapshot_lock:
                    self._publish_capability_snapshot(snapshot)
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

    def _runtime_float(self, context: Any, key: str, default: float) -> float:
        """Return one positive configurable runtime duration."""
        config_mgr = self._plugin_config_manager(context)
        try:
            value = float(
                self._config_value(config_mgr, "home_assistant", key, default)
            )
        except (TypeError, ValueError) as exc:
            raise HomeAssistantServiceError(
                f"Invalid Home Assistant duration [home_assistant].{key}."
            ) from exc
        if value <= 0:
            raise HomeAssistantServiceError(
                f"Home Assistant duration [home_assistant].{key} must be positive."
            )
        return value

    def _structural_refresh_seconds(self, context: Any) -> float | None:
        """Return the configured periodic structural reconciliation interval."""
        config_mgr = self._plugin_config_manager(context)
        mode = str(
            self._config_value(
                config_mgr,
                "home_assistant",
                "structural_refresh_mode",
                "hourly",
            )
            or ""
        ).strip().lower()
        if mode in {"disabled", "off", "startup_only"}:
            return None
        if mode not in {"hourly", "periodic"}:
            raise HomeAssistantServiceError(
                "Home Assistant structural_refresh_mode must be hourly, periodic, or disabled."
            )
        minutes = self._runtime_float(context, "structural_refresh_minutes", 60.0)
        return minutes * 60.0

    def _entity_policy_allows(
        self,
        context: Any,
        entity_id: str,
        operation: str,
    ) -> bool:
        """Apply host-owned entity visibility/read/control pattern policy."""
        config_mgr = self._plugin_config_manager(context)
        key = {
            "visible": "visible_entity_patterns",
            "read": "readable_entity_patterns",
            "control": "controllable_entity_patterns",
        }.get(operation)
        if key is None:
            return False
        denied = self._policy_patterns(
            self._config_value(
                config_mgr,
                "home_assistant",
                "denied_entity_patterns",
                "",
            )
        )
        if any(fnmatchcase(entity_id, pattern) for pattern in denied):
            return False
        allowed = self._policy_patterns(
            self._config_value(config_mgr, "home_assistant", key, "*")
        )
        return any(fnmatchcase(entity_id, pattern) for pattern in allowed)

    def _require_entity_policy(
        self,
        context: Any,
        entity_ids: tuple[str, ...],
        operation: str,
    ) -> None:
        """Fail closed when host configuration denies any resolved entity."""
        with self._snapshot_lock:
            snapshot = self._capability_snapshot
        denied = [
            entity_id
            for entity_id in entity_ids
            if (
                snapshot is not None
                and entity_id in snapshot.entities
                and (
                    snapshot.entities[entity_id].hidden
                    or snapshot.entities[entity_id].disabled
                )
            )
            or not self._entity_policy_allows(context, entity_id, "visible")
            or not self._entity_policy_allows(context, entity_id, operation)
        ]
        if denied:
            raise HomeAssistantControlError(
                "policy_denied",
                "Orac policy does not permit this Home Assistant operation for: "
                + ", ".join(denied)
                + ".",
            )

    def _confirmation_required(
        self,
        context: Any,
        primitive: PrimitiveCapability,
    ) -> bool:
        """Return host-configured confirmation sensitivity for a primitive."""
        default = ",".join(sorted(item.value for item in _CONFIRMATION_REQUIRED_PRIMITIVES))
        configured = self._policy_patterns(
            self._config_value(
                self._plugin_config_manager(context),
                "home_assistant",
                "confirmation_required_capabilities",
                default,
            )
        )
        return primitive.value in configured

    @staticmethod
    def _policy_patterns(value: Any) -> tuple[str, ...]:
        """Return canonical comma-separated host policy tokens."""
        return tuple(
            token.strip().lower()
            for token in str(value or "").split(",")
            if token.strip()
        )

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

    def _start_event_listener(self, context: Any) -> None:
        """Start the optional library-managed Home Assistant event stream."""
        client = self._client
        listen = getattr(client, "listen_events", None)
        config_mgr = self._plugin_config_manager(context)
        enabled = self._bool_config_value(
            config_mgr,
            "home_assistant",
            "enable_websocket",
            True,
        )
        if not enabled or not callable(listen) or context.stop_event.is_set():
            self._state.event_listener_status = "disabled" if not enabled else "unavailable"
            return
        if self._event_thread is not None and self._event_thread.is_alive():
            return
        reconnect_seconds = self._runtime_float(context, "ws_reconnect_seconds", 10.0)
        ping_interval = self._runtime_float(context, "ws_ping_interval_seconds", 30.0)
        ping_timeout = self._runtime_float(context, "ws_ping_timeout_seconds", 10.0)

        def run_listener() -> None:
            self._state.event_listener_status = "running"
            try:
                listen(
                    lambda event: self._handle_event(context, event),
                    reconnect_seconds=reconnect_seconds,
                    ping_interval_seconds=ping_interval,
                    ping_timeout_seconds=ping_timeout,
                )
            except Exception as exc:
                if not context.stop_event.is_set():
                    self._state.event_error_count += 1
                    self._state.event_listener_status = "failed"
                    self._log_error(f"Home Assistant event listener failed: {exc}")
            finally:
                if self._state.event_listener_status == "running":
                    self._state.event_listener_status = (
                        "stopped" if context.stop_event.is_set() else "disconnected"
                    )

        self._event_thread = threading.Thread(
            target=run_listener,
            name="home-assistant-events",
            daemon=True,
        )
        self._event_thread.start()

    def _handle_event(self, context: Any, event: dict[str, Any]) -> None:
        """Apply state events or request full refresh for registry changes."""
        event_type = str(event.get("event_type") or "").strip()
        if event_type in {
            "area_registry_updated",
            "device_registry_updated",
            "entity_registry_updated",
            "service_registered",
            "service_removed",
        }:
            self._refresh_requested.set()
            return
        if event_type != "state_changed":
            return
        data = event.get("data")
        new_state = data.get("new_state") if isinstance(data, dict) else None
        if not isinstance(new_state, dict):
            return
        self._apply_state_event(context, new_state)

    def _apply_state_event(self, context: Any, state: dict[str, Any]) -> None:
        """Persist and publish one event-driven state generation atomically."""
        if not self._sync_lock.acquire(blocking=False):
            self._refresh_requested.set()
            return
        repository = None
        try:
            with self._snapshot_lock:
                current = self._capability_snapshot
            if current is None:
                self._refresh_requested.set()
                return
            candidate = update_capability_state(current, state)
            repository = self._repository_factory(context)
            repository.merge_state(state)
            repository.commit()
            with self._snapshot_lock:
                self._publish_capability_snapshot(candidate)
            self._state.last_event_at = datetime.now(UTC)
        except Exception as exc:
            self._state.event_error_count += 1
            self._log_error(f"Home Assistant state event update failed: {exc}")
            rollback = getattr(repository, "rollback", None)
            if callable(rollback):
                rollback()
            self._refresh_requested.set()
        finally:
            close = getattr(repository, "close", None)
            if callable(close):
                close()
            self._sync_lock.release()

    def _publish_capability_snapshot(self, snapshot: CapabilitySnapshot) -> None:
        """Publish one already-validated capability generation."""
        self._capability_snapshot = snapshot
        self._state.capability_generation = snapshot.generation
        self._state.capability_entity_count = len(snapshot.entities)
        self._state.capability_binding_count = sum(
            len(values) for values in snapshot.bindings.values()
        )
        self._state.capability_action_count = len(snapshot.actions)
        self._state.capability_unmapped_action_count = snapshot.unmapped_action_count

    def _close_resources(self) -> None:
        """Close resources owned by the service."""
        for resource in (self._repository, self._client):
            close = getattr(resource, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass
        event_thread = self._event_thread
        if (
            event_thread is not None
            and event_thread is not threading.current_thread()
            and event_thread.is_alive()
        ):
            event_thread.join(timeout=1.0)
        self._event_thread = None

    def _log_info(self, message: str) -> None:
        """Write an info message when a logger is available."""
        if self._logger is not None and hasattr(self._logger, "log_info"):
            self._logger.log_info(message)

    def _log_error(self, message: str) -> None:
        """Write an error message when a logger is available."""
        if self._logger is not None and hasattr(self._logger, "log_error"):
            self._logger.log_error(message)


def _service_response_entity_ids(response: Any) -> set[str]:
    """Return entity IDs from a Home Assistant service response."""
    if response is None:
        return set()
    if not isinstance(response, list):
        raise HomeAssistantControlError(
            "malformed_response",
            "Home Assistant service response was not a JSON array.",
        )
    entity_ids: set[str] = set()
    for item in response:
        if not isinstance(item, dict):
            raise HomeAssistantControlError(
                "malformed_response",
                "Home Assistant service response contained a malformed item.",
            )
        entity_id = str(item.get("entity_id") or "").strip().lower()
        if not entity_id:
            raise HomeAssistantControlError(
                "malformed_response",
                "Home Assistant service response did not include an entity_id.",
            )
        entity_ids.add(entity_id)
    return entity_ids
