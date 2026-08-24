"""Tests for bounded read-only knowledge reconciliation."""

# Author: Clive Bostock
# Date: 14-Aug-2026
# Description: Verifies inventory, classification, redaction, and scan ceilings.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from orac_core.knowledge.managed_store import KnowledgeManagedStore  # noqa: E402
from orac_core.knowledge.reconciliation import DatabaseSnapshot  # noqa: E402
from orac_core.knowledge.reconciliation import (  # noqa: E402
    KnowledgeReconciliationService,
)
from orac_core.knowledge.reconciliation import (  # noqa: E402
    KnowledgeReconciliationRepository,
)
from orac_core.knowledge.reconciliation import LineageRecord  # noqa: E402
from orac_core.knowledge.reconciliation import ReconciliationLimits  # noqa: E402
from orac_core.knowledge.reconciliation import ReconciliationStatus  # noqa: E402
from orac_core.knowledge.reconciliation import RegisteredReference  # noqa: E402


class _Repository:
    """Return deterministic before and after snapshots."""

    def __init__(
        self,
        before: DatabaseSnapshot,
        after: DatabaseSnapshot | None = None,
    ) -> None:
        self._snapshots = [before, after or before]
        self.limits: list[int] = []

    def load_snapshot(
        self,
        *,
        max_rows: int,
        max_elapsed_seconds: int,
    ) -> DatabaseSnapshot:
        """Return the next snapshot and retain the requested bound."""
        self.limits.append(max_rows)
        assert max_elapsed_seconds > 0
        return self._snapshots.pop(0)


class _Cursor:
    """Small Oracle cursor double for read-only repository tests."""

    def __init__(self, session: "_Session") -> None:
        self._session = session
        self.description: list[tuple[str]] = []
        self._rows: list[tuple[object, ...]] = []

    def __enter__(self) -> "_Cursor":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def execute(self, statement: str) -> None:
        self._session.trace.append(statement.lower())
        if "systimestamp" in statement.lower():
            self._rows = [(datetime(2026, 8, 14, tzinfo=timezone.utc),)]

    def fetchone(self) -> tuple[object, ...] | None:
        return self._rows.pop(0) if self._rows else None

    def callproc(self, name: str, parameters: list[object]) -> None:
        self._session.trace.append(name.lower())
        result_cursor = parameters[0]
        assert isinstance(result_cursor, _Cursor)
        if name.endswith("open_registered_references"):
            digest = hashlib.sha256(b"repository").hexdigest()
            result_cursor.description = [
                (column,)
                for column in (
                    "REFERENCE_KIND",
                    "REFERENCE_ID",
                    "DOCUMENT_VERSION_ID",
                    "EXTRACTION_ID",
                    "ARTEFACT_ROLE_CODE",
                    "CONTENT_SHA256",
                    "STORAGE_KEY",
                    "BYTE_SIZE",
                    "MEDIA_TYPE",
                    "CREATED_ON",
                )
            ]
            result_cursor._rows = [
                (
                    "RAW",
                    1,
                    1,
                    None,
                    None,
                    digest,
                    f"sha256:{digest}",
                    10,
                    "text/plain",
                    None,
                )
            ]
        else:
            result_cursor.description = [
                (column,)
                for column in (
                    "LINEAGE_KIND",
                    "LINEAGE_ID",
                    "DOCUMENT_VERSION_ID",
                    "EXTRACTION_ID",
                    "SOURCE_ARTEFACT_ID",
                    "SOURCE_ARTEFACT_EXTRACTION_ID",
                    "MEMBER_COUNT",
                    "PRIMARY_MEMBER_COUNT",
                    "TABLE_MEMBER_COUNT",
                    "MINIMUM_ORDINAL",
                    "MAXIMUM_ORDINAL",
                    "COMPLETE_YN",
                    "TEXT_SHA256",
                    "SOURCE_CONTENT_SHA256",
                    "CHUNK_COUNT",
                )
            ]
            result_cursor._rows = []

    def fetchmany(self, size: int) -> list[tuple[object, ...]]:
        rows = self._rows[:size]
        self._rows = self._rows[size:]
        return rows

    def close(self) -> None:
        pass


class _Session:
    """Record transaction order for the repository contract."""

    def __init__(self) -> None:
        self.trace: list[str] = []

    def cursor(self) -> _Cursor:
        return _Cursor(self)

    def rollback(self) -> None:
        self.trace.append("rollback")

    def close(self) -> None:
        self.trace.append("close")


def _snapshot(
    references: tuple[RegisteredReference, ...] = (),
    lineage: tuple[LineageRecord, ...] = (),
    *,
    fingerprint: str = "recon-v1:stable",
) -> DatabaseSnapshot:
    return DatabaseSnapshot(
        snapshot_id="snapshot",
        captured_at="2026-08-14T12:00:00+00:00",
        references=references,
        lineage=lineage,
        state_fingerprint=fingerprint,
    )


