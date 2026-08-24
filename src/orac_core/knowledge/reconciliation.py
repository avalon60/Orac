"""Reconcile Oracle knowledge metadata with Core-managed physical storage."""

# Author: Clive Bostock
# Date: 14-Aug-2026
# Description: Provides bounded read-only knowledge inventory and reconciliation.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import json
import math
from pathlib import Path
import time
from typing import Any
import uuid

from .managed_store import KnowledgeManagedStore
from .managed_store import ManagedObjectIdentity
from .managed_store import ManagedStoreInventory
from .managed_store import ManagedStoreInventoryEntry
from .managed_store import ManagedStoreInventoryLimits
from .repository import default_orac_session

REPORT_SCHEMA_VERSION = 1
DEFAULT_MAX_DATABASE_ROWS = 250_000
DEFAULT_MAX_FILESYSTEM_ENTRIES = 250_000
DEFAULT_MAX_HASHED_BYTES = 10_737_418_240
DEFAULT_MAX_TEMPORARY_FILES_HASHED = 1_000
DEFAULT_MAX_ELAPSED_SECONDS = 300
DEFAULT_MAX_REPORT_ITEMS_PER_REASON = 20
DEFAULT_MAX_REPORT_BYTES = 1_048_576
DEFAULT_STALE_TEMPORARY_AGE_SECONDS = 86_400
DEFAULT_UNREGISTERED_OBJECT_GRACE_SECONDS = 86_400
MAX_DATABASE_ROWS = 1_000_000
MAX_FILESYSTEM_ENTRIES = 1_000_000
MAX_HASHED_BYTES = 107_374_182_400
MAX_TEMPORARY_FILES_HASHED = 10_000
MAX_ELAPSED_SECONDS = 1_800
MAX_REPORT_ITEMS_PER_REASON = 100
MAX_REPORT_BYTES = 4_194_304
MAX_TRAVERSAL_DEPTH = 4
MAX_CONCURRENCY = 1
DATABASE_PAGE_SIZE = 500


class ReconciliationStatus(StrEnum):
    """Overall outcome of a bounded reconciliation scan."""

    READY = "READY"
    BLOCKED = "BLOCKED"
    INCOMPLETE = "INCOMPLETE"


class FindingDisposition(StrEnum):
    """Operational impact of one stable reconciliation reason."""

    INFO = "INFO"
    WARNING = "WARNING"
    BLOCKING = "BLOCKING"
    INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True, slots=True)
