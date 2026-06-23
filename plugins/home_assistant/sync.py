"""Home Assistant synchronisation coordinator for the managed plugin service."""
# Author: Clive Bostock
# Date: 04-Jun-2026
# Description: Coordinates REST fetches and repository writes for HA startup sync.

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

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

    def __init__(self, *, client: Any, repository: Any) -> None:
        """Initialise the coordinator.

        Args:
            client: Home Assistant REST client.
            repository: Home Assistant repository using ORAC_PLUGIN.
        """
        self._client = client
        self._repository = repository

    def run_initial_sync(self) -> tuple[SyncResult, SyncResult]:
        """Run structural sync followed by state sync."""
        structural = self.run_structural_sync()
        state = self.run_state_sync()
        return structural, state

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

            for area in areas:
                self._repository.merge_area(area)
            for device in devices:
                self._repository.merge_device(device)
            for entity in entities:
                self._repository.merge_entity(entity)

            rows_processed = len(areas) + len(devices) + len(entities)
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
                self._fail_sync_run(sync_run_id, exc)
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
                self._fail_sync_run(sync_run_id, exc)
            else:
                self._repository.rollback()
            raise

    def _fail_sync_run(self, sync_run_id: str, exc: BaseException) -> None:
        """Best-effort failure recording for a started sync run."""
        try:
            self._repository.fail_sync_run(sync_run_id, error_message=str(exc))
            self._repository.commit()
        except Exception:
            self._repository.rollback()


def _now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)
