"""Home Assistant synchronisation coordinator for the managed plugin service."""
# Author: Clive Bostock
# Date: 04-Jun-2026
# Description: Coordinates REST fetches and repository writes for HA startup sync.

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .capabilities import CapabilitySnapshot
from .capabilities import derive_capability_snapshot

__author__ = "Clive Bostock"
__date__ = "04-Jun-2026"
__description__ = "Coordinates REST fetches and repository writes for HA startup sync."


@dataclass(frozen=True)
class SyncResult:
    """Summary of one Home Assistant synchronisation run."""

    sync_type: str
    sync_run_id: str
    rows_processed: int
    started_on: datetime
    completed_on: datetime


class HomeAssistantSyncCoordinator:
    """Runs Home Assistant structural and state syncs through repository APIs."""

    def __init__(
        self,
        *,
        client: Any,
        repository: Any,
        target_service_discovery_limit: int = 250,
    ) -> None:
        """Initialise the coordinator.

        Args:
            client: Home Assistant REST client.
            repository: Home Assistant repository using ORAC_PLUGIN.
            target_service_discovery_limit: Maximum per-entity action probes.
        """
        self._client = client
        self._repository = repository
        self._target_service_discovery_limit = max(
            0,
            int(target_service_discovery_limit),
        )
        self.capability_snapshot: CapabilitySnapshot | None = None
        self._entities: list[dict[str, Any]] = []
        self._states: list[dict[str, Any]] = []
        self._services: dict[str, Any] = {}

    def run_initial_sync(self) -> tuple[SyncResult, SyncResult]:
        """Build and publish one atomic structural, state, and capability snapshot."""
        structural_run_id: str | None = None
        state_run_id: str | None = None
        active_sync_type = "structural"
        structural_started = _now()
        state_started = structural_started
        try:
            structural_run_id = self._repository.begin_sync_run("structural")
            areas = self._client.fetch_areas()
            devices = self._client.fetch_devices()
            entities = self._client.fetch_entities()
            fetch_services = getattr(self._client, "fetch_services", None)
            services = fetch_services() if callable(fetch_services) else {}
            for area in areas:
                self._repository.merge_area(area)
            for device in devices:
                self._repository.merge_device(device)
            for entity in entities:
                self._repository.merge_entity(entity)
            structural_rows = len(areas) + len(devices) + len(entities)
            self._repository.complete_sync_run(
                structural_run_id,
                rows_processed=structural_rows,
            )

            active_sync_type = "state"
            state_started = _now()
            state_run_id = self._repository.begin_sync_run("state")
            states = self._client.fetch_states()
            for state in states:
                self._repository.merge_state(state)
            state_rows = len(states)
            self._repository.complete_sync_run(
                state_run_id,
                rows_processed=state_rows,
            )

            candidate_snapshot = derive_capability_snapshot(
                entities,
                states,
                services,
                services_by_entity=self._services_by_entity_for(entities),
                devices=devices,
            )
            self._repository.commit()
            self._entities = list(entities)
            self._states = list(states)
            self._services = dict(services)
            self.capability_snapshot = candidate_snapshot
            completed_on = _now()
            return (
                SyncResult(
                    "structural",
                    structural_run_id,
                    structural_rows,
                    structural_started,
                    completed_on,
                ),
                SyncResult(
                    "state",
                    state_run_id,
                    state_rows,
                    state_started,
                    completed_on,
                ),
            )
        except Exception as exc:
            failed_run_id = state_run_id or structural_run_id
            if failed_run_id:
                self._fail_sync_run(failed_run_id, active_sync_type, exc)
            else:
                self._repository.rollback()
            raise

    def run_structural_sync(self) -> SyncResult:
        """Fetch and persist Home Assistant structural metadata."""
        sync_run_id: str | None = None
        started_on = _now()
        rows_processed = 0
        try:
            sync_run_id = self._repository.begin_sync_run("structural")
            areas = self._client.fetch_areas()
            devices = self._client.fetch_devices()
            entities = self._client.fetch_entities()
            fetch_services = getattr(self._client, "fetch_services", None)
            services = fetch_services() if callable(fetch_services) else {}

            for area in areas:
                self._repository.merge_area(area)
            for device in devices:
                self._repository.merge_device(device)
            for entity in entities:
                self._repository.merge_entity(entity)

            rows_processed = len(areas) + len(devices) + len(entities)
            self._entities = list(entities)
            self._services = dict(services)
            self._repository.complete_sync_run(
                sync_run_id,
                rows_processed=rows_processed,
            )
            self._repository.commit()
            return SyncResult(
                sync_type="structural",
                sync_run_id=sync_run_id,
                rows_processed=rows_processed,
                started_on=started_on,
                completed_on=_now(),
            )
        except Exception as exc:
            if sync_run_id:
                self._fail_sync_run(sync_run_id, "structural", exc)
            else:
                self._repository.rollback()
            raise

    def run_state_sync(self) -> SyncResult:
        """Fetch and persist current Home Assistant state."""
        sync_run_id: str | None = None
        started_on = _now()
        rows_processed = 0
        try:
            sync_run_id = self._repository.begin_sync_run("state")
            states = self._client.fetch_states()
            for state in states:
                self._repository.merge_state(state)

            rows_processed = len(states)
            self._states = list(states)
            self._repository.complete_sync_run(
                sync_run_id,
                rows_processed=rows_processed,
            )
            self._repository.commit()
            return SyncResult(
                sync_type="state",
                sync_run_id=sync_run_id,
                rows_processed=rows_processed,
                started_on=started_on,
                completed_on=_now(),
            )
        except Exception as exc:
            if sync_run_id:
                self._fail_sync_run(sync_run_id, "state", exc)
            else:
                self._repository.rollback()
            raise

    def _fail_sync_run(
        self,
        sync_run_id: str,
        sync_type: str,
        exc: BaseException,
    ) -> None:
        """Roll back replacement work, then record failure independently."""
        self._repository.rollback()
        try:
            self._repository.record_failed_sync_run(
                sync_run_id,
                sync_type=sync_type,
                error_message=str(exc),
            )
        except Exception:
            self._repository.rollback()

    def _services_by_entity(self) -> dict[str, tuple[str, ...]]:
        """Feature-probe Home Assistant's target-specific action discovery."""
        return self._services_by_entity_for(self._entities)

    def _services_by_entity_for(
        self,
        entities: list[dict[str, Any]],
    ) -> dict[str, tuple[str, ...]]:
        """Return target-specific actions for a candidate entity generation."""
        fetch = getattr(self._client, "fetch_services_for_entity", None)
        if not callable(fetch):
            return {}
        if len(entities) > self._target_service_discovery_limit:
            return {}
        result: dict[str, tuple[str, ...]] = {}
        for entity in entities:
            entity_id = str(entity.get("entity_id") or "").strip().lower()
            if not entity_id:
                continue
            try:
                result[entity_id] = tuple(fetch(entity_id))
            except Exception:
                # The command is not available on every supported HA release.
                return {}
        return result


def _now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)
