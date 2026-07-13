"""Data models for the drop-box ingestion plugin."""
# Author: Clive Bostock
# Date: 27-Jun-2026
# Description: Defines scanner, repository, and service transfer objects.

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from orac_core.knowledge import DropBoxCaptureRequest

__author__ = "Clive Bostock"
__date__ = "27-Jun-2026"
__description__ = "Defines scanner, repository, and service transfer objects."


DEFAULT_IGNORE_PATTERNS: tuple[str, ...] = (
    "*.tmp",
    "*.part",
    "*.partial",
    "*.crdownload",
    ".~*",
    "~$*",
    ".DS_Store",
)


@dataclass(frozen=True)
class DropLocation:
    """Runtime configuration for one database-defined drop location."""

    drop_location_id: int
    location_code: str
    display_name: str
    path: Path
    allowed_extensions: tuple[str, ...] = ()
    recursive: bool = False
    max_file_size_bytes: int | None = None
    stability_seconds: int = 10
    ignore_patterns: tuple[str, ...] = DEFAULT_IGNORE_PATTERNS

    @classmethod
    def from_row(cls, row: dict) -> "DropLocation":
        """Create a location model from an ORAC_DROPBOX runtime view row."""
        max_size_mb = _optional_float(row.get("MAX_FILE_SIZE_MB"))
        return cls(
            drop_location_id=int(row["DROP_LOCATION_ID"]),
            location_code=str(row["LOCATION_CODE"]),
            display_name=str(row["DISPLAY_NAME"]),
            path=Path(str(row["PATH"])),
            allowed_extensions=_split_csv(str(row.get("ALLOWED_EXTENSIONS") or "")),
            recursive=_yn(row.get("RECURSIVE_YN")),
            max_file_size_bytes=(
                int(max_size_mb * 1024 * 1024) if max_size_mb is not None else None
            ),
            stability_seconds=int(row.get("STABILITY_SECONDS") or 10),
            ignore_patterns=(
                _split_csv(str(row.get("IGNORE_PATTERNS") or ""))
                or DEFAULT_IGNORE_PATTERNS
            ),
        )


@dataclass(frozen=True)
class FileObservation:
    """A stable filesystem observation for one candidate file."""

    path: Path
    size_bytes: int
    mtime_ns: int
    source_mtime: datetime
    observed_at: datetime


@dataclass(frozen=True)
class CandidateFile:
    """A file that passed cheap filters and is waiting for stability."""

    location: DropLocation
    observation: FileObservation

    @property
    def source_path(self) -> str:
        """Return the source path stored in the job table."""
        return str(self.observation.path)

    @property
    def source_filename(self) -> str:
        """Return the source file name stored in the job table."""
        return self.observation.path.name


@dataclass(frozen=True)
class HashedCandidate:
    """A stable candidate with a verified SHA-256 source hash."""

    candidate: CandidateFile
    source_hash: str


@dataclass(frozen=True)
class DropBoxHandoffJob:
    """Queued Drop Box job ready for Core-managed file capture."""

    drop_job_id: int
    drop_location_id: int
    location_code: str
    location_root: Path
    source_path: Path
    source_filename: str
    source_hash: str
    source_size_bytes: int
    source_mtime: datetime | None
    effective_scope_type: str
    effective_scope_key: str
    effective_processing_profile: str | None = None
    effective_profile_instruction: str | None = None
    effective_instruction: str | None = None

    @classmethod
    def from_row(cls, row: dict) -> "DropBoxHandoffJob":
        """Create a handoff job from ``drop_job_handoff_v``."""
        return cls(
            drop_job_id=int(row["DROP_JOB_ID"]),
            drop_location_id=int(row["DROP_LOCATION_ID"]),
            location_code=str(row["LOCATION_CODE"]),
            location_root=Path(str(row["LOCATION_ROOT"])),
            source_path=Path(str(row["SOURCE_PATH"])),
            source_filename=str(row["SOURCE_FILENAME"]),
            source_hash=str(row["SOURCE_HASH"]),
            source_size_bytes=int(row["SOURCE_SIZE_BYTES"]),
            source_mtime=row.get("SOURCE_MTIME"),
            effective_scope_type=str(row["EFFECTIVE_SCOPE_TYPE"]),
            effective_scope_key=str(row["EFFECTIVE_SCOPE_KEY"]),
            effective_processing_profile=row.get("EFFECTIVE_PROCESSING_PROFILE"),
            effective_profile_instruction=row.get("EFFECTIVE_PROFILE_INSTRUCTION"),
            effective_instruction=row.get("EFFECTIVE_INSTRUCTION"),
        )

    def to_capture_request(self) -> DropBoxCaptureRequest:
        """Return the Core capture request for this Drop Box job."""
        instruction = self.effective_instruction or self.effective_profile_instruction
        return DropBoxCaptureRequest(
            drop_job_id=self.drop_job_id,
            drop_location_id=self.drop_location_id,
            location_root=self.location_root,
            source_path=self.source_path,
            source_filename=self.source_filename,
            source_sha256=self.source_hash,
            source_size_bytes=self.source_size_bytes,
            source_mtime=self.source_mtime,
            target_scope_type=self.effective_scope_type,
            target_scope_key=self.effective_scope_key,
            processing_profile=self.effective_processing_profile,
            processing_instruction=instruction,
            source_key=f"{self.location_code}:{self.source_path}",
        )


@dataclass
class ScanResult:
    """Result of scanning one or more drop locations."""

    stable_candidates: list[CandidateFile] = field(default_factory=list)
    observed_candidates: int = 0
    missing_paths: int = 0
    skipped_disallowed_type: int = 0
    skipped_too_large: int = 0
    skipped_ignored: int = 0
    skipped_symlink: int = 0
    deferred_unstable: int = 0


@dataclass
class TickStats:
    """Operational counters for one service tick."""

    configuration_errors: int = 0
    locations_loaded: int = 0
    stable_candidates: int = 0
    enqueued: int = 0
    handed_off: int = 0
    handoff_failed: int = 0
    skipped_existing_observation: int = 0
    deferred_changed_during_hash: int = 0
    overlapping_tick_skipped: bool = False
    scan: ScanResult = field(default_factory=ScanResult)


def _split_csv(value: str) -> tuple[str, ...]:
    """Split a comma-separated config value into stripped non-empty entries."""
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _yn(value: object) -> bool:
    """Return whether a database Y/N value is enabled."""
    return str(value or "N").strip().upper() == "Y"


def _optional_float(value: object) -> float | None:
    """Return a numeric value or ``None`` for blank database values."""
    if value is None or str(value).strip() == "":
        return None
    return float(value)


def datetime_from_mtime_ns(mtime_ns: int) -> datetime:
    """Convert nanosecond filesystem mtime to a naive UTC database timestamp."""
    return datetime.fromtimestamp(mtime_ns / 1_000_000_000, tz=UTC).replace(
        tzinfo=None
    )
