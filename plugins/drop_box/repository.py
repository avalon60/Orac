"""Database repository for the drop-box ingestion plugin."""
# Author: Clive Bostock
# Date: 27-Jun-2026
# Description: Calls ORAC_DROPBOX package APIs through the ORAC_PLUGIN bridge.

from __future__ import annotations

from typing import Any

from model.plugin_database_session import ORAC_PLUGIN_DATABASE_USER

from .models import CandidateFile, DropBoxHandoffJob, DropLocation, HashedCandidate

__author__ = "Clive Bostock"
__date__ = "27-Jun-2026"
__description__ = "Calls ORAC_DROPBOX package APIs through the ORAC_PLUGIN bridge."


class DropBoxRepository:
    """Loads drop locations and enqueues jobs through approved database APIs."""

    _PACKAGE = "orac_dropbox.drop_box_api"

    def __init__(self, context: Any) -> None:
        """Initialise the repository from a plugin service context."""
        self._db_session = context.plugin_db_session()
        if getattr(self._db_session, "connected_username", None) != ORAC_PLUGIN_DATABASE_USER:
            raise RuntimeError("Drop-box repository requires ORAC_PLUGIN database identity.")

    def load_enabled_locations(self) -> list[DropLocation]:
        """Return enabled drop locations visible to the scanner service."""
        rows = self._db_session.fetch_dicts(
            """
            select drop_location_id,
                   location_code,
                   display_name,
                   path,
                   allowed_extensions,
                   recursive_yn,
                   max_file_size_mb,
                   stability_seconds,
                   ignore_patterns
              from orac_dropbox.drop_location_runtime_v
             order by location_code
            """
        )
        return [DropLocation.from_row(row) for row in rows]

    def load_configuration_errors(self) -> list[str]:
        """Return enabled drop locations omitted from scanning for config errors."""
        rows = self._db_session.fetch_dicts(
            """
            select location_code,
                   processing_profile,
                   error_message
              from orac_dropbox.drop_location_config_error_v
             order by location_code
            """
        )
        return [
            (
                f"{row['LOCATION_CODE']}: {row['ERROR_MESSAGE']} "
                f"processing_profile={row.get('PROCESSING_PROFILE') or '<null>'}"
            )
            for row in rows
        ]

    def observation_exists(self, candidate: CandidateFile) -> bool:
        """Return whether this unchanged file observation already has a job."""
        result = self._db_session.call_function(
            f"{self._PACKAGE}.observation_exists",
            return_type=int,
            parameters=[
                candidate.location.drop_location_id,
                candidate.source_path,
                candidate.observation.size_bytes,
                candidate.observation.source_mtime,
            ],
        )
        return int(result or 0) == 1

    def enqueue_job(self, hashed: HashedCandidate) -> None:
        """Create a durable queued job for a hashed stable file."""
        candidate = hashed.candidate
        self._db_session.call_procedure(
            f"{self._PACKAGE}.enqueue_job",
            [
                candidate.location.drop_location_id,
                candidate.source_path,
                candidate.source_filename,
                candidate.observation.size_bytes,
                candidate.observation.source_mtime,
                candidate.observation.observed_at,
                hashed.source_hash,
            ],
        )

    def load_handoff_jobs(self) -> list[DropBoxHandoffJob]:
        """Return queued jobs requiring Core managed-file capture."""
        rows = self._db_session.fetch_dicts(
            """
            select drop_job_id,
                   drop_location_id,
                   location_code,
                   location_root,
                   source_path,
                   source_filename,
                   source_hash,
                   source_size_bytes,
                   source_mtime,
                   effective_scope_type,
                   effective_scope_key,
                   effective_processing_profile,
                   effective_profile_instruction,
                   effective_instruction,
                   knowledge_ingestion_request_id
              from orac_dropbox.drop_job_handoff_v
             order by stable_on nulls last, drop_job_id
            """
        )
        return [DropBoxHandoffJob.from_row(row) for row in rows]

    def core_handoff_available(self) -> bool:
        """Return whether the Core knowledge handoff package is visible."""
        rows = self._db_session.fetch_dicts(
            """
            select count(*) as available_count
              from all_objects
             where owner = 'ORAC_CODE'
               and object_name = 'KNOWLEDGE_INGESTION_API'
               and object_type = 'PACKAGE'
               and status = 'VALID'
            """
        )
        if not rows:
            return False
        return int(rows[0].get("AVAILABLE_COUNT") or 0) > 0

    def update_status(
        self,
        *,
        drop_job_id: int,
        status_code: str,
        error_message: str | None = None,
        document_id: int | None = None,
    ) -> None:
        """Persist a Drop Box job status transition through the package API."""
        self._db_session.call_procedure(
            f"{self._PACKAGE}.update_status",
            [
                int(drop_job_id),
                status_code,
                error_message,
                document_id,
            ],
        )

    def record_core_acceptance(
        self,
        *,
        drop_job_id: int,
        knowledge_ingestion_request_id: int,
    ) -> None:
        """Persist the durable Core request accepted for a Drop Box job."""
        self._db_session.call_procedure(
            f"{self._PACKAGE}.record_core_acceptance",
            [
                int(drop_job_id),
                int(knowledge_ingestion_request_id),
            ],
        )

    def repair_missing_core_failures(self) -> int:
        """Requeue jobs failed only by the previously unavailable Core API."""
        result = self._db_session.call_function(
            f"{self._PACKAGE}.repair_missing_core_failures",
            return_type=int,
            parameters=[],
        )
        return int(result or 0)

    def commit(self) -> None:
        """Commit current plugin database work."""
        self._db_session.commit()

    def rollback(self) -> None:
        """Roll back current plugin database work."""
        self._db_session.rollback()

    def close(self) -> None:
        """Close the managed plugin database session."""
        self._db_session.close()
