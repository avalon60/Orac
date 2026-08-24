"""Inspect and migrate legacy Core knowledge storage safely."""

# Author: Clive Bostock
# Date: 13-Aug-2026
# Description: Provides read-only preflight and bounded legacy backfill services.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any

from .managed_store import KnowledgeManagedStore
from .managed_store import ManagedObjectIdentity
from .managed_store import ManagedStoreError
from .repository import default_orac_session

CANONICAL_MARKDOWN_MEDIA = "text/markdown; charset=utf-8"
DEFAULT_SCAN_LIMIT = 10_000
MAX_SCAN_LIMIT = 100_000
MAX_APPLY_LIMIT = 100
PAGE_SIZE = 500


def _oracle_value(value: Any) -> Any:
    """Materialise a database LOB while its owning session is open."""
    reader = getattr(value, "read", None)
    return reader() if callable(reader) else value


def _rows(cursor: Any) -> list[dict[str, Any]]:
    """Return lower-case dictionaries from one database cursor."""
    columns = [str(item[0]).lower() for item in cursor.description]
    return [
        {name: _oracle_value(value) for name, value in zip(columns, row, strict=True)}
        for row in cursor.fetchall()
    ]


class KnowledgeMigrationRepository:
    """Call the controlled database migration package through ORAC."""

    _PACKAGE = "orac_code.knowledge_migration_api"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any] | None = None,
    ) -> None:
        """Initialise the repository with an injectable session factory."""
        self._session_factory = session_factory or default_orac_session

    def backfill_candidates(
        self,
        *,
        after_extraction_id: int | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Load one ordered page of extraction candidates."""
        return self._candidate_page(
            "open_backfill_candidates",
            after_extraction_id,
            limit,
        )

    def raw_locator_candidates(
        self,
        *,
        after_document_version_id: int | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Load one ordered page of raw locator candidates."""
        return self._candidate_page(
            "open_raw_locator_candidates",
            after_document_version_id,
            limit,
        )

    def _candidate_page(
        self,
        procedure_name: str,
        after_id: int | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        session = self._session_factory()
        result_cursor = session.cursor()
        try:
            with session.cursor() as cursor:
                cursor.callproc(
                    f"{self._PACKAGE}.{procedure_name}",
                    [result_cursor, after_id, limit],
                )
            return _rows(result_cursor)
        finally:
            result_cursor.close()
            session.close()

    def backfill_extraction(
        self,
        *,
        extraction_id: int,
        output_set_json: str,
    ) -> dict[str, Any]:
        """Backfill and commit one complete extraction output set."""
        return self._call_and_commit(
            "backfill_extraction",
            [extraction_id, output_set_json],
        )

    def migrate_raw_locator(
        self,
        *,
        document_version_id: int,
        expected_locator: str,
        expected_sha256: str,
    ) -> dict[str, Any]:
        """Migrate and commit one verified raw locator."""
        return self._call_and_commit(
            "migrate_raw_locator",
            [document_version_id, expected_locator, expected_sha256],
        )

    def _call_and_commit(
        self,
        function_name: str,
        parameters: list[Any],
    ) -> dict[str, Any]:
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                result = cursor.callfunc(
                    f"{self._PACKAGE}.{function_name}",
                    str,
                    parameters,
                )
            payload = _oracle_value(result)
            parsed = json.loads(str(payload))
            if not isinstance(parsed, dict):
                raise TypeError("Knowledge migration result must be a JSON object.")
            session.commit()
            return parsed
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


@dataclass(frozen=True)
class MigrationCandidate:
    """One safely classified migration candidate."""

    item_id: int
    status: str
    reason_code: str
    values: dict[str, Any] = field(repr=False)

    def public_dict(self) -> dict[str, Any]:
        """Return non-sensitive candidate fields for reports."""
        return {
            "item_id": self.item_id,
            "status": self.status,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True)
class MigrationPreflight:
    """Bounded version-one migration preflight result."""

    backfill: tuple[MigrationCandidate, ...]
    raw_locators: tuple[MigrationCandidate, ...]
    truncated: bool
    store_facts: dict[str, Any]

    @property
    def blockers(self) -> tuple[MigrationCandidate, ...]:
        """Return candidates that prevent an apply operation."""
        return tuple(
            item
            for item in (*self.backfill, *self.raw_locators)
            if item.status == "BLOCKED"
        )

    def as_dict(self) -> dict[str, Any]:
        """Return the stable machine-readable report."""
        all_items = (*self.backfill, *self.raw_locators)
        reasons = Counter(item.reason_code for item in all_items)
        return {
            "schema_version": 1,
            "status": "BLOCKED" if self.blockers or self.truncated else "READY",
            "truncated": self.truncated,
            "store": self.store_facts,
            "counts": {
                "backfill_total": len(self.backfill),
                "backfill_eligible": sum(
                    item.status == "ELIGIBLE" for item in self.backfill
                ),
                "raw_locator_total": len(self.raw_locators),
                "raw_locator_eligible": sum(
                    item.status == "ELIGIBLE" for item in self.raw_locators
                ),
                "blocked": len(self.blockers),
            },
            "reason_counts": dict(sorted(reasons.items())),
            "backfill": [item.public_dict() for item in self.backfill],
            "raw_locators": [item.public_dict() for item in self.raw_locators],
        }


class KnowledgeMigrationService:
    """Coordinate read-only inspection and bounded migration batches."""

    def __init__(
        self,
        *,
        repository: KnowledgeMigrationRepository,
        inspection_store: KnowledgeManagedStore,
        write_store: KnowledgeManagedStore | None = None,
    ) -> None:
        """Initialise migration services around controlled boundaries."""
        self._repository = repository
        self._inspection_store = inspection_store
        self._write_store = write_store

    def preflight(self, *, scan_limit: int = DEFAULT_SCAN_LIMIT) -> MigrationPreflight:
        """Inspect migration candidates without changing filesystem or database state."""
        if scan_limit < 1 or scan_limit > MAX_SCAN_LIMIT:
            raise ValueError(f"scan_limit must be between 1 and {MAX_SCAN_LIMIT}.")
        backfill_rows, backfill_truncated = self._load_all(
            self._repository.backfill_candidates,
            id_field="extraction_id",
            scan_limit=scan_limit,
        )
        raw_rows, raw_truncated = self._load_all(
            self._repository.raw_locator_candidates,
            id_field="document_version_id",
            scan_limit=scan_limit,
        )
        facts = self._inspection_store.facts()
        return MigrationPreflight(
            backfill=tuple(self._classify_extraction(row) for row in backfill_rows),
            raw_locators=tuple(self._classify_raw_locator(row) for row in raw_rows),
            truncated=backfill_truncated or raw_truncated,
            store_facts={
                "configuration_source": facts.configuration_source,
                "root_device": facts.root_device,
                "temporary_device": facts.temporary_device,
                "object_device": facts.object_device,
                "promotion_method": facts.promotion_method,
                "logical_key_format": facts.logical_key_format,
                "legacy_key_reads": facts.legacy_key_reads,
            },
        )

    @staticmethod
    def _load_all(
        loader: Callable[..., list[dict[str, Any]]],
        *,
        id_field: str,
        scan_limit: int,
    ) -> tuple[list[dict[str, Any]], bool]:
        rows: list[dict[str, Any]] = []
        after_id: int | None = None
        while len(rows) <= scan_limit:
            requested = min(PAGE_SIZE, scan_limit + 1 - len(rows))
            page = loader(
                **{
                    f"after_{id_field}": after_id,
                    "limit": requested,
                }
            )
            if not page:
                return rows, False
            rows.extend(page)
            after_id = int(page[-1][id_field])
            if len(page) < requested:
                return rows[:scan_limit], len(rows) > scan_limit
        return rows[:scan_limit], True

    def _classify_extraction(self, row: dict[str, Any]) -> MigrationCandidate:
        extraction_id = int(row["extraction_id"])
        text = row.get("extracted_text")
        if not isinstance(text, str):
            return self._candidate(extraction_id, "BLOCKED", "EXTRACTION_TEXT_INVALID", row)
        if text.startswith("\ufeff") or "\r" in text or not text.endswith("\n"):
            return self._candidate(extraction_id, "BLOCKED", "EXTRACTION_TEXT_NONCANONICAL", row)
        payload = text.encode("utf-8")
        if hashlib.sha256(payload).hexdigest() != str(row.get("text_sha256") or ""):
            return self._candidate(extraction_id, "BLOCKED", "EXTRACTION_HASH_MISMATCH", row)
        if row.get("output_mime_type") != CANONICAL_MARKDOWN_MEDIA:
            return self._candidate(extraction_id, "SKIPPED", "OUTPUT_MEDIA_UNSUPPORTED", row)

        artefacts = int(row.get("artefact_count") or 0)
        legacy_sets = int(row.get("legacy_chunk_set_count") or 0)
        artefact_sets = int(row.get("artefact_chunk_set_count") or 0)
        if artefacts == 0 and legacy_sets > 0 and artefact_sets == 0:
            row["calculated_byte_size"] = len(payload)
            return self._candidate(extraction_id, "ELIGIBLE", "BACKFILL_REQUIRED", row)
        if artefacts == 0 and legacy_sets == 0 and artefact_sets == 0:
            return self._candidate(extraction_id, "SKIPPED", "NO_CHUNK_LINEAGE", row)
        if row.get("artefact_set_complete_yn") != "Y":
            return self._candidate(extraction_id, "BLOCKED", "ARTEFACT_SET_INCOMPLETE", row)
        if legacy_sets > 0 and artefact_sets > 0:
            return self._candidate(extraction_id, "BLOCKED", "CHUNK_LINEAGE_MIXED", row)
        try:
            identity = ManagedObjectIdentity(
                str(row.get("primary_content_sha256") or ""),
                int(row.get("primary_byte_size") or -1),
            )
        except ValueError:
            return self._candidate(extraction_id, "BLOCKED", "ARTEFACT_IDENTITY_INVALID", row)
        inspection = self._inspection_store.inspect_reference(
            str(row.get("primary_storage_key") or ""),
            identity,
        )
        if not inspection.ok:
            return self._candidate(extraction_id, "BLOCKED", inspection.reason_code, row)
        if legacy_sets > 0:
            return self._candidate(extraction_id, "ELIGIBLE", "BACKFILL_RELINK_REQUIRED", row)
        return self._candidate(extraction_id, "CURRENT", "ARTEFACT_BACKFILL_CURRENT", row)

    def _classify_raw_locator(self, row: dict[str, Any]) -> MigrationCandidate:
        document_version_id = int(row["document_version_id"])
        digest = str(row.get("content_sha256") or "")
        locator = str(row.get("content_uri") or "")
        try:
            identity = ManagedObjectIdentity(digest, int(row.get("byte_size") or -1))
        except ValueError:
            return self._candidate(document_version_id, "BLOCKED", "RAW_IDENTITY_INVALID", row)
        inspection = self._inspection_store.inspect_reference(locator, identity)
        if not inspection.ok:
            return self._candidate(document_version_id, "BLOCKED", inspection.reason_code, row)
        logical = self._inspection_store.storage_key(digest)
        legacy = self._inspection_store.legacy_storage_key(digest)
        if locator == logical:
            return self._candidate(document_version_id, "CURRENT", "RAW_LOCATOR_CURRENT", row)
        if locator == legacy:
            return self._candidate(document_version_id, "ELIGIBLE", "RAW_LOCATOR_LEGACY", row)
        return self._candidate(document_version_id, "BLOCKED", "RAW_LOCATOR_UNSUPPORTED", row)

    @staticmethod
    def _candidate(
        item_id: int,
        status: str,
        reason_code: str,
        values: dict[str, Any],
    ) -> MigrationCandidate:
        return MigrationCandidate(item_id, status, reason_code, values)

    def backfill(
        self,
        *,
        apply: bool,
        limit: int,
        scan_limit: int = DEFAULT_SCAN_LIMIT,
    ) -> dict[str, Any]:
        """Preview or apply one bounded extraction backfill batch."""
        return self._apply(
            operation="backfill",
            apply=apply,
            limit=limit,
            scan_limit=scan_limit,
        )

    def migrate_raw_locators(
        self,
        *,
        apply: bool,
        limit: int,
        scan_limit: int = DEFAULT_SCAN_LIMIT,
    ) -> dict[str, Any]:
        """Preview or apply one bounded raw-locator migration batch."""
        return self._apply(
            operation="raw_locators",
            apply=apply,
            limit=limit,
            scan_limit=scan_limit,
        )

    def _apply(
        self,
        *,
        operation: str,
        apply: bool,
        limit: int,
        scan_limit: int,
    ) -> dict[str, Any]:
        if limit < 1 or limit > MAX_APPLY_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_APPLY_LIMIT}.")
        preflight = self.preflight(scan_limit=scan_limit)
        candidates = preflight.backfill if operation == "backfill" else preflight.raw_locators
        eligible = [item for item in candidates if item.status == "ELIGIBLE"]
        report: dict[str, Any] = {
            "schema_version": 1,
            "operation": operation,
            "mode": "APPLY" if apply else "DRY_RUN",
            "preflight_status": preflight.as_dict()["status"],
            "eligible_count": len(eligible),
            "selected_count": min(limit, len(eligible)),
            "results": [],
        }
        if not apply:
            report["status"] = "DRY_RUN"
            return report
        relevant_blockers = [item for item in candidates if item.status == "BLOCKED"]
        if preflight.truncated or relevant_blockers:
            report["status"] = "BLOCKED"
            report["reason_code"] = (
                "PREFLIGHT_TRUNCATED" if preflight.truncated else "PREFLIGHT_BLOCKED"
            )
            return report
        if operation == "backfill" and self._write_store is None:
            raise ValueError("A write-capable managed store is required for backfill.")
        failures = 0
        for candidate in eligible[:limit]:
            try:
                if operation == "backfill":
                    result = self._backfill_one(candidate)
                else:
                    result = self._migrate_raw_locator_one(candidate)
            except (ManagedStoreError, OSError, RuntimeError, ValueError, TypeError):
                failures += 1
                result = {
                    "item_id": candidate.item_id,
                    "outcome": "FAILED",
                    "reason_code": f"{operation.upper()}_ITEM_FAILED",
                }
            report["results"].append(result)
        report["status"] = "FAILED" if failures else "COMPLETED"
        report["failure_count"] = failures
        return report

    def _backfill_one(self, candidate: MigrationCandidate) -> dict[str, Any]:
        row = candidate.values
        text = str(row["extracted_text"])
        payload = text.encode("utf-8")
        identity = ManagedObjectIdentity(str(row["text_sha256"]), len(payload))
        if candidate.reason_code == "BACKFILL_RELINK_REQUIRED":
            storage_key = str(row["primary_storage_key"])
        else:
            assert self._write_store is not None
            storage_key = self._write_store.put_bytes(payload, identity).storage_key
        envelope = json.dumps(
            {
                "schema_version": 1,
                "set_kind": "SINGLE",
                "members": [
                    {
                        "role": "PRIMARY",
                        "media_type": CANONICAL_MARKDOWN_MEDIA,
                        "content_sha256": identity.sha256,
                        "storage_key": storage_key,
                        "byte_size": identity.byte_size,
                        "logical_name": "primary.md",
                        "ordinal": 1,
                        "metadata": None,
                    }
                ],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        return self._repository.backfill_extraction(
            extraction_id=candidate.item_id,
            output_set_json=envelope,
        )

    def _migrate_raw_locator_one(
        self,
        candidate: MigrationCandidate,
    ) -> dict[str, Any]:
        row = candidate.values
        return self._repository.migrate_raw_locator(
            document_version_id=candidate.item_id,
            expected_locator=str(row["content_uri"]),
            expected_sha256=str(row["content_sha256"]),
        )
