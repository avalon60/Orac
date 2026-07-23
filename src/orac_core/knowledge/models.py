"""Data models for Core knowledge ingestion runtime workflows."""

# Author: Clive Bostock
# Date: 12-Jul-2026
# Description: Defines transfer objects shared by knowledge capture and worker code.

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from .scope import KnowledgeScope


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
    location_code: str | None = None
    legacy_source_key: str | None = None


@dataclass(frozen=True)
class ManagedCaptureResult:
    """Result of a managed-file capture and database registration attempt."""

    ingestion_request_id: int
    content_uri: str
    content_sha256: str
    status_code: str = "QUEUED"
    duplicate_payload: bool = False


@dataclass(frozen=True)
class KnowledgeSearchResult:
    """One scope-bound searchable knowledge chunk with safe provenance."""

    ingestion_request_id: int
    document_id: int
    document_version_id: int
    source_object_id: int
    source_reference: str
    parent_source_reference: str | None
    chunk_id: int
    chunk_no: int
    lexical_score: float
    semantic_score: float | None
    target_scope_type: str
    target_scope_key: str
    embedding_model_identifier: str
    embedding_dimensions: int
    chunk_text: str
    source_type: str = ""
    document_title: str | None = None
    original_filename: str | None = None
    content_uri: str | None = None
    span_start: int | None = None
    span_end: int | None = None
    chunk_content_sha256: str | None = None
    embedding_provider_code: str | None = None
    embedding_model_revision: str | None = None
    processing_profile_code: str | None = None

    @property
    def score(self) -> float:
        """Return the meaningful first-slice ranking score."""
        return self.lexical_score

    @property
    def scope(self) -> KnowledgeScope:
        """Return this result's canonical scope."""
        return KnowledgeScope(self.target_scope_type, self.target_scope_key)


@dataclass(frozen=True)
class KnowledgeRetrievalOutcome:
    """Structured result of one authorised scoped retrieval attempt."""

    status: str
    reason_codes: tuple[str, ...]
    scope: KnowledgeScope
    considered_count: int = 0
    threshold_count: int = 0
    malformed_count: int = 0
    embedding_model_identifier: str | None = None
    results: tuple[KnowledgeSearchResult, ...] = ()


@dataclass(frozen=True)
class KnowledgeGroundingPack:
    """Bounded untrusted local evidence ready for prompt assembly."""

    evidence_block: str
    outcome: KnowledgeRetrievalOutcome
    provenance: Mapping[str, Any]


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
