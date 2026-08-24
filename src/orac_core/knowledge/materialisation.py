"""Authorised materialisation of bounded normalised knowledge content."""

# Author: Clive Bostock
# Date: 13-Aug-2026
# Description: Resolves controlled knowledge identities and safely materialises verified text.

from __future__ import annotations

import csv
from dataclasses import dataclass, field, replace
import hashlib
import io
import json
import re
import time
from types import MappingProxyType
from typing import Any, Iterator, Mapping, Sequence
import uuid

from .managed_store import (
    KnowledgeManagedStore,
    ManagedObjectIdentity,
    ManagedStoreError,
)
from .repository import KnowledgeRetrievalRepository
from .scope import KnowledgeScope

_TARGET_TYPES = frozenset(
    {"DOCUMENT", "DOCUMENT_VERSION", "EXTRACTION", "ARTEFACT", "CHUNK_SET"}
)
_SELECTION_TYPES = frozenset(
    {
        "COMPLETE",
        "MEMBERS",
        "MEMBER_RANGE",
        "TEXT_RANGE",
        "CHUNK_RANGE",
        "CHUNK_CONTEXT",
        "SECTION_RANGE",
        "TABLE_RANGE",
    }
)
_MEDIA_TYPES = frozenset(
    {
        "text/markdown; charset=utf-8",
        "text/csv; charset=utf-8",
        "text/plain; charset=utf-8",
        "application/json",
    }
)
_A1_RANGE = re.compile(r"^([A-Z]+)([1-9][0-9]*):([A-Z]+)([1-9][0-9]*)$")


@dataclass(frozen=True, slots=True)
class KnowledgeMaterialisationRequest:
    """One controlled metadata or normalised-content retrieval request."""

    operation: str
    target_type: str
    target_id: int
    selection_type: str = "COMPLETE"
    selection: Mapping[str, Any] = field(default_factory=dict)
    include_raw_metadata: bool = False
    retrieval_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        """Canonicalise and validate the caller-controlled request envelope."""
        operation = str(self.operation).strip().upper()
        target_type = str(self.target_type).strip().upper()
        selection_type = str(self.selection_type).strip().upper()
        try:
            canonical_uuid = str(uuid.UUID(str(self.retrieval_id)))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("retrieval_id must be a canonical UUID") from exc
        if operation not in {"METADATA", "CONTENT"}:
            raise ValueError("operation must be METADATA or CONTENT")
        if target_type not in _TARGET_TYPES or int(self.target_id) <= 0:
            raise ValueError("target must use a supported type and positive identity")
        if selection_type not in _SELECTION_TYPES:
            raise ValueError("selection_type is unsupported")
        if target_type == "CHUNK_SET" and selection_type not in {
            "CHUNK_RANGE", "CHUNK_CONTEXT", "SECTION_RANGE"
        }:
            raise ValueError("CHUNK_SET targets require a bounded chunk selection")
        if selection_type in {"CHUNK_RANGE", "CHUNK_CONTEXT", "SECTION_RANGE"} and target_type != "CHUNK_SET":
            raise ValueError("chunk and section ranges require a CHUNK_SET target")
        if selection_type in {"TEXT_RANGE", "TABLE_RANGE"} and target_type != "ARTEFACT":
            raise ValueError("text and table ranges require an ARTEFACT target")
        if selection_type in {"MEMBERS", "MEMBER_RANGE"} and target_type not in {
            "DOCUMENT", "DOCUMENT_VERSION", "EXTRACTION"
        }:
            raise ValueError("member selection requires a document or extraction target")
        if not isinstance(self.selection, Mapping):
            raise ValueError("selection must be a mapping")
        object.__setattr__(self, "operation", operation)
        object.__setattr__(self, "target_type", target_type)
        object.__setattr__(self, "target_id", int(self.target_id))
        object.__setattr__(self, "selection_type", selection_type)
        object.__setattr__(self, "selection", MappingProxyType(dict(self.selection)))
        object.__setattr__(self, "retrieval_id", canonical_uuid)

    def to_json(self) -> str:
        """Return the bounded schema-versioned database request envelope."""
        payload = {
            "schema_version": 1,
            "operation": self.operation,
            "target": {"type": self.target_type, "id": self.target_id},
            "selection": {"type": self.selection_type, **dict(self.selection)},
            "include_raw_metadata": self.include_raw_metadata,
        }
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        if len(encoded.encode("utf-8")) > 65536:
            raise ValueError("retrieval request exceeds 64 KiB")
        return encoded


