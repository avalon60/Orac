"""Data models for Core knowledge ingestion runtime workflows."""
# Author: Clive Bostock
# Date: 12-Jul-2026
# Description: Defines transfer objects shared by knowledge capture and worker code.

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class DropBoxCaptureRequest:
    """Trusted handoff facts for one Drop Box source file."""

    drop_job_id: int
    drop_location_id: int
    location_root: Path
    source_path: Path
    source_filename: str
    source_sha256: str
    source_size_bytes: int
    source_mtime: datetime | None
    target_scope_type: str
    target_scope_key: str
    processing_profile: str | None = None
    processing_instruction: str | None = None
    source_key: str | None = None


@dataclass(frozen=True)
class ManagedCaptureResult:
    """Result of a managed-file capture and database registration attempt."""

    ingestion_request_id: int
    content_uri: str
    content_sha256: str
    status_code: str = "QUEUED"
    duplicate_payload: bool = False


@dataclass(frozen=True)
class ClaimedKnowledgeRequest:
    """One queue request claimed by the Core knowledge worker."""

    ingestion_request_id: int
    lease_owner: str
    lease_token: str
    source_object_id: int
    content_uri: str
    mime_type: str
    original_filename: str | None
    source_modified_on: datetime | None