def _reference(
    digest: str,
    byte_size: int,
    *,
    reference_id: int = 1,
    kind: str = "RAW",
) -> RegisteredReference:
    return RegisteredReference(
        reference_kind=kind,
        reference_id=reference_id,
        document_version_id=1,
        extraction_id=1 if kind == "ARTEFACT" else None,
        artefact_role_code="PRIMARY" if kind == "ARTEFACT" else None,
        content_sha256=digest,
        storage_key=f"sha256:{digest}",
        byte_size=byte_size,
        media_type="text/markdown; charset=utf-8",
        created_on=None,
    )


def _limits(**overrides: int) -> ReconciliationLimits:
    values = {
        "max_database_rows": 100,
        "max_filesystem_entries": 100,
        "max_hashed_bytes": 1024 * 1024,
        "max_temporary_files_hashed": 20,
        "max_elapsed_seconds": 30,
        "max_report_items_per_reason": 5,
        "max_report_bytes": 100_000,
        "stale_temporary_age_seconds": 60,
        "unregistered_object_grace_seconds": 60,
    }
    values.update(overrides)
    return ReconciliationLimits(**values)


def _service(
    root: Path,
    snapshot: DatabaseSnapshot,
    *,
    after: DatabaseSnapshot | None = None,
    limits: ReconciliationLimits | None = None,
) -> KnowledgeReconciliationService:
    store = KnowledgeManagedStore.for_read_only_inspection(root)
    return KnowledgeReconciliationService(
        repository=_Repository(snapshot, after),
        inspection_store=store,
        limits=limits or _limits(),
        clock=lambda: datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc),
    )