@dataclass(frozen=True, slots=True)
class KnowledgeRetrievedPart:
    """One verified result part and its public lineage metadata."""

    content: bytes
    provenance: Mapping[str, Any]
    verification: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class KnowledgeMaterialisationResult:
    """Stable public result for metadata or normalised content retrieval."""

    retrieval_id: str
    status: str
    reason_code: str
    operation: str
    scope: KnowledgeScope
    target_type: str
    target_id: int
    metadata: Mapping[str, Any] = field(default_factory=dict)
    members: tuple[Mapping[str, Any], ...] = ()
    chunks: tuple[Mapping[str, Any], ...] = ()
    verification: tuple[Mapping[str, Any], ...] = ()


class KnowledgeRetrievalStream:
    """Context-managed bounded response stream with terminal audit recording."""

    def __init__(
        self,
        *,
        result: KnowledgeMaterialisationResult,
        parts: Sequence[KnowledgeRetrievedPart],
        repository: KnowledgeRetrievalRepository,
        started_at: float,
        block_size: int,
    ) -> None:
        """Initialise an already verified, bounded stream."""
        self.result = result
        self.parts = tuple(parts)
        self._repository = repository
        self._started_at = started_at
        self._block_size = block_size
        self._closed = False
        self._completed = False
        self._iteration_started = False
        self._returned_byte_size = 0
        self._returned_digest = hashlib.sha256()

    def __enter__(self) -> "KnowledgeRetrievalStream":
        """Return this stream."""
        return self

    def iter_bytes(self) -> Iterator[bytes]:
        """Yield verified content in bounded blocks."""
        if self._iteration_started:
            raise RuntimeError("retrieval stream may be consumed only once")
        self._iteration_started = True
        for part in self.parts:
            for offset in range(0, len(part.content), self._block_size):
                block = part.content[offset : offset + self._block_size]
                self._returned_byte_size += len(block)
                self._returned_digest.update(block)
                yield block
        self._completed = True

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        """Record the terminal outcome without persisting content."""
        if self._closed or self.result.status != "APPROVED":
            return
        self._closed = True
        outcome = "FAILED" if exc_type is not None else (
            "COMPLETED" if self._completed else "CANCELLED"
        )
        reason = {
            "FAILED": "RETRIEVAL_INTERNAL_ERROR",
            "COMPLETED": "RETRIEVAL_CONTENT_RETURNED",
            "CANCELLED": "RETRIEVAL_CANCELLED",
        }[outcome]
        self._repository.record_outcome(
            retrieval_id=self.result.retrieval_id,
            outcome_code=outcome,
            reason_code=reason,
            returned_byte_size=self._returned_byte_size,
            returned_sha256=self._returned_digest.hexdigest(),
            member_count=len(self.parts),
            chunk_count=len(self.result.chunks),
            duration_ms=max(0, int((time.monotonic() - self._started_at) * 1000)),
        )


