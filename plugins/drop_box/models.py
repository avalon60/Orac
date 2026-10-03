"""Data models for the drop-box ingestion plugin."""

# Author: Clive Bostock
# Date: 27-Jun-2026
# Description: Defines scanner, repository, and service transfer objects.

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import os
import json
from pathlib import Path

from lib.fsutils import project_home
from orac_core.knowledge import DropBoxCaptureRequest

from .conversion import NormalisedDocument

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

_ORAC_HOME_TOKEN = "${ORAC_HOME}"


def _optional_oracle_text(value: object, *, field_name: str) -> str | None:
    """Return text from a plain string or Oracle LOB-backed field.

    Args:
        value: Database value to normalise.
        field_name: Human-readable field name for validation errors.

    Returns:
        The text value, or ``None`` when the database value is null.

    Raises:
        TypeError: If the database value or LOB payload is not text.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    reader = getattr(value, "read", None)
    if not callable(reader):
        raise TypeError(f"Drop Box {field_name} must be text or an Oracle LOB.")
    payload = reader()
    if not isinstance(payload, str):
        raise TypeError(f"Drop Box {field_name} Oracle LOB must contain text.")
    return payload


def _resolved_location_path(raw_value: object) -> Path:
    """Resolve one validated database-defined Drop Box source path.

    Args:
        raw_value (object): Database path value.

    Returns:
        Path: Absolute lexical source path for the scanner.

    Raises:
        ValueError: If the value is empty, relative, contains traversal, or
            uses an unsupported environment token.
    """
    raw_path = str(raw_value or "").strip()
    if not raw_path:
        raise ValueError("Drop Box source path is required.")
    if any(ord(character) < 32 or ord(character) == 127 for character in raw_path):
        raise ValueError("Drop Box source path contains control characters.")

    token_prefix = f"{_ORAC_HOME_TOKEN}/"
    if raw_path.startswith(token_prefix):
        relative_path = Path(raw_path[len(token_prefix) :])
        if (
            not relative_path.parts
            or relative_path.is_absolute()
            or ".." in relative_path.parts
        ):
            raise ValueError("Drop Box ORAC_HOME path is unsafe.")
        configured_home = os.environ.get("ORAC_HOME")
        orac_home = (
            Path(configured_home).expanduser()
            if configured_home is not None
            else project_home()
        )
        if not orac_home.is_absolute():
            raise ValueError("ORAC_HOME must resolve to an absolute path.")
        return orac_home / relative_path

    if "${" in raw_path:
        raise ValueError("Drop Box source path uses an unsupported environment token.")

    location_path = Path(raw_path).expanduser()
    if not location_path.is_absolute():
        raise ValueError("Drop Box source path must be absolute.")
    if ".." in location_path.parts:
        raise ValueError("Drop Box source path must not contain traversal.")
    return location_path


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
            path=_resolved_location_path(row["PATH"]),
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
    target_knowledge_scope_id: int
    producer_knowledge_scope_id: int
    effective_processing_profile: str | None = None
    effective_profile_instruction: str | None = None
    effective_instruction: str | None = None
    effective_classification_tags_json: str | None = None
    conversion_attempts: int = 0

    @classmethod
    def from_row(cls, row: dict) -> "DropBoxHandoffJob":
        """Create a handoff job from ``drop_job_handoff_v``."""
        return cls(
            drop_job_id=int(row["DROP_JOB_ID"]),
            drop_location_id=int(row["DROP_LOCATION_ID"]),
            location_code=str(row["LOCATION_CODE"]),
            location_root=_resolved_location_path(row["LOCATION_ROOT"]),
            source_path=Path(str(row["SOURCE_PATH"])),
            source_filename=str(row["SOURCE_FILENAME"]),
            source_hash=str(row["SOURCE_HASH"]),
            source_size_bytes=int(row["SOURCE_SIZE_BYTES"]),
            source_mtime=row.get("SOURCE_MTIME"),
            effective_scope_type=str(row["EFFECTIVE_SCOPE_TYPE"]),
            effective_scope_key=str(row["EFFECTIVE_SCOPE_KEY"]),
            target_knowledge_scope_id=int(row["TARGET_KNOWLEDGE_SCOPE_ID"]),
            producer_knowledge_scope_id=int(row["PRODUCER_KNOWLEDGE_SCOPE_ID"]),
            effective_processing_profile=row.get("EFFECTIVE_PROCESSING_PROFILE"),
            effective_profile_instruction=_optional_oracle_text(
                row.get("EFFECTIVE_PROFILE_INSTRUCTION"),
                field_name="profile instruction",
            ),
            effective_instruction=_optional_oracle_text(
                row.get("EFFECTIVE_INSTRUCTION"),
                field_name="location instruction",
            ),
            effective_classification_tags_json=_optional_oracle_text(
                row.get("EFFECTIVE_CLASSIFICATION_TAGS_JSON"),
                field_name="classification JSON",
            ),
            conversion_attempts=int(row.get("CONVERSION_ATTEMPTS") or 0),
        )

    def to_capture_request(
        self,
        normalised: NormalisedDocument | None = None,
    ) -> DropBoxCaptureRequest:
        """Return the Core capture request for this Drop Box job."""
        instruction = self.effective_instruction or self.effective_profile_instruction
        source_key = self._source_key()
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
            target_knowledge_scope_id=self.target_knowledge_scope_id,
            producer_knowledge_scope_id=self.producer_knowledge_scope_id,
            processing_profile=self.effective_processing_profile,
            processing_instruction=instruction,
            source_key=source_key,
            location_code=self.location_code,
            source_format_code=(
                normalised.source_format_code if normalised is not None else None
            ),
            source_mime_type=(
                normalised.source_mime_type if normalised is not None else None
            ),
            normalised_markdown=(
                normalised.markdown if normalised is not None else None
            ),
            normalised_text_sha256=(
                normalised.text_sha256 if normalised is not None else None
            ),
            normalised_byte_size=(
                normalised.byte_size if normalised is not None else None
            ),
            output_mime_type=(
                normalised.output_mime_type if normalised is not None else None
            ),
            extractor_code=(
                normalised.extractor_code if normalised is not None else None
            ),
            extractor_version=(
                normalised.extractor_version if normalised is not None else None
            ),
            extraction_metadata_json=(
                json.dumps(
                    {
                        **json.loads(normalised.metadata_json),
                        "producer_knowledge_scope_id": self.producer_knowledge_scope_id,
                    }
                )
                if normalised is not None
                else None
            ),
            classification_tags_json=self.effective_classification_tags_json,
        )

    def _source_key(self) -> str:
        """Return the stable Drop Box source identity for this job."""
        try:
            relative = self.source_path.resolve(strict=False).relative_to(
                self.location_root.resolve(strict=False)
            )
        except ValueError:
            relative = Path(self.source_filename)
        return f"{self.location_code}:{relative.as_posix()}"


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
    return datetime.fromtimestamp(mtime_ns / 1_000_000_000, tz=UTC).replace(tzinfo=None)
