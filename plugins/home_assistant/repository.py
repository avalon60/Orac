"""Database repository for Home Assistant plugin synchronisation."""
# Author: Clive Bostock
# Date: 04-Jun-2026
# Description: Calls Home Assistant plugin database package APIs through ORAC_PLUGIN.

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
import json
from typing import Any, Callable
from uuid import uuid4

from model.plugin_database_session import ORAC_PLUGIN_DATABASE_USER

from .control import AreaDeviceList
from .control import list_areas
from .control import AreaListRequest
from .control import AreaInventoryRequest
from .control import ControlRequest
from .control import ResolvedControl
from .control import list_area_devices
from .control import resolve_control_target
from .sensor_query import SensorQueryRequest
from .sensor_query import SensorQueryResult
from .sensor_query import execute_sensor_query
from .sensor_query import resolve_sensor_query_entity_ids

__author__ = "Clive Bostock"
__date__ = "04-Jun-2026"
__description__ = "Calls Home Assistant plugin database package APIs through ORAC_PLUGIN."


class HomeAssistantRepository:
    """Persists Home Assistant sync data through granted package APIs only."""

    _PACKAGE = "orac_ha.ha_sync_api"

    def __init__(
        self,
        context: Any,
        *,
        run_id_factory: Callable[[], str] | None = None,
    ) -> None:
        """Initialise the repository.

        Args:
            context: Orac plugin service context exposing ``plugin_db_session``.
            run_id_factory: Optional deterministic run id factory for tests.
        """
        self._db_session = context.plugin_db_session()
        if getattr(self._db_session, "connected_username", None) != ORAC_PLUGIN_DATABASE_USER:
            raise RuntimeError("Home Assistant repository requires ORAC_PLUGIN database identity.")
        self._run_id_factory = run_id_factory or (lambda: str(uuid4()))

    def begin_sync_run(self, sync_type: str) -> str:
        """Reset shadow tables, record sync start, and return the run id."""
        sync_run_id = self._run_id_factory()
        self._db_session.call_procedure(
            f"{self._PACKAGE}.begin_sync_run",
            [sync_run_id, sync_type],
        )
        return sync_run_id

    def complete_sync_run(
        self,
        sync_run_id: str,
        *,
        rows_processed: int,
        message: str | None = None,
    ) -> None:
        """Record successful completion of a sync run."""
        self._db_session.call_procedure(
            f"{self._PACKAGE}.complete_sync_run",
            [sync_run_id, rows_processed, message],
        )

    def fail_sync_run(
        self,
        sync_run_id: str,
        *,
        error_message: str,
    ) -> None:
        """Record a failed sync run without exposing secret values."""
        self._db_session.call_procedure(
            f"{self._PACKAGE}.fail_sync_run",
            [sync_run_id, _safe_error_message(error_message)],
        )

    def merge_area(self, area: Mapping[str, Any]) -> None:
        """Merge one Home Assistant area payload."""
        self._call_json_payload("merge_area", area)

    def merge_device(self, device: Mapping[str, Any]) -> None:
        """Merge one Home Assistant device payload."""
        self._call_json_payload("merge_device", device)

    def merge_entity(self, entity: Mapping[str, Any]) -> None:
        """Merge one Home Assistant entity payload."""
        self._call_json_payload("merge_entity", entity)

    def merge_state(self, state: Mapping[str, Any]) -> None:
        """Merge one Home Assistant current-state payload."""
        self._call_json_payload("merge_state", state)

    def resolve_control(self, request: ControlRequest) -> ResolvedControl:
        """Resolve a device-control target through the granted read-only view."""
        return resolve_control_target(request, self._control_resolution_rows())

    def list_area(self, request: AreaListRequest) -> AreaDeviceList:
        """List devices for an exact area through the granted read-only view."""
        return list_area_devices(request, self._control_resolution_rows())

    def list_areas(self, request: AreaInventoryRequest) -> tuple[str, ...]:
        """List the known Home Assistant areas from the granted view."""
        return list_areas(self._control_resolution_rows())

    def query_sensors(
        self,
        request: SensorQueryRequest,
        *,
        stale_after_hours: float,
        live_states: list[dict[str, Any]],
    ) -> SensorQueryResult:
        """Resolve a sensor query using shadow metadata and live HA states."""
        return execute_sensor_query(
            request,
            _overlay_live_states(self._control_resolution_rows(), live_states),
            stale_after=timedelta(hours=stale_after_hours),
        )

    def resolve_sensor_entities(self, request: SensorQueryRequest) -> tuple[str, ...]:
        """Resolve sensor entities using only shadow structural metadata."""
        return resolve_sensor_query_entity_ids(
            request,
            self._control_resolution_rows(),
        )

    def query_cached_sensors(
        self,
        request: SensorQueryRequest,
        *,
        stale_after_hours: float,
    ) -> SensorQueryResult:
        """Render explicitly labelled cached sensor data after a live failure."""
        result = execute_sensor_query(
            request,
            self._control_resolution_rows(),
            stale_after=timedelta(hours=stale_after_hours),
        )
        return SensorQueryResult(
            content=(
                "I cannot get a live reading from Home Assistant right now. "
                f"Cached Home Assistant data from Orac: {result.content}"
            ),
            entity_ids=result.entity_ids,
            areas=result.areas,
            status="cached",
        )

    def _control_resolution_rows(self) -> list[dict[str, Any]]:
        """Return rows from the Home Assistant control-resolution view."""
        return self._db_session.fetch_dicts(
            """
            select alias_name,
                   entity_id,
                   domain,
                   object_id,
                   entity_name,
                   original_name,
                   disabled_by,
                   friendly_name,
                   device_class,
                   unit_of_measurement,
                   device_name,
                   area_name,
                   area_aliases,
                   current_state,
                   last_changed,
                   last_updated
              from orac_ha.ha_control_resolution_v
            """
        )

    def commit(self) -> None:
        """Commit the current repository transaction."""
        self._db_session.commit()

    def rollback(self) -> None:
        """Roll back the current repository transaction."""
        self._db_session.rollback()

    def close(self) -> None:
        """Close the managed plugin database session."""
        self._db_session.close()

    def _call_json_payload(
        self,
        procedure_name: str,
        payload: Mapping[str, Any],
    ) -> None:
        """Call one package procedure with a canonical JSON payload."""
        self._db_session.call_procedure(
            f"{self._PACKAGE}.{procedure_name}",
            [_json_payload(payload)],
        )