class KnowledgeMaterialisationService:
    """Authorise, verify, bound, and expose normalised knowledge content."""

    def __init__(
        self,
        *,
        managed_store: KnowledgeManagedStore,
        repository: KnowledgeRetrievalRepository | None = None,
        max_metadata_members: int = 256,
        max_selected_members: int = 32,
        max_selected_chunks: int = 64,
        max_table_rows: int = 10000,
        max_member_source_bytes: int = 8 * 1024 * 1024,
        max_aggregate_source_bytes: int = 16 * 1024 * 1024,
        max_emitted_bytes: int = 4 * 1024 * 1024,
        block_size: int = 1024 * 1024,
    ) -> None:
        """Initialise retrieval dependencies and immutable safety limits."""
        self._store = managed_store
        self._repository = repository or KnowledgeRetrievalRepository()
        self._max_metadata_members = min(int(max_metadata_members), 256)
        self._max_selected_members = min(int(max_selected_members), 32)
        self._max_selected_chunks = min(int(max_selected_chunks), 64)
        self._max_table_rows = min(int(max_table_rows), 10000)
        self._max_member_source_bytes = min(
            int(max_member_source_bytes), 8 * 1024 * 1024
        )
        self._max_aggregate_source_bytes = min(
            int(max_aggregate_source_bytes), 16 * 1024 * 1024
        )
        self._max_emitted_bytes = min(int(max_emitted_bytes), 4 * 1024 * 1024)
        self._block_size = min(max(int(block_size), 1), 1024 * 1024)

    def describe(
        self,
        request: KnowledgeMaterialisationRequest,
        *,
        principal_username: str,
        scope: KnowledgeScope,
    ) -> KnowledgeMaterialisationResult:
        """Return authorised metadata without materialising managed bytes."""
        if request.operation != "METADATA":
            raise ValueError("describe requires a METADATA request")
        started_at = time.monotonic()
        resolution, rows = self._resolve(request, principal_username, scope)
        result = self._public_result(request, scope, resolution, rows)
        if result.status == "APPROVED":
            self._repository.record_outcome(
                retrieval_id=request.retrieval_id,
                outcome_code="COMPLETED",
                reason_code="RETRIEVAL_METADATA_RETURNED",
                member_count=len(result.members),
                duration_ms=max(0, int((time.monotonic() - started_at) * 1000)),
            )
            return replace(
                result,
                status="COMPLETED",
                reason_code="RETRIEVAL_METADATA_RETURNED",
            )
        return result

    def open_content(
        self,
        request: KnowledgeMaterialisationRequest,
        *,
        principal_username: str,
        scope: KnowledgeScope,
    ) -> KnowledgeRetrievalStream:
        """Return a context-managed stream over verified bounded content."""
        if request.operation != "CONTENT":
            raise ValueError("open_content requires a CONTENT request")
        started_at = time.monotonic()
        resolution, rows = self._resolve(request, principal_username, scope)
        public_result = self._public_result(request, scope, resolution, rows)
        if public_result.status != "APPROVED":
            return KnowledgeRetrievalStream(
                result=public_result,
                parts=(),
                repository=self._repository,
                started_at=started_at,
                block_size=self._block_size,
            )
        try:
            selected = self._select_rows(request, rows)
            parts = self._materialise(request, selected)
        except (ValueError, UnicodeError, csv.Error, ManagedStoreError) as exc:
            reason = _safe_materialisation_reason(exc)
            self._repository.record_outcome(
                retrieval_id=request.retrieval_id,
                outcome_code="FAILED",
                reason_code=reason,
                duration_ms=max(0, int((time.monotonic() - started_at) * 1000)),
            )
            failed = KnowledgeMaterialisationResult(
                retrieval_id=request.retrieval_id,
                status="FAILED",
                reason_code=reason,
                operation=request.operation,
                scope=scope,
                target_type=request.target_type,
                target_id=request.target_id,
            )
            return KnowledgeRetrievalStream(
                result=failed,
                parts=(),
                repository=self._repository,
                started_at=started_at,
                block_size=self._block_size,
            )
        verification = tuple(part.verification for part in parts)
        approved = KnowledgeMaterialisationResult(
            retrieval_id=public_result.retrieval_id,
            status="APPROVED",
            reason_code="RETRIEVAL_APPROVED",
            operation=public_result.operation,
            scope=scope,
            target_type=public_result.target_type,
            target_id=public_result.target_id,
            metadata=public_result.metadata,
            members=tuple(part.provenance for part in parts),
            chunks=public_result.chunks,
            verification=verification,
        )
        return KnowledgeRetrievalStream(
            result=approved,
            parts=parts,
            repository=self._repository,
            started_at=started_at,
            block_size=self._block_size,
        )

    def _resolve(
        self,
        request: KnowledgeMaterialisationRequest,
        principal_username: str,
        scope: KnowledgeScope,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Resolve a request through the mandatory database security boundary."""
        if not str(principal_username).strip():
            raise ValueError("principal_username is required")
        return self._repository.resolve_request(
            retrieval_id=request.retrieval_id,
            principal_username=str(principal_username).strip(),
            target_scope_type=scope.scope_type,
            target_scope_key=scope.scope_key,
            request_json=request.to_json(),
        )

    def _public_result(
        self,
        request: KnowledgeMaterialisationRequest,
        scope: KnowledgeScope,
        resolution: Mapping[str, Any],
        rows: Sequence[Mapping[str, Any]],
    ) -> KnowledgeMaterialisationResult:
        """Strip internal locators and build stable public provenance."""
        status = str(resolution.get("status") or "FAILED")
        reason = str(resolution.get("reason_code") or "RETRIEVAL_INTERNAL_ERROR")
        if status != "APPROVED":
            return KnowledgeMaterialisationResult(
                request.retrieval_id, status, reason, request.operation, scope,
                request.target_type, request.target_id
            )
        if len(rows) > self._max_metadata_members:
            raise ValueError("RETRIEVAL_LIMIT_EXCEEDED")
        members = tuple(_public_member(row, request.include_raw_metadata) for row in rows)
        chunks = tuple(_public_chunk(row) for row in rows if row.get("chunk_id") is not None)
        first = rows[0] if rows else {}
        metadata = {
            "document_id": first.get("document_id"),
            "document_title": first.get("document_title"),
            "document_version_id": first.get("document_version_id"),
            "extraction_id": first.get("extraction_id"),
            "classification_codes": _classification_codes(
                first.get("classification_tags_json")
            ),
            "legacy_provenance": (
                {
                    "source_kind": "LEGACY_EXTRACTION_CLOB",
                    "source_artefact_id": None,
                    "artefact_role": None,
                    "logical_member_name": None,
                }
                if rows and all(row.get("artefact_id") is None for row in rows)
                else None
            ),
        }
        return KnowledgeMaterialisationResult(
            request.retrieval_id, status, reason, request.operation, scope,
            request.target_type, request.target_id,
            MappingProxyType(metadata), members, chunks
        )

    def _select_rows(
        self,
        request: KnowledgeMaterialisationRequest,
        rows: Sequence[Mapping[str, Any]],
    ) -> list[Mapping[str, Any]]:
        """Apply identity-based selection rules without accepting locators."""
        selection = request.selection
        if request.selection_type == "COMPLETE":
            candidates = [
                row for row in rows
                if row.get("artefact_role_code") in {"PRIMARY", "MANIFEST"}
            ]
            if not candidates and rows and rows[0].get("artefact_id") is None:
                candidates = [rows[0]]
            if len(candidates) != 1:
                raise ValueError("RETRIEVAL_REPRESENTATION_UNAVAILABLE")
            return candidates
        if request.selection_type == "MEMBERS":
            ids = _positive_id_list(selection.get("artefact_ids"))
            if len(ids) > self._max_selected_members:
                raise ValueError("RETRIEVAL_LIMIT_EXCEEDED")
            selected = [row for row in rows if row.get("artefact_id") in ids]
            if {row.get("artefact_id") for row in selected} != set(ids):
                raise ValueError("RETRIEVAL_TARGET_NOT_FOUND")
            return selected
        if request.selection_type == "MEMBER_RANGE":
            first_id = _positive_int(selection.get("first_artefact_id"))
            last_id = _positive_int(selection.get("last_artefact_id"))
            by_id = {int(row["artefact_id"]): row for row in rows if row.get("artefact_id")}
            if first_id not in by_id or last_id not in by_id:
                raise ValueError("RETRIEVAL_TARGET_NOT_FOUND")
            start = int(by_id[first_id]["member_ordinal"])
            end = int(by_id[last_id]["member_ordinal"])
            if end < start:
                raise ValueError("RETRIEVAL_RANGE_INVALID")
            selected = [
                row for row in rows
                if row.get("member_ordinal") is not None
                and start <= int(row["member_ordinal"]) <= end
            ]
            if len(selected) != end - start + 1 or len(selected) > self._max_selected_members:
                raise ValueError("RETRIEVAL_LIMIT_EXCEEDED")
            return selected
        if request.selection_type in {"TEXT_RANGE", "TABLE_RANGE"}:
            artefact_id = _positive_int(selection.get("artefact_id"))
            selected = [row for row in rows if row.get("artefact_id") == artefact_id]
            if len(selected) != 1:
                raise ValueError("RETRIEVAL_TARGET_NOT_FOUND")
            return selected
        if request.selection_type in {"CHUNK_RANGE", "CHUNK_CONTEXT", "SECTION_RANGE"}:
            if request.selection_type == "CHUNK_CONTEXT":
                first_id = _positive_int(selection.get("first_anchor_chunk_id"))
                last_id = _positive_int(selection.get("last_anchor_chunk_id"))
                context_before = _bounded_context(selection.get("context_before"))
                context_after = _bounded_context(selection.get("context_after"))
            else:
                first_id = _positive_int(selection.get("first_chunk_id"))
                last_id = _positive_int(selection.get("last_chunk_id"))
                context_before = 0
                context_after = 0
            by_id = {int(row["chunk_id"]): row for row in rows if row.get("chunk_id")}
            if first_id not in by_id or last_id not in by_id:
                raise ValueError("RETRIEVAL_TARGET_NOT_FOUND")
            start = max(
                min(int(row["chunk_no"]) for row in by_id.values()),
                int(by_id[first_id]["chunk_no"]) - context_before,
            )
            end = min(
                max(int(row["chunk_no"]) for row in by_id.values()),
                int(by_id[last_id]["chunk_no"]) + context_after,
            )
            chunk_set_id = int(by_id[first_id]["chunk_set_id"])
            if end < start or int(by_id[last_id]["chunk_set_id"]) != chunk_set_id:
                raise ValueError("RETRIEVAL_RANGE_INVALID")
            selected = [
                row for row in rows
                if int(row.get("chunk_set_id") or -1) == chunk_set_id
                and start <= int(row.get("chunk_no") or -1) <= end
            ]
            if len(selected) != end - start + 1 or len(selected) > self._max_selected_chunks:
                raise ValueError("RETRIEVAL_LIMIT_EXCEEDED")
            return selected
        raise ValueError("RETRIEVAL_REQUEST_INVALID")

    def _materialise(
        self,
        request: KnowledgeMaterialisationRequest,
        rows: Sequence[Mapping[str, Any]],
    ) -> tuple[KnowledgeRetrievedPart, ...]:
        """Verify complete sources and produce bounded selection bytes."""
        registered_sizes = [int(row.get("artefact_byte_size") or 0) for row in rows]
        if any(size > self._max_member_source_bytes for size in registered_sizes):
            raise ValueError("RETRIEVAL_LIMIT_EXCEEDED")
        if sum(registered_sizes) > self._max_aggregate_source_bytes:
            raise ValueError("RETRIEVAL_LIMIT_EXCEEDED")
        if request.selection_type == "CHUNK_RANGE":
            parts = tuple(self._chunk_part(row) for row in rows)
        elif request.selection_type in {"CHUNK_CONTEXT", "SECTION_RANGE"}:
            parts = (self._section_part(rows),)
        else:
            parts = tuple(self._member_part(request, row) for row in rows)
        observed_source_bytes = sum(
            int(part.verification.get("observed_byte_size") or 0)
            for part in parts
        )
        if observed_source_bytes > self._max_aggregate_source_bytes:
            raise ValueError("RETRIEVAL_LIMIT_EXCEEDED")
        if sum(len(part.content) for part in parts) > self._max_emitted_bytes:
            raise ValueError("RETRIEVAL_LIMIT_EXCEEDED")
        return parts

    def _source_text(self, row: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
        """Read and verify a managed member or legacy extraction CLOB."""
        artefact_id = row.get("artefact_id")
        if artefact_id is None:
            text = row.get("legacy_extracted_text")
            if not isinstance(text, str):
                raise ValueError("RETRIEVAL_LEGACY_CONTENT_UNAVAILABLE")
            payload = text.encode("utf-8")
            if len(payload) > self._max_member_source_bytes:
                raise ValueError("RETRIEVAL_LIMIT_EXCEEDED")
            expected = str(row.get("normalised_text_sha256") or "")
            observed = hashlib.sha256(payload).hexdigest()
            if observed != expected:
                raise ValueError("RETRIEVAL_OBJECT_CORRUPT")
            return text, {
                "storage_kind": "LEGACY_CLOB",
                "status": "VERIFIED_CLOB_HASH",
                "expected_sha256": expected,
                "expected_byte_size": len(payload),
                "observed_sha256": observed,
                "observed_byte_size": len(payload),
            }
        media_type = str(row.get("artefact_media_type") or "")
        if media_type not in _MEDIA_TYPES:
            raise ValueError("RETRIEVAL_MEDIA_UNSUPPORTED")
        identity = ManagedObjectIdentity(
            str(row.get("artefact_content_sha256") or ""),
            int(row.get("artefact_byte_size") or -1),
        )
        chunks: list[bytes] = []
        observed_size = 0
        with self._store.open_verified(str(row.get("artefact_storage_key") or ""), identity) as stream:
            while True:
                chunk = stream.read(min(self._block_size, self._max_member_source_bytes + 1 - observed_size))
                if not chunk:
                    break
                chunks.append(chunk)
                observed_size += len(chunk)
                if observed_size > self._max_member_source_bytes:
                    break
        payload = b"".join(chunks)
        if len(payload) > self._max_member_source_bytes:
            raise ValueError("RETRIEVAL_LIMIT_EXCEEDED")
        text = payload.decode("utf-8", errors="strict")
        return text, {
            "storage_kind": "MANAGED_STORE",
            "status": "VERIFIED",
            "expected_sha256": identity.sha256,
            "expected_byte_size": identity.byte_size,
            "observed_sha256": identity.sha256,
            "observed_byte_size": len(payload),
        }

    def _member_part(
        self,
        request: KnowledgeMaterialisationRequest,
        row: Mapping[str, Any],
    ) -> KnowledgeRetrievedPart:
        """Materialise one complete or ranged member."""
        text, verification = self._source_text(row)
        if request.selection_type == "TEXT_RANGE":
            start = _nonnegative_int(request.selection.get("start_char"))
            end = _nonnegative_int(request.selection.get("end_char"))
            if end <= start or end > len(text):
                raise ValueError("RETRIEVAL_RANGE_INVALID")
            text = text[start:end]
        elif request.selection_type == "TABLE_RANGE":
            if row.get("artefact_role_code") != "TABLE":
                raise ValueError("RETRIEVAL_ROLE_UNSUPPORTED")
            requested_range = str(request.selection.get("cell_range") or "")
            metadata = _json_object(row.get("artefact_metadata_json"))
            source_range = str(metadata.get("source_cell_range") or "")
            if not _range_contains(source_range, requested_range):
                raise ValueError("RETRIEVAL_RANGE_INVALID")
            text = self._select_table_range(text, requested_range)
        payload = text.encode("utf-8")
        verification = {
            **verification,
            "emitted_sha256": hashlib.sha256(payload).hexdigest(),
            "emitted_byte_size": len(payload),
        }
        provenance = _public_member(row, request.include_raw_metadata)
        provenance = {**provenance, "selection": dict(request.selection)}
        return KnowledgeRetrievedPart(payload, MappingProxyType(provenance), MappingProxyType(verification))

    def _chunk_part(self, row: Mapping[str, Any]) -> KnowledgeRetrievedPart:
        """Verify and return one stored chunk."""
        text = row.get("chunk_text")
        if not isinstance(text, str):
            raise ValueError("RETRIEVAL_REPRESENTATION_UNAVAILABLE")
        payload = text.encode("utf-8")
        expected = str(row.get("chunk_content_sha256") or "")
        observed = hashlib.sha256(payload).hexdigest()
        if expected != observed:
            raise ValueError("RETRIEVAL_OBJECT_CORRUPT")
        verification = MappingProxyType(
            {
                "storage_kind": "DATABASE_CHUNK",
                "status": "VERIFIED",
                "expected_sha256": expected,
                "observed_sha256": observed,
                "emitted_sha256": observed,
                "emitted_byte_size": len(payload),
            }
        )
        return KnowledgeRetrievedPart(payload, MappingProxyType(_public_chunk(row)), verification)

    def _section_part(
        self, rows: Sequence[Mapping[str, Any]]
    ) -> KnowledgeRetrievedPart:
        """Materialise a source span anchored by contiguous chunk identities."""
        first = rows[0]
        if any(row.get("artefact_id") != first.get("artefact_id") for row in rows):
            raise ValueError("RETRIEVAL_RANGE_INVALID")
        text, verification = self._source_text(first)
        start = min(int(row.get("span_start") or 0) for row in rows)
        end = max(int(row.get("span_end") or 0) for row in rows)
        if end <= start or end > len(text):
            raise ValueError("RETRIEVAL_RANGE_INVALID")
        payload = text[start:end].encode("utf-8")
        verification = {
            **verification,
            "emitted_sha256": hashlib.sha256(payload).hexdigest(),
            "emitted_byte_size": len(payload),
        }
        provenance = {
            **_public_member(first, include_raw_metadata=True),
            "section_span_start": start,
            "section_span_end": end,
            "first_chunk_id": rows[0].get("chunk_id"),
            "last_chunk_id": rows[-1].get("chunk_id"),
        }
        return KnowledgeRetrievedPart(payload, MappingProxyType(provenance), MappingProxyType(verification))

    def _select_table_range(self, text: str, cell_range: str) -> str:
        """Select a bounded rectangular range and return canonical CSV."""
        start_col, start_row, end_col, end_row = _parse_a1_range(cell_range)
        if end_row - start_row + 1 > self._max_table_rows:
            raise ValueError("RETRIEVAL_LIMIT_EXCEEDED")
        rows = list(csv.reader(io.StringIO(text, newline="")))
        if end_row > len(rows) or end_col < start_col:
            raise ValueError("RETRIEVAL_RANGE_INVALID")
        selected: list[list[str]] = []
        for row in rows[start_row - 1 : end_row]:
            if end_col > len(row):
                raise ValueError("RETRIEVAL_RANGE_INVALID")
            selected.append(row[start_col - 1 : end_col])
        target = io.StringIO(newline="")
        writer = csv.writer(target, lineterminator="\n")
        writer.writerows(selected)
        return target.getvalue()


def _public_member(row: Mapping[str, Any], include_raw_metadata: bool) -> Mapping[str, Any]:
    """Return an allowlisted member descriptor with explicit legacy nulls."""
    artefact_metadata = _optional_json_object(row.get("artefact_metadata_json"))
    result: dict[str, Any] = {
        "document_id": row.get("document_id"),
        "document_version_id": row.get("document_version_id"),
        "extraction_id": row.get("extraction_id"),
        "artefact_id": row.get("artefact_id"),
        "artefact_role": row.get("artefact_role_code"),
        "logical_member_name": row.get("artefact_logical_name"),
        "member_ordinal": row.get("member_ordinal"),
        "media_type": row.get("artefact_media_type") or row.get("output_mime_type"),
        "content_sha256": row.get("artefact_content_sha256") or row.get("normalised_text_sha256"),
        "byte_size": row.get("artefact_byte_size"),
        "workbook_document_version_id": row.get("document_version_id"),
        "workbook_extraction_id": row.get("extraction_id"),
        "worksheet_name": artefact_metadata.get("sheet_name"),
        "table_name": artefact_metadata.get("table_name"),
        "source_cell_range": artefact_metadata.get("source_cell_range"),
        "header_rows": artefact_metadata.get("header_rows"),
        "hidden_sheet": artefact_metadata.get("hidden_sheet"),
        "artefact_metadata": artefact_metadata or None,
        "legacy_artefact_provenance": row.get("artefact_id") is None,
    }
    if include_raw_metadata:
        result["raw_metadata"] = {
            "revision_content_sha256": row.get("revision_content_sha256"),
            "revision_byte_size": row.get("revision_byte_size"),
            "revision_mime_type": row.get("revision_mime_type"),
            "original_filename": row.get("original_filename"),
            "source_format_code": row.get("source_format_code"),
            "extractor_code": row.get("extractor_code"),
            "extractor_version": row.get("extractor_version"),
            "extractor_metadata": row.get("extractor_metadata_json"),
        }
    return MappingProxyType(result)


def _public_chunk(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return exact chunk and member provenance without chunk content."""
    chunk_metadata = _optional_json_object(row.get("chunk_metadata_json"))
    artefact_metadata = _optional_json_object(row.get("artefact_metadata_json"))
    return {
        "document_id": row.get("document_id"),
        "document_version_id": row.get("document_version_id"),
        "extraction_id": row.get("extraction_id"),
        "chunk_set_id": row.get("chunk_set_id"),
        "chunk_id": row.get("chunk_id"),
        "chunk_no": row.get("chunk_no"),
        "span_start": row.get("span_start"),
        "span_end": row.get("span_end"),
        "chunk_content_sha256": row.get("chunk_content_sha256"),
        "source_artefact_id": row.get("artefact_id") or row.get("source_artefact_id"),
        "source_artefact_role": row.get("artefact_role_code") or row.get("source_artefact_role_code"),
        "source_artefact_logical_name": row.get("artefact_logical_name") or row.get("source_artefact_logical_name"),
        "worksheet_name": artefact_metadata.get("sheet_name") or row.get("source_sheet_name"),
        "table_name": artefact_metadata.get("table_name") or row.get("source_table_name"),
        "source_member_cell_range": artefact_metadata.get("source_cell_range") or row.get("source_member_cell_range"),
        "source_header_rows": artefact_metadata.get("header_rows") or row.get("source_header_rows_json"),
        "source_hidden_sheet": artefact_metadata.get("hidden_sheet") if "hidden_sheet" in artefact_metadata else row.get("source_hidden_sheet"),
        "media_type": row.get("artefact_media_type") or row.get("output_mime_type") or "text/plain; charset=utf-8",
        "source_row_start": chunk_metadata.get("source_row_start") or row.get("source_row_start"),
        "source_row_end": chunk_metadata.get("source_row_end") or row.get("source_row_end"),
        "source_chunk_cell_range": chunk_metadata.get("source_cell_range") or row.get("source_chunk_cell_range"),
        "chunk_metadata": chunk_metadata or None,
        "legacy_artefact_provenance": (
            row.get("artefact_id") is None and row.get("source_artefact_id") is None
        ),
    }


def _safe_materialisation_reason(exc: Exception) -> str:
    """Map internal validation and store errors to stable public reasons."""
    if isinstance(exc, ManagedStoreError):
        reason = exc.reason_code
        if reason == "MANAGED_OBJECT_MISSING":
            return "RETRIEVAL_OBJECT_MISSING"
        if reason in {
            "MANAGED_OBJECT_HASH_MISMATCH",
            "MANAGED_OBJECT_SIZE_MISMATCH",
            "STORAGE_KEY_IDENTITY_MISMATCH",
        }:
            return "RETRIEVAL_OBJECT_CORRUPT"
        if reason in {
            "INVALID_STORAGE_KEY",
            "MANAGED_OBJECT_SYMLINK",
            "MANAGED_OBJECT_NOT_REGULAR",
            "UNSAFE_STORE_LAYOUT",
            "UNSAFE_MANAGED_PERMISSIONS",
            "STORE_ROOT_IDENTITY_CHANGED",
        }:
            return "RETRIEVAL_OBJECT_UNSAFE"
        return "RETRIEVAL_STORE_UNAVAILABLE"
    if isinstance(exc, UnicodeError):
        return "RETRIEVAL_DECODE_FAILED"
    message = str(exc)
    if message.startswith("RETRIEVAL_"):
        return message
    return "RETRIEVAL_REQUEST_INVALID"


def _positive_id_list(value: Any) -> tuple[int, ...]:
    """Validate a unique sequence of positive controlled identities."""
    if not isinstance(value, list):
        raise ValueError("RETRIEVAL_REQUEST_INVALID")
    result = tuple(_positive_int(item) for item in value)
    if not result or len(result) != len(set(result)):
        raise ValueError("RETRIEVAL_DUPLICATE_ID")
    return result


def _positive_int(value: Any) -> int:
    """Return a positive integer or reject booleans and coercive strings."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("RETRIEVAL_REQUEST_INVALID")
    return value


def _nonnegative_int(value: Any) -> int:
    """Return a non-negative integer without coercion."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("RETRIEVAL_REQUEST_INVALID")
    return value


def _bounded_context(value: Any) -> int:
    """Return a controlled surrounding chunk count."""
    result = _nonnegative_int(value)
    if result > 8:
        raise ValueError("RETRIEVAL_LIMIT_EXCEEDED")
    return result


def _parse_a1_range(value: str) -> tuple[int, int, int, int]:
    """Parse a canonical uppercase A1 rectangle."""
    match = _A1_RANGE.fullmatch(value)
    if match is None:
        raise ValueError("RETRIEVAL_RANGE_INVALID")
    start_col = _column_number(match.group(1))
    end_col = _column_number(match.group(3))
    start_row = int(match.group(2))
    end_row = int(match.group(4))
    if end_col < start_col or end_row < start_row:
        raise ValueError("RETRIEVAL_RANGE_INVALID")
    return start_col, start_row, end_col, end_row


def _column_number(label: str) -> int:
    """Convert an uppercase spreadsheet column label to one-based index."""
    result = 0
    for character in label:
        result = result * 26 + ord(character) - ord("A") + 1
    return result


def _range_contains(container: str, requested: str) -> bool:
    """Return whether one valid A1 rectangle fully contains another."""
    try:
        c_start_col, c_start_row, c_end_col, c_end_row = _parse_a1_range(container)
        r_start_col, r_start_row, r_end_col, r_end_row = _parse_a1_range(requested)
    except ValueError:
        return False
    return (
        c_start_col <= r_start_col <= r_end_col <= c_end_col
        and c_start_row <= r_start_row <= r_end_row <= c_end_row
    )


def _json_object(value: Any) -> dict[str, Any]:
    """Materialise a JSON object from native Oracle JSON or text."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("RETRIEVAL_REQUEST_INVALID")


def _optional_json_object(value: Any) -> dict[str, Any]:
    """Return a JSON object or an empty mapping for a database null."""
    return {} if value is None else _json_object(value)


def _classification_codes(value: Any) -> tuple[str, ...]:
    """Return controlled document classification codes from database JSON."""
    if value is None:
        return ()
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, list):
        raise ValueError("RETRIEVAL_REQUEST_INVALID")
    result = tuple(str(item) for item in parsed)
    if any(not re.fullmatch(r"[A-Z0-9_]{1,100}", item) for item in result):
        raise ValueError("RETRIEVAL_REQUEST_INVALID")
    return result