class ReconciliationLimits:
    """Version-one safety limits for a complete reconciliation run."""

    max_database_rows: int = DEFAULT_MAX_DATABASE_ROWS
    max_filesystem_entries: int = DEFAULT_MAX_FILESYSTEM_ENTRIES
    max_hashed_bytes: int = DEFAULT_MAX_HASHED_BYTES
    max_temporary_files_hashed: int = DEFAULT_MAX_TEMPORARY_FILES_HASHED
    max_elapsed_seconds: int = DEFAULT_MAX_ELAPSED_SECONDS
    max_report_items_per_reason: int = DEFAULT_MAX_REPORT_ITEMS_PER_REASON
    max_report_bytes: int = DEFAULT_MAX_REPORT_BYTES
    stale_temporary_age_seconds: int = DEFAULT_STALE_TEMPORARY_AGE_SECONDS
    unregistered_object_grace_seconds: int = DEFAULT_UNREGISTERED_OBJECT_GRACE_SECONDS
    traversal_depth: int = MAX_TRAVERSAL_DEPTH
    concurrency: int = MAX_CONCURRENCY

    def __post_init__(self) -> None:
        """Enforce compiled absolute ceilings and fixed scan topology."""
        maxima = {
            "max_database_rows": MAX_DATABASE_ROWS,
            "max_filesystem_entries": MAX_FILESYSTEM_ENTRIES,
            "max_hashed_bytes": MAX_HASHED_BYTES,
            "max_temporary_files_hashed": MAX_TEMPORARY_FILES_HASHED,
            "max_elapsed_seconds": MAX_ELAPSED_SECONDS,
            "max_report_items_per_reason": MAX_REPORT_ITEMS_PER_REASON,
            "max_report_bytes": MAX_REPORT_BYTES,
        }
        for name, maximum in maxima.items():
            value = int(getattr(self, name))
            minimum = {
                "max_database_rows": 2,
                "max_report_bytes": 512,
            }.get(name, 1)
            if value < minimum or value > maximum:
                raise ValueError(f"{name} must be between {minimum} and {maximum}.")
        for name in (
            "stale_temporary_age_seconds",
            "unregistered_object_grace_seconds",
        ):
            if int(getattr(self, name)) < 1:
                raise ValueError(f"{name} must be positive.")
        if self.traversal_depth != MAX_TRAVERSAL_DEPTH:
            raise ValueError("traversal_depth is fixed at 4.")
        if self.concurrency != MAX_CONCURRENCY:
            raise ValueError("concurrency is fixed at 1.")

    def store_limits(self) -> ManagedStoreInventoryLimits:
        """Return the physical-store subset of the limits."""
        return ManagedStoreInventoryLimits(
            max_filesystem_entries=self.max_filesystem_entries,
            max_hashed_bytes=self.max_hashed_bytes,
            max_temporary_files_hashed=self.max_temporary_files_hashed,
            max_elapsed_seconds=self.max_elapsed_seconds,
            stale_temporary_age_seconds=self.stale_temporary_age_seconds,
            max_traversal_depth=self.traversal_depth,
        )

    def as_dict(self) -> dict[str, int]:
        """Return public scalar limits."""
        return {name: int(getattr(self, name)) for name in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class RegisteredReference:
    """One private registered managed-payload reference."""

    reference_kind: str
    reference_id: int
    document_version_id: int
    extraction_id: int | None
    artefact_role_code: str | None
    content_sha256: str = field(repr=False)
    storage_key: str = field(repr=False)
    byte_size: int
    media_type: str
    created_on: Any = field(repr=False)


@dataclass(frozen=True, slots=True)
class LineageRecord:
    """One private extraction or chunk-set lineage inventory record."""

    lineage_kind: str
    lineage_id: int
    document_version_id: int
    extraction_id: int
    source_artefact_id: int | None
    source_artefact_extraction_id: int | None
    member_count: int | None
    primary_member_count: int | None
    table_member_count: int | None
    minimum_ordinal: int | None
    maximum_ordinal: int | None
    complete_yn: str | None
    text_sha256: str | None = field(repr=False)
    source_content_sha256: str | None = field(repr=False)
    chunk_count: int | None = None


@dataclass(frozen=True, slots=True)
class DatabaseSnapshot:
    """One complete, short-lived Oracle read-only inventory snapshot."""

    snapshot_id: str
    captured_at: str
    references: tuple[RegisteredReference, ...] = field(repr=False)
    lineage: tuple[LineageRecord, ...] = field(repr=False)
    complete: bool = True
    incomplete_reason_codes: tuple[str, ...] = ()
    state_fingerprint: str = ""

    @property
    def row_count(self) -> int:
        """Return the total cursor rows retained in the snapshot."""
        return len(self.references) + len(self.lineage)

    def public_dict(self) -> dict[str, object]:
        """Return safe snapshot facts without metadata identities."""
        return {
            "snapshot_id": self.snapshot_id,
            "captured_at": self.captured_at,
            "row_count": self.row_count,
            "complete": self.complete,
            "state_fingerprint": self.state_fingerprint,
        }


@dataclass(frozen=True, slots=True, order=True)
class DatabaseIdentitySample:
    """Safe numeric database identity retained for operator triage."""

    reference_kind: str
    database_id: int

    def as_dict(self) -> dict[str, object]:
        """Return the safe JSON representation."""
        return {
            "reference_kind": self.reference_kind,
            "database_id": self.database_id,
        }


@dataclass(frozen=True, slots=True)
class ReconciliationFinding:
    """One aggregated stable reason with bounded numeric samples."""

    reason_code: str
    disposition: FindingDisposition
    count: int
    samples: tuple[DatabaseIdentitySample, ...] = ()
    samples_truncated: bool = False

    def as_dict(self) -> dict[str, object]:
        """Return the public bounded finding."""
        return {
            "reason_code": self.reason_code,
            "disposition": self.disposition.value,
            "count": self.count,
            "samples": [sample.as_dict() for sample in self.samples],
            "samples_truncated": self.samples_truncated,
        }


@dataclass(frozen=True, slots=True)
class ReconciliationUsage:
    """Resources consumed by one bounded scan."""

    database_rows: int
    filesystem_entries: int
    hashed_bytes: int
    temporary_files_hashed: int
    elapsed_milliseconds: int

    def as_dict(self) -> dict[str, int]:
        """Return scalar resource usage."""
        return {name: int(getattr(self, name)) for name in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class ReconciliationCounts:
    """Safe aggregate database and physical inventory counts."""

    database_reference_count: int
    database_lineage_row_count: int
    distinct_registered_payload_count: int
    shared_payload_count: int
    shared_reference_count: int
    shared_reference_surplus_count: int
    physical_object_count: int
    physical_object_bytes: int
    temporary_file_count: int
    temporary_file_bytes: int
    distinct_temporary_content_count: int
    stale_temporary_file_count: int
    stale_temporary_file_bytes: int
    stale_temporary_youngest_age_seconds: int
    stale_temporary_oldest_age_seconds: int
    stale_temporary_distinct_content_count: int
    orphan_candidate_count: int

    def as_dict(self) -> dict[str, int]:
        """Return scalar aggregate counts."""
        return {name: int(getattr(self, name)) for name in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    """Immutable version-one operator reconciliation report."""

    scan_id: str
    status: ReconciliationStatus
    complete: bool
    started_at: str
    completed_at: str
    configuration_source: str
    limits: ReconciliationLimits
    usage: ReconciliationUsage
    database_before: DatabaseSnapshot
    database_after: DatabaseSnapshot
    inventory: ManagedStoreInventory = field(repr=False)
    counts: ReconciliationCounts
    findings: tuple[ReconciliationFinding, ...]
    state_fingerprint: str

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic report that cannot exceed its byte ceiling."""
        findings = list(self.findings)

        def payload() -> dict[str, object]:
            reason_counts = {finding.reason_code: finding.count for finding in findings}
            return {
                "report_type": "knowledge_reconciliation",
                "schema_version": REPORT_SCHEMA_VERSION,
                "scan_id": self.scan_id,
                "status": self.status.value,
                "complete": self.complete,
                "started_at": self.started_at,
                "completed_at": self.completed_at,
                "configuration": {"source": self.configuration_source},
                "limits": self.limits.as_dict(),
                "usage": self.usage.as_dict(),
                "snapshots": {
                    "database_before": self.database_before.public_dict(),
                    "filesystem": {
                        "complete": self.inventory.complete,
                        "filesystem_entries": self.inventory.filesystem_entries,
                    },
                    "database_after": self.database_after.public_dict(),
                },
                "store": {
                    "root_identity_stable": self.inventory.root_identity_stable,
                    "object_directory_compatible": (
                        self.inventory.object_directory_stable
                    ),
                    "temporary_directory_compatible": (
                        self.inventory.temporary_directory_stable
                    ),
                    "atomic_promotion_prerequisites": (
                        self.inventory.root_identity_stable
                        and self.inventory.object_directory_stable
                        and self.inventory.temporary_directory_stable
                    ),
                    "promotion_capability": "NOT_PROBED_READ_ONLY",
                },
                "counts": dict(sorted(self.counts.as_dict().items())),
                "reason_counts": dict(sorted(reason_counts.items())),
                "findings": [finding.as_dict() for finding in findings],
                "state_fingerprint": self.state_fingerprint,
            }

        while _json_size(payload()) > self.limits.max_report_bytes:
            candidate_indexes = [
                index for index, finding in enumerate(findings) if finding.samples
            ]
            if not candidate_indexes:
                return self._minimal_oversize_report()
            index = candidate_indexes[-1]
            finding = findings[index]
            findings[index] = replace(
                finding,
                samples=finding.samples[:-1],
                samples_truncated=True,
            )
        return payload()

    def _minimal_oversize_report(self) -> dict[str, object]:
        """Return the fail-closed report when even aggregates exceed the limit."""
        return {
            "report_type": "knowledge_reconciliation",
            "schema_version": REPORT_SCHEMA_VERSION,
            "scan_id": self.scan_id,
            "status": ReconciliationStatus.INCOMPLETE.value,
            "complete": False,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "reason_counts": {"RECON_REPORT_BYTE_LIMIT_EXCEEDED": 1},
            "findings": [
                {
                    "reason_code": "RECON_REPORT_BYTE_LIMIT_EXCEEDED",
                    "disposition": FindingDisposition.INCOMPLETE.value,
                    "count": 1,
                    "samples": [],
                    "samples_truncated": False,
                }
            ],
        }


def _json_size(value: object) -> int:
    """Return deterministic UTF-8 JSON size."""
    return len(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode(
            "utf-8"
        )
    )


def _fingerprint(value: object) -> str:
    """Return an opaque domain-separated inventory state fingerprint."""
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    digest = hashlib.sha256(b"orac-knowledge-reconciliation-v1\x00" + canonical)
    return f"recon-v1:{digest.hexdigest()}"


def _elapsed_inventory() -> ManagedStoreInventory:
    """Return an explicit empty inventory when no scan time remains."""
    return ManagedStoreInventory(
        entries=(),
        complete=False,
        incomplete_reason_codes=("RECON_ELAPSED_TIME_LIMIT_EXCEEDED",),
        filesystem_entries=0,
        hashed_bytes=0,
        temporary_files_hashed=0,
        elapsed_milliseconds=0,
        root_identity_stable=False,
        object_directory_stable=False,
        temporary_directory_stable=False,
    )


def _row_dicts(cursor: Any) -> Iterable[dict[str, Any]]:
    """Stream lower-case dictionaries from an Oracle cursor."""
    columns = [str(item[0]).lower() for item in cursor.description]
    while True:
        rows = cursor.fetchmany(DATABASE_PAGE_SIZE)
        if not rows:
            return
        for row in rows:
            yield dict(zip(columns, row, strict=True))


class KnowledgeReconciliationRepository:
    """Read bounded inventories through the runtime-only reconciliation API."""

    _PACKAGE = "orac_code.knowledge_reconciliation_api"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any] | None = None,
    ) -> None:
        """Initialise the repository with an injectable runtime session."""
        self._session_factory = session_factory or default_orac_session

    def load_snapshot(
        self,
        *,
        max_rows: int,
        max_elapsed_seconds: int,
    ) -> DatabaseSnapshot:
        """Load one short Oracle read-only snapshot and close its transaction."""
        if max_rows < 1 or max_rows > MAX_DATABASE_ROWS:
            raise ValueError(f"max_rows must be between 1 and {MAX_DATABASE_ROWS}.")
        if max_elapsed_seconds < 1 or max_elapsed_seconds > MAX_ELAPSED_SECONDS:
            raise ValueError(
                f"max_elapsed_seconds must be between 1 and {MAX_ELAPSED_SECONDS}."
            )
        session = self._session_factory()
        session.call_timeout = max_elapsed_seconds * 1000
        references: list[RegisteredReference] = []
        lineage: list[LineageRecord] = []
        incomplete: list[str] = []
        captured_at = datetime.now(timezone.utc).isoformat()
        try:
            with session.cursor() as cursor:
                cursor.execute("set transaction read only")
                cursor.execute("select systimestamp from dual")
                row = cursor.fetchone()
                if row:
                    captured_at = _timestamp_text(row[0])
            for procedure_name in (
                "open_registered_references",
                "open_lineage_inventory",
            ):
                remaining = max_rows - len(references) - len(lineage)
                if remaining < 1:
                    incomplete.append("RECON_DATABASE_ROW_LIMIT_EXCEEDED")
                    break
                result_cursor = session.cursor()
                try:
                    with session.cursor() as cursor:
                        cursor.callproc(
                            f"{self._PACKAGE}.{procedure_name}",
                            [result_cursor, remaining + 1],
                        )
                    for row_dict in _row_dicts(result_cursor):
                        if len(references) + len(lineage) >= max_rows:
                            incomplete.append("RECON_DATABASE_ROW_LIMIT_EXCEEDED")
                            break
                        if procedure_name == "open_registered_references":
                            references.append(_registered_reference(row_dict))
                        else:
                            lineage.append(_lineage_record(row_dict))
                finally:
                    result_cursor.close()
                if incomplete:
                    break
            session.rollback()
        except Exception:
            try:
                session.rollback()
            except Exception:
                pass
            raise
        finally:
            session.close()
        state = _snapshot_state(references, lineage)
        return DatabaseSnapshot(
            snapshot_id=str(uuid.uuid4()),
            captured_at=captured_at,
            references=tuple(references),
            lineage=tuple(lineage),
            complete=not incomplete,
            incomplete_reason_codes=tuple(incomplete),
            state_fingerprint=_fingerprint(state),
        )


def _timestamp_text(value: Any) -> str:
    """Return a stable timestamp string without relying on session lifetime."""
    formatter = getattr(value, "isoformat", None)
    return str(formatter() if callable(formatter) else value)


def _registered_reference(row: dict[str, Any]) -> RegisteredReference:
    """Convert one controlled cursor row to an immutable reference."""
    return RegisteredReference(
        reference_kind=str(row["reference_kind"]),
        reference_id=int(row["reference_id"]),
        document_version_id=int(row["document_version_id"]),
        extraction_id=(
            int(row["extraction_id"]) if row.get("extraction_id") is not None else None
        ),
        artefact_role_code=(
            str(row["artefact_role_code"])
            if row.get("artefact_role_code") is not None
            else None
        ),
        content_sha256=str(row.get("content_sha256") or ""),
        storage_key=str(row.get("storage_key") or ""),
        byte_size=(
            int(str(row["byte_size"])) if row.get("byte_size") is not None else -1
        ),
        media_type=str(row.get("media_type") or ""),
        created_on=row.get("created_on"),
    )


def _lineage_record(row: dict[str, Any]) -> LineageRecord:
    """Convert one controlled cursor row to immutable lineage facts."""

    def optional_int(name: str) -> int | None:
        return int(str(row[name])) if row.get(name) is not None else None

    return LineageRecord(
        lineage_kind=str(row["lineage_kind"]),
        lineage_id=int(row["lineage_id"]),
        document_version_id=int(row["document_version_id"]),
        extraction_id=int(row["extraction_id"]),
        source_artefact_id=optional_int("source_artefact_id"),
        source_artefact_extraction_id=optional_int("source_artefact_extraction_id"),
        member_count=optional_int("member_count"),
        primary_member_count=optional_int("primary_member_count"),
        table_member_count=optional_int("table_member_count"),
        minimum_ordinal=optional_int("minimum_ordinal"),
        maximum_ordinal=optional_int("maximum_ordinal"),
        complete_yn=(str(row["complete_yn"]) if row.get("complete_yn") else None),
        text_sha256=(str(row["text_sha256"]) if row.get("text_sha256") else None),
        source_content_sha256=(
            str(row["source_content_sha256"])
            if row.get("source_content_sha256")
            else None
        ),
        chunk_count=optional_int("chunk_count"),
    )


def _snapshot_state(
    references: Iterable[RegisteredReference],
    lineage: Iterable[LineageRecord],
) -> dict[str, object]:
    """Build canonical private snapshot material for change detection."""
    return {
        "references": [
            (
                row.reference_kind,
                row.reference_id,
                row.document_version_id,
                row.extraction_id,
                row.artefact_role_code,
                row.content_sha256,
                row.storage_key,
                row.byte_size,
                row.media_type,
            )
            for row in references
        ],
        "lineage": [
            (
                row.lineage_kind,
                row.lineage_id,
                row.document_version_id,
                row.extraction_id,
                row.source_artefact_id,
                row.source_artefact_extraction_id,
                row.member_count,
                row.primary_member_count,
                row.table_member_count,
                row.minimum_ordinal,
                row.maximum_ordinal,
                row.complete_yn,
                row.text_sha256,
                row.source_content_sha256,
                row.chunk_count,
            )
            for row in lineage
        ],
    }


_DISPOSITIONS: dict[str, FindingDisposition] = {
    "MANAGED_OBJECT_REGISTERED_VERIFIED": FindingDisposition.INFO,
    "DB_SHARED_PAYLOAD": FindingDisposition.INFO,
    "DB_RAW_LOCATOR_CANONICAL": FindingDisposition.INFO,
    "DB_RAW_LOCATOR_LEGACY": FindingDisposition.WARNING,
    "DB_CHUNK_SET_LEGACY_NULL_SOURCE": FindingDisposition.WARNING,
    "MANAGED_OBJECT_LINK_COUNT_UNEXPECTED": FindingDisposition.WARNING,
    "STORE_TEMP_ACTIVE": FindingDisposition.INFO,
    "STORE_TEMP_NAME_UNEXPECTED": FindingDisposition.WARNING,
    "STORE_TEMP_HASH_DUPLICATE": FindingDisposition.INFO,
    "RECON_DATABASE_CHANGED_DURING_SCAN": FindingDisposition.INFO,
    "RECON_FILESYSTEM_CHANGED_DURING_SCAN": FindingDisposition.INFO,
}
_INCOMPLETE_REASONS = {
    "RECON_DATABASE_ROW_LIMIT_EXCEEDED",
    "RECON_FILESYSTEM_ENTRY_LIMIT_EXCEEDED",
    "RECON_HASH_BYTE_LIMIT_EXCEEDED",
    "RECON_TEMP_HASH_FILE_LIMIT_EXCEEDED",
    "RECON_ELAPSED_TIME_LIMIT_EXCEEDED",
    "RECON_REPORT_BYTE_LIMIT_EXCEEDED",
    "RECON_CONCURRENT_CHANGE_UNRESOLVED",
    "RECON_SCAN_RETRY_REQUIRED",
    "STORE_ROOT_CHANGED_DURING_SCAN",
    "STORE_CONFIG_CHANGED_DURING_SCAN",
    "STORE_OBJECT_DIRECTORY_CHANGED_DURING_SCAN",
    "STORE_TEMP_DIRECTORY_CHANGED_DURING_SCAN",
    "STORE_ENTRY_CHANGED_DURING_SCAN",
    "MANAGED_OBJECT_UNREGISTERED_RECENT",
}


class _FindingAccumulator:
    """Aggregate stable reasons while retaining only bounded numeric samples."""

    def __init__(self, sample_limit: int) -> None:
        self._sample_limit = sample_limit
        self._counts: Counter[str] = Counter()
        self._samples: dict[str, set[DatabaseIdentitySample]] = {}

    def add(
        self,
        reason_code: str,
        *,
        count: int = 1,
        sample: DatabaseIdentitySample | None = None,
    ) -> None:
        """Add occurrences and an optional safe numeric sample."""
        self._counts[reason_code] += count
        if sample is not None:
            self._samples.setdefault(reason_code, set()).add(sample)

    def findings(self) -> tuple[ReconciliationFinding, ...]:
        """Return deterministically ordered immutable findings."""
        result: list[ReconciliationFinding] = []
        for reason_code, count in sorted(self._counts.items()):
            all_samples = sorted(self._samples.get(reason_code, set()))
            disposition = _DISPOSITIONS.get(
                reason_code,
                (
                    FindingDisposition.INCOMPLETE
                    if reason_code in _INCOMPLETE_REASONS
                    else FindingDisposition.BLOCKING
                ),
            )
            result.append(
                ReconciliationFinding(
                    reason_code=reason_code,
                    disposition=disposition,
                    count=count,
                    samples=tuple(all_samples[: self._sample_limit]),
                    samples_truncated=len(all_samples) > self._sample_limit,
                )
            )
        return tuple(result)


class KnowledgeReconciliationService:
    """Coordinate bounded database and physical inventory reconciliation."""

    def __init__(
        self,
        *,
        repository: KnowledgeReconciliationRepository,
        inspection_store: KnowledgeManagedStore,
        limits: ReconciliationLimits,
        clock: Callable[[], datetime] | None = None,
        configured_root_probe: Callable[[], Path] | None = None,
    ) -> None:
        """Initialise reconciliation around controlled read-only boundaries."""
        self._repository = repository
        self._store = inspection_store
        self._limits = limits
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._configured_root_probe = configured_root_probe

    def reconcile(self) -> ReconciliationReport:
        """Run two database snapshots around one verified physical scan."""
        started = self._clock()
        started_monotonic = time.monotonic()
        per_snapshot_limit = self._limits.max_database_rows // 2

        def remaining_seconds() -> int:
            elapsed = time.monotonic() - started_monotonic
            return max(0, math.ceil(self._limits.max_elapsed_seconds - elapsed))

        before = self._repository.load_snapshot(
            max_rows=per_snapshot_limit,
            max_elapsed_seconds=self._limits.max_elapsed_seconds,
        )
        remaining = remaining_seconds()
        if remaining:
            inventory = self._store.inventory(
                replace(self._limits.store_limits(), max_elapsed_seconds=remaining)
            )
        else:
            inventory = _elapsed_inventory()
        remaining = remaining_seconds()
        if remaining:
            after = self._repository.load_snapshot(
                max_rows=per_snapshot_limit,
                max_elapsed_seconds=remaining,
            )
        else:
            after = replace(
                before,
                snapshot_id=str(uuid.uuid4()),
                complete=False,
                incomplete_reason_codes=(
                    *before.incomplete_reason_codes,
                    "RECON_ELAPSED_TIME_LIMIT_EXCEEDED",
                ),
            )
        accumulator = _FindingAccumulator(self._limits.max_report_items_per_reason)

        for reason in (*before.incomplete_reason_codes, *after.incomplete_reason_codes):
            accumulator.add(reason)
        for reason in inventory.incomplete_reason_codes:
            accumulator.add(reason)
        if before.state_fingerprint != after.state_fingerprint:
            accumulator.add("RECON_DATABASE_CHANGED_DURING_SCAN")
        if not (
            inventory.root_identity_stable
            and inventory.object_directory_stable
            and inventory.temporary_directory_stable
        ):
            accumulator.add("RECON_FILESYSTEM_CHANGED_DURING_SCAN")
        if self._configured_root_probe is not None:
            initial_root = self._store.facts().configured_root.expanduser().absolute()
            try:
                final_root = self._configured_root_probe().expanduser().absolute()
            except (KeyError, OSError, RuntimeError, TypeError, ValueError):
                accumulator.add("STORE_CONFIG_CHANGED_DURING_SCAN")
            else:
                if final_root != initial_root:
                    accumulator.add("STORE_CONFIG_CHANGED_DURING_SCAN")

        self._classify_database(after, accumulator)
        self._classify_lineage(after.lineage, accumulator)
        counts = self._classify_physical(before, after, inventory, accumulator)
        elapsed_milliseconds = max(
            0, int((time.monotonic() - started_monotonic) * 1000)
        )
        if elapsed_milliseconds >= self._limits.max_elapsed_seconds * 1000:
            accumulator.add("RECON_ELAPSED_TIME_LIMIT_EXCEEDED")
        findings = accumulator.findings()
        complete = (
            before.complete
            and after.complete
            and inventory.complete
            and not any(
                finding.disposition == FindingDisposition.INCOMPLETE
                for finding in findings
            )
        )
        if not complete:
            status = ReconciliationStatus.INCOMPLETE
        elif any(
            finding.disposition == FindingDisposition.BLOCKING for finding in findings
        ):
            status = ReconciliationStatus.BLOCKED
        else:
            status = ReconciliationStatus.READY
        completed = self._clock()
        usage = ReconciliationUsage(
            database_rows=before.row_count + after.row_count,
            filesystem_entries=inventory.filesystem_entries,
            hashed_bytes=inventory.hashed_bytes,
            temporary_files_hashed=inventory.temporary_files_hashed,
            elapsed_milliseconds=max(
                inventory.elapsed_milliseconds,
                elapsed_milliseconds,
            ),
        )
        state_fingerprint = _fingerprint(
            {
                "database": after.state_fingerprint,
                "physical": [
                    (
                        entry.entry_kind,
                        entry.identity_digest,
                        entry.content_digest,
                        entry.byte_size,
                        entry.reason_codes,
                    )
                    for entry in inventory.entries
                ],
                "reasons": [
                    (finding.reason_code, finding.count) for finding in findings
                ],
            }
        )
        return ReconciliationReport(
            scan_id=str(uuid.uuid4()),
            status=status,
            complete=complete,
            started_at=started.isoformat(),
            completed_at=completed.isoformat(),
            configuration_source=self._store.facts().configuration_source,
            limits=self._limits,
            usage=usage,
            database_before=before,
            database_after=after,
            inventory=inventory,
            counts=counts,
            findings=findings,
            state_fingerprint=state_fingerprint,
        )

    def _classify_database(
        self,
        snapshot: DatabaseSnapshot,
        accumulator: _FindingAccumulator,
    ) -> None:
        references_by_digest: dict[str, list[RegisteredReference]] = {}
        for reference in snapshot.references:
            sample = _reference_sample(reference)
            try:
                identity = ManagedObjectIdentity(
                    reference.content_sha256,
                    reference.byte_size,
                )
            except ValueError as exc:
                reason = (
                    "DB_REFERENCE_SIZE_INVALID"
                    if "byte size" in str(exc)
                    else "DB_REFERENCE_HASH_INVALID"
                )
                accumulator.add(reason, sample=sample)
                continue
            references_by_digest.setdefault(identity.sha256, []).append(reference)
            if not reference.media_type.strip():
                accumulator.add("DB_REFERENCE_MEDIA_TYPE_INVALID", sample=sample)
            canonical_key = self._store.storage_key(identity.sha256)
            if reference.reference_kind == "RAW":
                if reference.storage_key == canonical_key:
                    accumulator.add("DB_RAW_LOCATOR_CANONICAL", sample=sample)
                elif reference.storage_key == self._store.legacy_storage_key(
                    identity.sha256
                ):
                    accumulator.add("DB_RAW_LOCATOR_LEGACY", sample=sample)
                else:
                    accumulator.add("DB_RAW_LOCATOR_UNSUPPORTED", sample=sample)
            elif reference.reference_kind == "ARTEFACT":
                if reference.storage_key != canonical_key:
                    accumulator.add(
                        "DB_ARTEFACT_STORAGE_KEY_INVALID",
                        sample=sample,
                    )
                if reference.artefact_role_code not in {
                    "PRIMARY",
                    "MANIFEST",
                    "TABLE",
                    "METADATA",
                }:
                    accumulator.add("DB_ARTEFACT_ROLE_INVALID", sample=sample)
                else:
                    expected_media_type = {
                        "PRIMARY": "text/markdown; charset=utf-8",
                        "MANIFEST": "text/markdown; charset=utf-8",
                        "TABLE": "text/csv; charset=utf-8",
                        "METADATA": "application/json",
                    }[str(reference.artefact_role_code)]
                    if reference.media_type != expected_media_type:
                        accumulator.add(
                            "DB_REFERENCE_MEDIA_TYPE_INVALID",
                            sample=sample,
                        )
            else:
                accumulator.add("DB_REFERENCE_KIND_INVALID", sample=sample)

        for references in references_by_digest.values():
            if len(references) > 1:
                accumulator.add(
                    "DB_SHARED_PAYLOAD",
                    sample=_reference_sample(references[0]),
                )
            if len({reference.byte_size for reference in references}) > 1:
                for reference in references:
                    accumulator.add(
                        "DB_CONTRADICTORY_PAYLOAD_SIZE",
                        sample=_reference_sample(reference),
                    )

    @staticmethod
    def _classify_lineage(
        lineage: Iterable[LineageRecord],
        accumulator: _FindingAccumulator,
    ) -> None:
        for row in lineage:
            sample = DatabaseIdentitySample(row.lineage_kind, row.lineage_id)
            if row.lineage_kind == "EXTRACTION":
                if row.complete_yn != "Y":
                    accumulator.add(
                        "DB_ARTEFACT_OUTPUT_SET_INCOMPLETE",
                        sample=sample,
                    )
                if int(row.primary_member_count or 0) == 0:
                    accumulator.add("DB_EXTRACTION_PRIMARY_MISSING", sample=sample)
                elif int(row.primary_member_count or 0) > 1:
                    accumulator.add("DB_EXTRACTION_PRIMARY_MULTIPLE", sample=sample)
                if (
                    row.text_sha256
                    and row.source_content_sha256
                    and row.text_sha256 != row.source_content_sha256
                ):
                    accumulator.add(
                        "DB_EXTRACTION_PRIMARY_HASH_MISMATCH",
                        sample=sample,
                    )
            elif row.lineage_kind == "CHUNK_SET":
                if row.source_artefact_id is None:
                    accumulator.add(
                        "DB_CHUNK_SET_LEGACY_NULL_SOURCE",
                        sample=sample,
                    )
                elif row.source_artefact_extraction_id is None:
                    accumulator.add("DB_CHUNK_SET_ARTEFACT_MISSING", sample=sample)
                elif row.source_artefact_extraction_id != row.extraction_id:
                    accumulator.add(
                        "DB_CHUNK_SET_ARTEFACT_CROSS_EXTRACTION",
                        sample=sample,
                    )
            else:
                accumulator.add("DB_LINEAGE_KIND_INVALID", sample=sample)

    def _classify_physical(
        self,
        before: DatabaseSnapshot,
        after: DatabaseSnapshot,
        inventory: ManagedStoreInventory,
        accumulator: _FindingAccumulator,
    ) -> ReconciliationCounts:
        before_by_digest = _valid_references_by_digest(before.references)
        after_by_digest = _valid_references_by_digest(after.references)
        objects: dict[str, ManagedStoreInventoryEntry] = {}
        temporary_hash_counts: Counter[str] = Counter()
        for entry in inventory.entries:
            for reason in entry.reason_codes:
                accumulator.add(reason)
            if entry.entry_kind == "OBJECT" and entry.identity_digest:
                objects[entry.identity_digest] = entry
            elif entry.entry_kind == "TEMPORARY" and entry.content_digest:
                temporary_hash_counts[entry.content_digest] += 1

        duplicate_temporary_count = sum(
            count - 1 for count in temporary_hash_counts.values() if count > 1
        )
        if duplicate_temporary_count:
            accumulator.add(
                "STORE_TEMP_HASH_DUPLICATE",
                count=duplicate_temporary_count,
            )

        for digest, references in after_by_digest.items():
            object_entry = objects.get(digest)
            if object_entry is None:
                if digest not in before_by_digest:
                    accumulator.add("RECON_CONCURRENT_CHANGE_UNRESOLVED")
                    accumulator.add("RECON_SCAN_RETRY_REQUIRED")
                else:
                    for reference in references:
                        accumulator.add(
                            "MANAGED_OBJECT_MISSING",
                            sample=_reference_sample(reference),
                        )
                continue
            if object_entry.stable and not {
                "MANAGED_OBJECT_HASH_MISMATCH",
                "STORE_ENTRY_CHANGED_DURING_SCAN",
            }.intersection(object_entry.reason_codes):
                for reference in references:
                    if reference.byte_size != object_entry.byte_size:
                        accumulator.add(
                            "MANAGED_OBJECT_SIZE_MISMATCH",
                            sample=_reference_sample(reference),
                        )
                    else:
                        accumulator.add(
                            "MANAGED_OBJECT_REGISTERED_VERIFIED",
                            sample=_reference_sample(reference),
                        )

        registered_digests = set(after_by_digest)
        for digest, entry in objects.items():
            if digest in registered_digests:
                continue
            if digest in before_by_digest:
                accumulator.add("RECON_CONCURRENT_CHANGE_UNRESOLVED")
            elif entry.age_seconds < self._limits.unregistered_object_grace_seconds:
                accumulator.add("MANAGED_OBJECT_UNREGISTERED_RECENT")
                accumulator.add("RECON_SCAN_RETRY_REQUIRED")
            elif entry.stable and inventory.complete:
                accumulator.add("MANAGED_OBJECT_ORPHAN_CONFIRMED")
            else:
                accumulator.add("RECON_CONCURRENT_CHANGE_UNRESOLVED")

        shared_references = [
            references for references in after_by_digest.values() if len(references) > 1
        ]
        temporary_entries = [
            entry for entry in inventory.entries if entry.entry_kind == "TEMPORARY"
        ]
        stale_entries = [
            entry
            for entry in temporary_entries
            if "STORE_TEMP_STALE" in entry.reason_codes
        ]
        stale_ages = [entry.age_seconds for entry in stale_entries]
        stale_hashes = {
            entry.content_digest
            for entry in stale_entries
            if entry.content_digest is not None
        }
        return ReconciliationCounts(
            database_reference_count=len(after.references),
            database_lineage_row_count=len(after.lineage),
            distinct_registered_payload_count=len(after_by_digest),
            shared_payload_count=len(shared_references),
            shared_reference_count=sum(
                len(references) for references in shared_references
            ),
            shared_reference_surplus_count=sum(
                len(references) - 1 for references in shared_references
            ),
            physical_object_count=len(objects),
            physical_object_bytes=sum(entry.byte_size for entry in objects.values()),
            temporary_file_count=len(temporary_entries),
            temporary_file_bytes=sum(entry.byte_size for entry in temporary_entries),
            distinct_temporary_content_count=len(temporary_hash_counts),
            stale_temporary_file_count=len(stale_entries),
            stale_temporary_file_bytes=sum(entry.byte_size for entry in stale_entries),
            stale_temporary_youngest_age_seconds=min(stale_ages, default=0),
            stale_temporary_oldest_age_seconds=max(stale_ages, default=0),
            stale_temporary_distinct_content_count=len(stale_hashes),
            orphan_candidate_count=sum(
                digest not in registered_digests for digest in objects
            ),
        )


def _reference_sample(reference: RegisteredReference) -> DatabaseIdentitySample:
    """Return the safe numeric identity for one registered reference."""
    return DatabaseIdentitySample(reference.reference_kind, reference.reference_id)


def _valid_references_by_digest(
    references: Iterable[RegisteredReference],
) -> dict[str, list[RegisteredReference]]:
    """Group structurally valid references by private content identity."""
    result: dict[str, list[RegisteredReference]] = {}
    for reference in references:
        try:
            identity = ManagedObjectIdentity(
                reference.content_sha256,
                reference.byte_size,
            )
        except ValueError:
            continue
        result.setdefault(identity.sha256, []).append(reference)
    return result
