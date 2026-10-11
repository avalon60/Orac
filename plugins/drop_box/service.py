"""Scheduled service for the generic drop-box ingestion plugin."""

# Author: Clive Bostock
# Date: 27-Jun-2026
# Description: Runs non-overlapping scans and creates durable drop-box jobs.

from __future__ import annotations

import threading
from typing import Any, Callable

from orac_core.knowledge import KnowledgeManagedFileCaptureService
from orac_core.knowledge.capture import KnowledgeCaptureError
from orac_core.knowledge.managed_store import ManagedStoreConfigurationError

from .models import TickStats
from .conversion import DropBoxConversionError
from .conversion import DropBoxDocumentConverter
from .conversion import FORMAT_RECIPES
from .repository import DropBoxRepository
from .scanner import DropBoxScanner

__author__ = "Clive Bostock"
__date__ = "27-Jun-2026"
__description__ = "Runs non-overlapping scans and creates durable drop-box jobs."


def _is_immutable_document_version_conflict(error: Exception) -> bool:
    """Return whether Core reported immutable document-version metadata drift."""
    return "ORA-20429" in str(error).upper()


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
        capture_service_factory: (
            Callable[[Any], KnowledgeManagedFileCaptureService] | None
        ) = None,
        converter: DropBoxDocumentConverter | None = None,
    ) -> None:
        """Initialise the service with injectable scanner and repository."""
        self._logger = logger
        self._config_mgr = config_mgr
        self._manifest = manifest
        self._scanner = scanner or DropBoxScanner()
        self._repository_factory = repository_factory or DropBoxRepository
        self._capture_service_factory = capture_service_factory or (
            lambda _context: KnowledgeManagedFileCaptureService(
                config_mgr=config_mgr,
                logger=logger,
            )
        )
        self._converter = converter or DropBoxDocumentConverter()
        self._tick_lock = threading.Lock()
        self.last_stats = TickStats()
        self.last_error: str | None = None

    def tick(self, context: Any) -> None:
        """Run one scheduled scan tick without overlapping in this process."""
        if not self._tick_lock.acquire(blocking=False):
            self.last_stats = TickStats(overlapping_tick_skipped=True)
            self._log_warning(
                "Drop-box scan tick skipped because a previous tick is still running."
            )
            return
        repository = None
        stats = TickStats()
        try:
            repository = self._repository_factory(context)
            configuration_errors = repository.load_configuration_errors()
            stats.configuration_errors = len(configuration_errors)
            for configuration_error in configuration_errors:
                self._log_warning(
                    "Drop-box location skipped because of configuration error: "
                    f"{configuration_error}."
                )
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
            self._handoff_jobs(context, repository, stats)
            repository.commit()
            self.last_error = None
            self.last_stats = stats
            self._log_info(
                "Drop-box scan tick complete: "
                f"locations={stats.locations_loaded} "
                f"configuration_errors={stats.configuration_errors} "
                f"stable={stats.stable_candidates} "
                f"enqueued={stats.enqueued} "
                f"handed_off={stats.handed_off} "
                f"handoff_failed={stats.handoff_failed} "
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

    def _handoff_jobs(
        self,
        context: Any,
        repository: DropBoxRepository,
        stats: TickStats,
    ) -> None:
        """Pass queued jobs to Core capture and persist handoff status."""
        capture_service = self._capture_service_factory(context)
        for job in repository.load_handoff_jobs():
            try:
                repository.update_status(
                    drop_job_id=job.drop_job_id,
                    status_code="processing",
                )
                recipe = FORMAT_RECIPES.get(job.source_path.suffix.lower())
                command_probe = None
                if recipe is not None and recipe.source_format_code == "pdf":
                    command_probe = context.resolve_command_dependency("pdftotext")
                elif recipe is not None and recipe.reader is not None:
                    command_probe = context.resolve_command_dependency("pandoc")
                normalised = self._converter.normalise(
                    job.source_path,
                    expected_sha256=job.source_hash,
                    expected_size=job.source_size_bytes,
                    command_probe=command_probe,
                    drop_location_id=job.drop_location_id,
                    drop_job_id=job.drop_job_id,
                )
                result = capture_service.capture_drop_box_file(
                    job.to_capture_request(normalised)
                )
                repository.record_core_acceptance(
                    drop_job_id=job.drop_job_id,
                    knowledge_ingestion_request_id=result.ingestion_request_id,
                )
                stats.handed_off += 1
            except DropBoxConversionError as exc:
                if exc.reason_code == "UNSUPPORTED_FORMAT":
                    status = "skipped_disallowed_type"
                elif exc.reason_code in {
                    "PANDOC_MISSING",
                    "PANDOC_INCOMPATIBLE",
                    "PANDOC_PROBE_FAILED",
                    "PANDOC_PROBE_TIMED_OUT",
                    "PDFTOTEXT_UNAVAILABLE",
                }:
                    status = "deferred_prerequisite"
                elif exc.retryable:
                    status = (
                        "failed"
                        if job.conversion_attempts >= 2
                        else "conversion_retry_wait"
                    )
                else:
                    status = "quarantined"
                repository.update_status(
                    drop_job_id=job.drop_job_id,
                    status_code=status,
                    error_message=f"{exc.reason_code}: {exc}",
                    reason_code=exc.reason_code,
                )
                stats.handoff_failed += 1
                self._log_warning(
                    f"Drop-box job {job.drop_job_id} conversion deferred or failed: {exc}"
                )
            except ManagedStoreConfigurationError:
                raise
            except KnowledgeCaptureError as exc:
                repository.update_status(
                    drop_job_id=job.drop_job_id,
                    status_code="failed",
                    error_message=f"Drop Box managed-file capture failed: {exc}",
                )
                stats.handoff_failed += 1
                self._log_warning(
                    f"Drop-box job {job.drop_job_id} failed managed-file capture: {exc}"
                )
            except Exception as exc:
                repository.update_status(
                    drop_job_id=job.drop_job_id,
                    status_code="queued",
                    error_message=None,
                    reason_code=None,
                )
                if _is_immutable_document_version_conflict(exc):
                    self._log_warning(
                        "Drop-box job "
                        f"{job.drop_job_id} remains queued after Core rejected reuse "
                        "of an existing content-hash version because immutable "
                        "metadata differs. The Oracle diagnostic lists conflicting "
                        f"field names only: {exc}"
                    )
                else:
                    self._log_warning(
                        "Drop-box job "
                        f"{job.drop_job_id} remains queued because Core handoff "
                        f"is temporarily unavailable: {exc}"
                    )

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
