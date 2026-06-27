"""Scheduled service for the generic drop-box ingestion plugin."""
# Author: Clive Bostock
# Date: 27-Jun-2026
# Description: Runs non-overlapping scans and creates durable drop-box jobs.

from __future__ import annotations

import threading
from typing import Any, Callable

from .models import TickStats
from .repository import DropBoxRepository
from .scanner import DropBoxScanner

__author__ = "Clive Bostock"
__date__ = "27-Jun-2026"
__description__ = "Runs non-overlapping scans and creates durable drop-box jobs."


class DropBoxService:
    """Orac-managed scheduled service for drop-box scanning."""

    def __init__(
        self,
        logger: Any | None = None,
        config_mgr: Any | None = None,
        manifest: Any | None = None,
        *,
        scanner: DropBoxScanner | None = None,
        repository_factory: Callable[[Any], DropBoxRepository] | None = None,
    ) -> None:
        """Initialise the service with injectable scanner and repository."""
        self._logger = logger
        self._config_mgr = config_mgr
        self._manifest = manifest
        self._scanner = scanner or DropBoxScanner()
        self._repository_factory = repository_factory or DropBoxRepository
        self._tick_lock = threading.Lock()
        self.last_stats = TickStats()
        self.last_error: str | None = None

    def tick(self, context: Any) -> None:
        """Run one scheduled scan tick without overlapping in this process."""
        if not self._tick_lock.acquire(blocking=False):
            self.last_stats = TickStats(overlapping_tick_skipped=True)
            self._log_warning("Drop-box scan tick skipped because a previous tick is still running.")
            return
        repository = None
        stats = TickStats()
        try:
            repository = self._repository_factory(context)
            locations = repository.load_enabled_locations()
            stats.locations_loaded = len(locations)
            stats.scan = self._scanner.scan_locations(locations)
            stats.stable_candidates = len(stats.scan.stable_candidates)

            for candidate in stats.scan.stable_candidates:
                if repository.observation_exists(candidate):
                    stats.skipped_existing_observation += 1
                    continue
                hashed = self._scanner.hash_candidate(candidate)
                if hashed is None:
                    stats.deferred_changed_during_hash += 1
                    continue
                repository.enqueue_job(hashed)
                stats.enqueued += 1
            repository.commit()
            self.last_error = None
            self.last_stats = stats
            self._log_info(
                "Drop-box scan tick complete: "
                f"locations={stats.locations_loaded} "
                f"stable={stats.stable_candidates} "
                f"enqueued={stats.enqueued} "
                f"existing={stats.skipped_existing_observation} "
                f"changed={stats.deferred_changed_during_hash}."
            )
        except Exception as exc:
            self.last_error = str(exc)
            self.last_stats = stats
            if repository is not None:
                try:
                    repository.rollback()
                except Exception:
                    pass
            self._log_error(f"Drop-box scan tick failed: {exc}")
            raise
        finally:
            if repository is not None:
                try:
                    repository.close()
                except Exception:
                    pass
            self._tick_lock.release()

    def health(self, context: Any) -> bool:
        """Return whether the service has no currently recorded error."""
        return self.last_error is None

    def _log_info(self, message: str) -> None:
        if self._logger is not None and hasattr(self._logger, "log_info"):
            self._logger.log_info(message)

    def _log_warning(self, message: str) -> None:
        if self._logger is not None and hasattr(self._logger, "log_warning"):
            self._logger.log_warning(message)

    def _log_error(self, message: str) -> None:
        if self._logger is not None and hasattr(self._logger, "log_error"):
            self._logger.log_error(message)