def _cli_module() -> object:
    """Load the hyphenated controller script for isolated CLI tests."""
    path = PROJECT_ROOT / "src" / "controller" / "orac-knowledge.py"
    spec = importlib.util.spec_from_file_location("orac_knowledge_controller", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_registered_object_is_ready_and_report_is_redacted() -> None:
    """A complete registered object yields only safe aggregate output."""
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "managed"
        result = KnowledgeManagedStore(root).put_bytes(b"safe payload")
        reference = _reference(result.identity.sha256, result.identity.byte_size)

        report = _service(root, _snapshot((reference,))).reconcile()
        payload = report.as_dict()
        encoded = json.dumps(payload, sort_keys=True)

        assert report.status == ReconciliationStatus.READY
        assert payload["report_type"] == "knowledge_reconciliation"
        assert payload["schema_version"] == 1
        assert result.identity.sha256 not in encoded
        assert str(root) not in encoded
        assert result.storage_key not in encoded
        assert payload["counts"]["physical_object_count"] == 1


def test_repository_uses_a_short_read_only_transaction() -> None:
    """Oracle snapshot loading rolls back and closes before returning."""
    session = _Session()

    snapshot = KnowledgeReconciliationRepository(
        session_factory=lambda: session
    ).load_snapshot(max_rows=10, max_elapsed_seconds=30)

    assert snapshot.row_count == 1
    assert session.trace[0] == "set transaction read only"
    assert "orac_code.knowledge_reconciliation_api.open_registered_references" in (
        session.trace
    )
    assert session.trace[-2:] == ["rollback", "close"]
    assert session.call_timeout == 30_000


def test_cli_reconcile_options_only_lower_configured_ceilings() -> None:
    """The CLI cannot widen administrator-configured safety limits."""
    module = _cli_module()
    parser = module.build_parser()  # type: ignore[attr-defined]
    args = parser.parse_args(["reconcile", "--max-database-rows", "100"])

    class _Config:
        def int_config_value(
            self,
            _section: str,
            _key: str,
            default: int,
        ) -> int:
            return default

    limits = module._reconciliation_limits(_Config(), args)  # type: ignore[attr-defined]
    assert limits.max_database_rows == 100

    raised_args = parser.parse_args(["reconcile", "--max-database-rows", "250001"])
    with pytest.raises(ValueError, match="may lower but not raise"):
        module._reconciliation_limits(  # type: ignore[attr-defined]
            _Config(),
            raised_args,
        )


@pytest.mark.parametrize(
    ("status", "expected_exit"),
    (("READY", 0), ("BLOCKED", 2), ("INCOMPLETE", 3)),
)
def test_cli_maps_reconciliation_status_to_stable_exit_codes(
    status: str,
    expected_exit: int,
) -> None:
    """Automation receives distinct ready, blocked, and incomplete exits."""
    module = _cli_module()
    report = SimpleNamespace(as_dict=lambda: {"status": status})
    service = SimpleNamespace(reconcile=lambda: report)
    with (
        patch.object(module, "_config", return_value=SimpleNamespace()),
        patch.object(module, "_reconciliation_service", return_value=service),
        patch.object(module, "_emit"),
    ):
        assert module.main(["reconcile", "--json"]) == expected_exit


def test_shared_payload_counts_one_physical_object() -> None:
    """Raw and artefact references can safely share one physical payload."""
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "managed"
        result = KnowledgeManagedStore(root).put_bytes(b"shared")
        references = (
            _reference(result.identity.sha256, result.identity.byte_size),
            _reference(
                result.identity.sha256,
                result.identity.byte_size,
                reference_id=2,
                kind="ARTEFACT",
            ),
        )

        report = _service(root, _snapshot(references)).reconcile()

        assert report.status == ReconciliationStatus.READY
        assert report.counts.database_reference_count == 2
        assert report.counts.distinct_registered_payload_count == 1
        assert report.counts.shared_payload_count == 1
        assert report.counts.physical_object_count == 1


def test_old_unregistered_object_is_blocked_but_not_removed() -> None:
    """A stable old orphan is reported without mutating its bytes."""
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "managed"
        result = KnowledgeManagedStore(root).put_bytes(b"orphan")
        object_path = next(
            path for path in (root / "sha256").rglob("*") if path.is_file()
        )
        old = time.time() - 3600
        os.utime(object_path, (old, old))

        report = _service(root, _snapshot()).reconcile()
        reasons = {finding.reason_code for finding in report.findings}

        assert report.status == ReconciliationStatus.BLOCKED
        assert "MANAGED_OBJECT_ORPHAN_CONFIRMED" in reasons
        assert object_path.read_bytes() == b"orphan"
        assert result.identity.sha256 not in json.dumps(report.as_dict())


def test_recent_unregistered_object_requires_retry() -> None:
    """A promotion-window candidate cannot be called a durable orphan."""
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "managed"
        KnowledgeManagedStore(root).put_bytes(b"recent")

        report = _service(root, _snapshot()).reconcile()
        reasons = {finding.reason_code for finding in report.findings}

        assert report.status == ReconciliationStatus.INCOMPLETE
        assert "MANAGED_OBJECT_UNREGISTERED_RECENT" in reasons
        assert "RECON_SCAN_RETRY_REQUIRED" in reasons


def test_stale_temporary_file_is_blocking_and_unchanged() -> None:
    """A stale temporary file is diagnosed without cleanup."""
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "managed"
        KnowledgeManagedStore(root)
        temporary_path = root / ".tmp" / ("capture-" + "a" * 32 + ".tmp")
        temporary_path.write_bytes(b"interrupted")
        old = time.time() - 3600
        os.utime(temporary_path, (old, old))

        report = _service(root, _snapshot()).reconcile()
        reasons = {finding.reason_code for finding in report.findings}

        assert report.status == ReconciliationStatus.BLOCKED
        assert "STORE_TEMP_STALE" in reasons
        assert report.counts.stale_temporary_file_count == 1
        assert report.counts.stale_temporary_file_bytes == len(b"interrupted")
        assert report.counts.stale_temporary_youngest_age_seconds >= 3600
        assert report.counts.stale_temporary_oldest_age_seconds >= 3600
        assert report.counts.stale_temporary_distinct_content_count == 1
        assert temporary_path.read_bytes() == b"interrupted"


def test_filesystem_ceiling_is_explicitly_incomplete() -> None:
    """A truncated physical scan never reports READY."""
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "managed"
        KnowledgeManagedStore(root).put_bytes(b"bounded")

        report = _service(
            root,
            _snapshot(),
            limits=_limits(max_filesystem_entries=1),
        ).reconcile()

        assert report.status == ReconciliationStatus.INCOMPLETE
        assert any(
            finding.reason_code == "RECON_FILESYSTEM_ENTRY_LIMIT_EXCEEDED"
            for finding in report.findings
        )


def test_symlink_and_corrupt_object_are_reported_without_following() -> None:
    """Physical inventory blocks unsafe and hash-mismatched entries."""
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "managed"
        result = KnowledgeManagedStore(root).put_bytes(b"original")
        object_path = next(
            path for path in (root / "sha256").rglob("*") if path.is_file()
        )
        object_path.write_bytes(b"modified")
        (root / "unsafe-link").symlink_to(object_path)
        reference = _reference(result.identity.sha256, result.identity.byte_size)

        report = _service(root, _snapshot((reference,))).reconcile()
        reasons = {finding.reason_code for finding in report.findings}

        assert report.status == ReconciliationStatus.BLOCKED
        assert "MANAGED_OBJECT_HASH_MISMATCH" in reasons
        assert "STORE_SYMLINK_FOUND" in reasons


def test_new_database_reference_missing_from_scanned_inventory_is_incomplete() -> None:
    """A database registration after enumeration is retried, not called durable."""
    digest = hashlib.sha256(b"late registration").hexdigest()
    reference = _reference(digest, len(b"late registration"))
    before = _snapshot(fingerprint="recon-v1:before")
    after = _snapshot((reference,), fingerprint="recon-v1:after")
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "managed"
        KnowledgeManagedStore(root)

        report = _service(root, before, after=after).reconcile()
        reasons = {finding.reason_code for finding in report.findings}

        assert report.status == ReconciliationStatus.INCOMPLETE
        assert "RECON_CONCURRENT_CHANGE_UNRESOLVED" in reasons
        assert "MANAGED_OBJECT_MISSING" not in reasons


def test_database_change_is_visible_without_forcing_failure_when_resolved() -> None:
    """A registration completed during the scan is visible and can resolve."""
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "managed"
        result = KnowledgeManagedStore(root).put_bytes(b"registered during scan")
        reference = _reference(result.identity.sha256, result.identity.byte_size)
        before = _snapshot(fingerprint="recon-v1:before")
        after = _snapshot((reference,), fingerprint="recon-v1:after")

        report = _service(root, before, after=after).reconcile()
        reasons = {finding.reason_code for finding in report.findings}

        assert report.status == ReconciliationStatus.READY
        assert "RECON_DATABASE_CHANGED_DURING_SCAN" in reasons


def test_configured_root_change_during_scan_is_incomplete_and_redacted() -> None:
    """A changed configured root is visible without exposing either value."""
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "managed"
        KnowledgeManagedStore(root)
        service = KnowledgeReconciliationService(
            repository=_Repository(_snapshot()),
            inspection_store=KnowledgeManagedStore.for_read_only_inspection(root),
            limits=_limits(),
            configured_root_probe=lambda: Path(temporary) / "replacement",
        )

        report = service.reconcile()
        encoded = json.dumps(report.as_dict(), sort_keys=True)

        assert report.status == ReconciliationStatus.INCOMPLETE
        assert any(
            finding.reason_code == "STORE_CONFIG_CHANGED_DURING_SCAN"
            for finding in report.findings
        )
        assert str(root) not in encoded
        assert str(Path(temporary) / "replacement") not in encoded


def test_invalid_lineage_is_distinct_from_disk_failure() -> None:
    """Incomplete output lineage uses database-specific reason codes."""
    lineage = (
        LineageRecord(
            lineage_kind="EXTRACTION",
            lineage_id=7,
            document_version_id=7,
            extraction_id=7,
            source_artefact_id=None,
            source_artefact_extraction_id=None,
            member_count=0,
            primary_member_count=0,
            table_member_count=0,
            minimum_ordinal=None,
            maximum_ordinal=None,
            complete_yn="N",
            text_sha256=hashlib.sha256(b"text").hexdigest(),
            source_content_sha256=None,
        ),
    )
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "managed"
        KnowledgeManagedStore(root)

        report = _service(root, _snapshot(lineage=lineage)).reconcile()
        reasons = {finding.reason_code for finding in report.findings}

        assert report.status == ReconciliationStatus.BLOCKED
        assert "DB_ARTEFACT_OUTPUT_SET_INCOMPLETE" in reasons
        assert "DB_EXTRACTION_PRIMARY_MISSING" in reasons
        assert "MANAGED_OBJECT_MISSING" not in reasons


def test_report_samples_are_bounded_and_numeric_only() -> None:
    """Reports retain only deterministic numeric database samples."""
    invalid_references = tuple(
        _reference("invalid", 1, reference_id=identifier) for identifier in range(1, 8)
    )
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "managed"
        KnowledgeManagedStore(root)

        report = _service(
            root,
            _snapshot(invalid_references),
            limits=_limits(max_report_items_per_reason=2),
        ).reconcile()
        finding = next(
            item
            for item in report.findings
            if item.reason_code == "DB_REFERENCE_HASH_INVALID"
        )

        assert len(finding.samples) == 2
        assert finding.samples_truncated is True
        assert [sample.database_id for sample in finding.samples] == [1, 2]


def test_report_byte_ceiling_fails_closed_with_minimal_contract() -> None:
    """An oversized ordinary report becomes a bounded incomplete report."""
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "managed"
        KnowledgeManagedStore(root)

        payload = (
            _service(
                root,
                _snapshot(),
                limits=_limits(max_report_bytes=512),
            )
            .reconcile()
            .as_dict()
        )
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        assert len(encoded) <= 512
        assert payload["status"] == "INCOMPLETE"
        assert payload["reason_counts"] == {"RECON_REPORT_BYTE_LIMIT_EXCEEDED": 1}