def _json_payload(payload: Mapping[str, Any]) -> str:
    """Serialise a Home Assistant API payload for package consumption."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _safe_error_message(error_message: str) -> str:
    """Return a bounded, single-line error message for database logging."""
    return str(error_message or "").replace("\r", " ").replace("\n", " ")[:4000]


def _overlay_live_states(
    metadata_rows: list[dict[str, Any]],
    live_states: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Overlay current HA state onto shadow rows without persisting it."""
    states_by_entity = {
        str(state.get("entity_id") or "").strip().lower(): state
        for state in live_states
        if str(state.get("entity_id") or "").strip()
    }
    rows: list[dict[str, Any]] = []
    for source in metadata_rows:
        row = {str(key).lower(): value for key, value in source.items()}
        entity_id = str(row.get("entity_id") or "").strip().lower()
        state = states_by_entity.get(entity_id)
        if state is None:
            row["current_state"] = "unavailable"
            row["last_changed"] = None
            row["last_updated"] = None
            rows.append(row)
            continue
        attributes = state.get("attributes")
        if not isinstance(attributes, Mapping):
            attributes = {}
        row["current_state"] = state.get("state")
        row["last_changed"] = state.get("last_changed")
        row["last_updated"] = state.get("last_updated")
        for key in ("friendly_name", "device_class", "unit_of_measurement"):
            if attributes.get(key) is not None:
                row[key] = attributes[key]
        rows.append(row)
    return rows
