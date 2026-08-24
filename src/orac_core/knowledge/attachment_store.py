"""Own private, opaque, single-use binary attachment objects."""

# Author: Clive Bostock
# Date: 23-Aug-2026
# Description: Provides descriptor-oriented attachment binding and cleanup.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import threading
import time
from typing import BinaryIO, Protocol
import uuid

ATTACHMENT_DIRECTORY_MODE = 0o700
ATTACHMENT_FILE_MODE = 0o600
ATTACHMENT_NAME_PATTERN = re.compile(r"^att-([A-Za-z0-9_-]{43})$")
ALLOCATION_NAME_PATTERN = re.compile(r"^\.alloc-[0-9a-f]{32}$")
ATTACHMENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
METADATA_FILE_NAME = "metadata.json"
PAYLOAD_FILE_NAME = "payload"
MAX_METADATA_BYTES = 64 * 1024
READ_BLOCK_SIZE = 1024 * 1024


class AttachmentStoreError(RuntimeError):
    """Raised when an attachment lifecycle operation fails safely."""

    def __init__(self, reason_code: str, message: str) -> None:
        """Initialise a stable reason-coded attachment error."""
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class AttachmentBinding:
    """Content-free binding that makes one opaque handle non-transferable."""

    request_id: str
    request_fingerprint: str
    principal_fingerprint: str
    route_fingerprint: str
    policy_fingerprint: str
    source_fingerprint: str
    selection_fingerprint: str
    correlation_id: str
    audit_id: str
    policy_result_id: str
    route_result_id: str
    route_kind: str
    route_identity: str
    processor_code: str
    processor_profile: str
    processor_version: str
    verified_representation: str
    mime_decision: str
    limits_fingerprint: str
    locality_decision_id: str
    classification_decision_id: str
    consent_decision_id: str
    minimisation_decision_id: str
    created_at: datetime
    expires_at: datetime
    cleanup_deadline: datetime

    def __post_init__(self) -> None:
        """Validate identifiers, fingerprints, and bounded lifetime."""
        for name in (
            "request_id",
            "correlation_id",
            "audit_id",
            "policy_result_id",
            "route_result_id",
            "locality_decision_id",
            "classification_decision_id",
            "consent_decision_id",
            "minimisation_decision_id",
        ):
            _canonical_uuid(getattr(self, name), field_name=name)
        for name in (
            "request_fingerprint",
            "principal_fingerprint",
            "route_fingerprint",
            "policy_fingerprint",
            "source_fingerprint",
            "selection_fingerprint",
            "limits_fingerprint",
        ):
            _canonical_sha256(getattr(self, name), field_name=name)
        for name in (
            "route_kind",
            "route_identity",
            "processor_code",
            "processor_profile",
            "processor_version",
            "verified_representation",
            "mime_decision",
        ):
            value = str(getattr(self, name)).strip()
            if not value or len(value) > 128 or any(ord(char) < 32 for char in value):
                raise ValueError(f"{name} is invalid")
        created_at = _utc_datetime(self.created_at, field_name="created_at")
        expires_at = _utc_datetime(self.expires_at, field_name="expires_at")
        cleanup_deadline = _utc_datetime(
            self.cleanup_deadline,
            field_name="cleanup_deadline",
        )
        if expires_at <= created_at:
            raise ValueError("expires_at must follow created_at")
        if cleanup_deadline < expires_at:
            raise ValueError("cleanup_deadline cannot precede expires_at")


@dataclass(frozen=True, slots=True)
class AttachmentRecord:
    """Private attachment state without a physical path or managed key."""

    attachment_id: str
    binding: AttachmentBinding
    byte_size: int
    sha256: str
    state: str = "READY"
    consumed_at: datetime | None = None
    cleanup_reason: str | None = None

    def __post_init__(self) -> None:
        """Validate the safe persisted record shape."""
        if ATTACHMENT_ID_PATTERN.fullmatch(self.attachment_id) is None:
            raise ValueError("attachment_id must be opaque base64url data")
        if int(self.byte_size) < 0:
            raise ValueError("byte_size must be zero or greater")
        _canonical_sha256(self.sha256, field_name="sha256")
        if self.state not in {
            "READY",
            "CONSUMED",
            "CANCELLED",
            "EXPIRED",
            "CLEANUP_FAILED",
        }:
            raise ValueError("attachment state is unsupported")
        if self.consumed_at is not None:
            _utc_datetime(self.consumed_at, field_name="consumed_at")


@dataclass(frozen=True, slots=True)
class AttachmentRecoveryReport:
    """Bounded content-free startup reconciliation outcome."""

    inspected_entries: int
    recovered_ready: int
    cleaned_entries: int
    ambiguous_entries: int
    complete: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AttachmentWriteResult:
    """Verified result of atomically binding one private payload."""

    record: AttachmentRecord
    writer_result: object


class AttachmentWriter(Protocol):
    """Write one already approved bounded derivative to an attachment sink."""

    def __call__(self, sink: BinaryIO) -> object:
        """Write to ``sink`` and return content-free derivative evidence."""
        ...


class _BoundedAttachmentWriter:
    """Binary sink that enforces output size, cancellation, and deadline."""

    def __init__(
        self,
        raw: BinaryIO,
        *,
        max_bytes: int,
        deadline_monotonic: float,
        cancelled: Callable[[], bool],
    ) -> None:
        self._raw = raw
        self._max_bytes = int(max_bytes)
        self._deadline_monotonic = float(deadline_monotonic)
        self._cancelled = cancelled
        self.byte_size = 0
        self.digest = hashlib.sha256()

    def writable(self) -> bool:
        """Return whether the wrapped stream accepts writes."""
        return True

    def write(self, payload: bytes) -> int:
        """Write one bounded binary block."""
        if not isinstance(payload, bytes):
            raise AttachmentStoreError(
                "MAT_PROCESSOR_OUTPUT_INVALID",
                "Attachment processors must emit binary bytes.",
            )
        self._check_terminal_state()
        if self.byte_size + len(payload) > self._max_bytes:
            raise AttachmentStoreError(
                "MAT_OUTPUT_LIMIT_EXCEEDED",
                "Attachment output exceeded its approved byte limit.",
            )
        written = self._raw.write(payload)
        if written != len(payload):
            raise AttachmentStoreError(
                "MAT_ATTACHMENT_ALLOCATION_FAILED",
                "Attachment output could not be written completely.",
            )
        self.byte_size += written
        self.digest.update(payload)
        return written

    def flush(self) -> None:
        """Flush the wrapped stream after a terminal-state check."""
        self._check_terminal_state()
        self._raw.flush()

    def _check_terminal_state(self) -> None:
        if self._cancelled():
            raise AttachmentStoreError(
                "MAT_CANCELLED",
                "Attachment materialisation was cancelled.",
            )
        if time.monotonic() >= self._deadline_monotonic:
            raise AttachmentStoreError(
                "MAT_ELAPSED_TIME_EXPIRED",
                "Attachment materialisation exceeded its elapsed-time limit.",
            )


class _GuardedAttachmentReader:
    """Read-only descriptor wrapper that enforces terminal handle state."""

    def __init__(
        self,
        raw: BinaryIO,
        *,
        expires_at: datetime,
        cancelled: Callable[[], bool],
    ) -> None:
        self._raw = raw
        self._expires_at = expires_at
        self._cancelled = cancelled

    def read(self, size: int = -1) -> bytes:
        """Read bytes while the consumed lease remains current."""
        if self._cancelled():
            raise AttachmentStoreError(
                "MAT_CANCELLED",
                "Attachment consumption was cancelled.",
            )
        if _now_utc() >= self._expires_at:
            raise AttachmentStoreError(
                "MAT_ATTACHMENT_EXPIRED",
                "Attachment consumption expired.",
            )
        return self._raw.read(size)

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        """Move the underlying verified descriptor position."""
        return self._raw.seek(offset, whence)

    def tell(self) -> int:
        """Return the underlying descriptor position."""
        return self._raw.tell()


class OpaqueAttachmentStore:
    """Manage private attachment objects below one fixed runtime root."""

    def __init__(
        self,
        runtime_root: Path,
        *,
        max_recovery_entries: int = 4096,
        max_recovery_elapsed_seconds: int = 10,
        stale_allocation_seconds: int = 300,
    ) -> None:
        """Initialise and validate the fixed host-owned runtime root."""
        self._configured_root = Path(runtime_root).expanduser()
        self._root = self._initialise_root(self._configured_root)
        root_stat = os.stat(self._root, follow_symlinks=False)
        self._root_device = int(root_stat.st_dev)
        self._root_inode = int(root_stat.st_ino)
        self._max_recovery_entries = _positive_int(
            max_recovery_entries,
            field_name="max_recovery_entries",
        )
        self._max_recovery_elapsed_seconds = _positive_int(
            max_recovery_elapsed_seconds,
            field_name="max_recovery_elapsed_seconds",
        )
        self._stale_allocation_seconds = _positive_int(
            stale_allocation_seconds,
            field_name="stale_allocation_seconds",
        )
        self._lock = threading.RLock()
        self._records: dict[str, AttachmentRecord] = {}
        self._request_index: dict[str, str] = {}
        self._tombstones: dict[str, str] = {}

    def bind(
        self,
        *,
        binding: AttachmentBinding,
        max_output_bytes: int,
        deadline_monotonic: float,
        cancelled: Callable[[], bool],
        writer: AttachmentWriter,
    ) -> AttachmentWriteResult:
        """Write, verify, and atomically bind one opaque private payload."""
        max_bytes = _positive_int(max_output_bytes, field_name="max_output_bytes")
        with self._lock:
            existing_id = self._request_index.get(binding.request_id)
            if existing_id is not None:
                existing = self._records.get(existing_id)
                if (
                    existing is not None
                    and existing.binding.request_fingerprint
                    == binding.request_fingerprint
                    and existing.state == "READY"
                ):
                    return AttachmentWriteResult(existing, None)
                raise AttachmentStoreError(
                    "MAT_ATTACHMENT_BINDING_CONFLICT",
                    "Attachment request identity is already bound differently.",
                )

            root_fd = self._open_root()
            allocation_name = f".alloc-{uuid.uuid4().hex}"
            attachment_id = _new_attachment_id()
            final_name = f"att-{attachment_id}"
            allocation_fd = -1
            payload_fd = -1
            promoted = False
            try:
                os.mkdir(
                    allocation_name,
                    ATTACHMENT_DIRECTORY_MODE,
                    dir_fd=root_fd,
                )
                allocation_fd = self._open_child_directory(
                    root_fd,
                    allocation_name,
                )
                os.fchmod(allocation_fd, ATTACHMENT_DIRECTORY_MODE)
                payload_fd = os.open(
                    PAYLOAD_FILE_NAME,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    ATTACHMENT_FILE_MODE,
                    dir_fd=allocation_fd,
                )
                os.fchmod(payload_fd, ATTACHMENT_FILE_MODE)
                with os.fdopen(payload_fd, "wb", closefd=True) as payload_stream:
                    payload_fd = -1
                    bounded_writer = _BoundedAttachmentWriter(
                        payload_stream,
                        max_bytes=max_bytes,
                        deadline_monotonic=deadline_monotonic,
                        cancelled=cancelled,
                    )
                    writer_result = writer(bounded_writer)  # type: ignore[arg-type]
                    bounded_writer.flush()
                    os.fsync(payload_stream.fileno())
                record = AttachmentRecord(
                    attachment_id=attachment_id,
                    binding=binding,
                    byte_size=bounded_writer.byte_size,
                    sha256=bounded_writer.digest.hexdigest(),
                )
                self._write_metadata(allocation_fd, record)
                os.fsync(allocation_fd)
                try:
                    os.stat(final_name, dir_fd=root_fd, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    raise AttachmentStoreError(
                        "MAT_ATTACHMENT_BINDING_FAILED",
                        "Opaque attachment identity collision.",
                    )
                os.rename(
                    allocation_name,
                    final_name,
                    src_dir_fd=root_fd,
                    dst_dir_fd=root_fd,
                )
                promoted = True
                os.fsync(root_fd)
            except AttachmentStoreError:
                raise
            except OSError as exc:
                raise AttachmentStoreError(
                    "MAT_ATTACHMENT_ALLOCATION_FAILED",
                    "Private attachment allocation failed.",
                ) from exc
            finally:
                if payload_fd >= 0:
                    os.close(payload_fd)
                if allocation_fd >= 0:
                    os.close(allocation_fd)
                if not promoted:
                    self._remove_allocation(root_fd, allocation_name)
                os.close(root_fd)
            self._records[attachment_id] = record
            self._request_index[binding.request_id] = attachment_id
            return AttachmentWriteResult(record, writer_result)

    @contextmanager
    def open_once(
        self,
        attachment_id: str,
        *,
        binding: AttachmentBinding,
        cancelled: Callable[[], bool],
        now: datetime | None = None,
    ) -> Iterator[BinaryIO]:
        """Yield one verified descriptor once, then clean it up terminally."""
        current = _now_utc() if now is None else _utc_datetime(now, field_name="now")
        payload_stream: BinaryIO | None = None
        terminal_reason = "MAT_ATTACHMENT_CONSUMED"
        with self._lock:
            record = self._record_for_use(attachment_id, binding)
            if cancelled():
                terminal_reason = "MAT_CANCELLED"
                self._mark_terminal(record, state="CANCELLED", reason=terminal_reason)
                self.cleanup(attachment_id, reason_code=terminal_reason)
                raise AttachmentStoreError(
                    terminal_reason,
                    "Attachment consumption was cancelled.",
                )
            if current >= record.binding.expires_at:
                terminal_reason = "MAT_ATTACHMENT_EXPIRED"
                self._mark_terminal(record, state="EXPIRED", reason=terminal_reason)
                self.cleanup(attachment_id, reason_code=terminal_reason)
                raise AttachmentStoreError(
                    terminal_reason,
                    "Attachment handle expired.",
                )
            directory_fd = self._open_attachment_directory(attachment_id)
            payload_fd = -1
            try:
                payload_fd = os.open(
                    PAYLOAD_FILE_NAME,
                    os.O_RDONLY | os.O_NOFOLLOW,
                    dir_fd=directory_fd,
                )
                try:
                    self._verify_payload_descriptor(payload_fd, record)
                except AttachmentStoreError as exc:
                    self._mark_terminal(
                        record,
                        state="CLEANUP_FAILED",
                        reason=exc.reason_code,
                    )
                    raise
                consumed_at = current
                consumed = replace(
                    record,
                    state="CONSUMED",
                    consumed_at=consumed_at,
                    cleanup_reason="MAT_ATTACHMENT_CONSUMED",
                )
                self._write_metadata(directory_fd, consumed)
                os.fsync(directory_fd)
                self._records[attachment_id] = consumed
                payload_stream = os.fdopen(
                    payload_fd,
                    "rb",
                    buffering=0,
                    closefd=True,
                )
                payload_fd = -1
            finally:
                if payload_fd >= 0:
                    os.close(payload_fd)
                os.close(directory_fd)
        try:
            yield _GuardedAttachmentReader(  # type: ignore[misc]
                payload_stream,
                expires_at=record.binding.expires_at,
                cancelled=cancelled,
            )
        except AttachmentStoreError as exc:
            terminal_reason = exc.reason_code
            raise
        finally:
            if payload_stream is not None:
                payload_stream.close()
            self.cleanup(attachment_id, reason_code=terminal_reason)

    def status(self, attachment_id: str) -> AttachmentRecord | None:
        """Return content-free state for a known live attachment."""
        _validate_attachment_id(attachment_id)
        with self._lock:
            return self._records.get(attachment_id)

    def cleanup(self, attachment_id: str, *, reason_code: str) -> str:
        """Idempotently remove one recognised attachment without links."""
        _validate_attachment_id(attachment_id)
        with self._lock:
            root_fd = self._open_root()
            try:
                removed = self._remove_attachment_directory(root_fd, attachment_id)
            finally:
                os.close(root_fd)
            record = self._records.pop(attachment_id, None)
            if record is not None:
                self._request_index.pop(record.binding.request_id, None)
            self._tombstones[attachment_id] = reason_code
            if len(self._tombstones) > self._max_recovery_entries:
                oldest = next(iter(self._tombstones))
                self._tombstones.pop(oldest, None)
            return "CLEANED" if removed else "ALREADY_CLEANED"

    def reconcile(self, *, now: datetime | None = None) -> AttachmentRecoveryReport:
        """Recover current handles and remove only recognised terminal entries."""
        current = _now_utc() if now is None else _utc_datetime(now, field_name="now")
        started = time.monotonic()
        inspected = 0
        recovered = 0
        cleaned = 0
        ambiguous = 0
        complete = True
        reasons: list[str] = []
        with self._lock:
            root_fd = self._open_root()
            try:
                with os.scandir(root_fd) as iterator:
                    names = sorted(entry.name for entry in iterator)
                for name in names:
                    if inspected >= self._max_recovery_entries:
                        complete = False
                        reasons.append("MAT_RECONCILIATION_ENTRY_LIMIT")
                        break
                    if time.monotonic() - started >= self._max_recovery_elapsed_seconds:
                        complete = False
                        reasons.append("MAT_RECONCILIATION_ELAPSED_TIME")
                        break
                    inspected += 1
                    if ALLOCATION_NAME_PATTERN.fullmatch(name):
                        outcome = self._reconcile_allocation(
                            root_fd,
                            name,
                            current=current,
                        )
                    elif ATTACHMENT_NAME_PATTERN.fullmatch(name):
                        outcome = self._reconcile_attachment(
                            root_fd,
                            name,
                            current=current,
                        )
                    else:
                        outcome = "AMBIGUOUS"
                    if outcome == "RECOVERED":
                        recovered += 1
                    elif outcome == "CLEANED":
                        cleaned += 1
                    else:
                        ambiguous += 1
                        if "MAT_RECONCILIATION_AMBIGUOUS" not in reasons:
                            reasons.append("MAT_RECONCILIATION_AMBIGUOUS")
            finally:
                os.close(root_fd)
        return AttachmentRecoveryReport(
            inspected_entries=inspected,
            recovered_ready=recovered,
            cleaned_entries=cleaned,
            ambiguous_entries=ambiguous,
            complete=complete and ambiguous == 0,
            reason_codes=tuple(dict.fromkeys(reasons)),
        )

    def shutdown(self) -> AttachmentRecoveryReport:
        """Clean current-process live handles during bounded service shutdown."""
        with self._lock:
            attachment_ids = tuple(self._records)
        cleaned = 0
        ambiguous = 0
        for attachment_id in attachment_ids[: self._max_recovery_entries]:
            try:
                self.cleanup(
                    attachment_id,
                    reason_code="MAT_SERVICE_SHUTDOWN",
                )
                cleaned += 1
            except AttachmentStoreError:
                ambiguous += 1
        return AttachmentRecoveryReport(
            inspected_entries=min(len(attachment_ids), self._max_recovery_entries),
            recovered_ready=0,
            cleaned_entries=cleaned,
            ambiguous_entries=ambiguous,
            complete=(
                len(attachment_ids) <= self._max_recovery_entries and ambiguous == 0
            ),
            reason_codes=(("MAT_CLEANUP_FAILED",) if ambiguous else ()),
        )

    def _record_for_use(
        self,
        attachment_id: str,
        binding: AttachmentBinding,
    ) -> AttachmentRecord:
        _validate_attachment_id(attachment_id)
        if attachment_id in self._tombstones:
            raise AttachmentStoreError(
                "MAT_ATTACHMENT_ALREADY_CONSUMED",
                "Attachment handle is no longer available.",
            )
        record = self._records.get(attachment_id)
        if record is None:
            raise AttachmentStoreError(
                "MAT_ATTACHMENT_UNKNOWN",
                "Attachment handle is unavailable.",
            )
        if record.binding != binding:
            raise AttachmentStoreError(
                "MAT_ATTACHMENT_BINDING_INVALID",
                "Attachment handle binding does not match the consumer.",
            )
        if record.state != "READY":
            raise AttachmentStoreError(
                "MAT_ATTACHMENT_ALREADY_CONSUMED",
                "Attachment handle has already reached a terminal state.",
            )
        return record

    def _mark_terminal(
        self,
        record: AttachmentRecord,
        *,
        state: str,
        reason: str,
    ) -> None:
        directory_fd = self._open_attachment_directory(record.attachment_id)
        try:
            terminal = replace(record, state=state, cleanup_reason=reason)
            self._write_metadata(directory_fd, terminal)
            os.fsync(directory_fd)
            self._records[record.attachment_id] = terminal
        finally:
            os.close(directory_fd)

    def _reconcile_allocation(
        self,
        root_fd: int,
        name: str,
        *,
        current: datetime,
    ) -> str:
        try:
            entry_stat = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
        except OSError:
            return "AMBIGUOUS"
        if not self._safe_directory_stat(entry_stat):
            return "AMBIGUOUS"
        age_seconds = max(0, current.timestamp() - entry_stat.st_mtime)
        if age_seconds < self._stale_allocation_seconds:
            return "AMBIGUOUS"
        return "CLEANED" if self._remove_allocation(root_fd, name) else "AMBIGUOUS"

    def _reconcile_attachment(
        self,
        root_fd: int,
        name: str,
        *,
        current: datetime,
    ) -> str:
        match = ATTACHMENT_NAME_PATTERN.fullmatch(name)
        if match is None:
            return "AMBIGUOUS"
        attachment_id = match.group(1)
        directory_fd = -1
        try:
            entry_stat = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
            if not self._safe_directory_stat(entry_stat):
                return "AMBIGUOUS"
            directory_fd = self._open_child_directory(root_fd, name)
            record = self._read_metadata(directory_fd)
            if record.attachment_id != attachment_id:
                return "AMBIGUOUS"
            payload_fd = os.open(
                PAYLOAD_FILE_NAME,
                os.O_RDONLY | os.O_NOFOLLOW,
                dir_fd=directory_fd,
            )
            try:
                self._verify_payload_descriptor(payload_fd, record)
            finally:
                os.close(payload_fd)
            if (
                record.state != "READY"
                or current >= record.binding.expires_at
                or current >= record.binding.cleanup_deadline
            ):
                return (
                    "CLEANED"
                    if self._remove_attachment_directory(root_fd, attachment_id)
                    else "AMBIGUOUS"
                )
            previous = self._request_index.get(record.binding.request_id)
            if previous not in {None, attachment_id}:
                return "AMBIGUOUS"
            self._records[attachment_id] = record
            self._request_index[record.binding.request_id] = attachment_id
            return "RECOVERED"
        except (AttachmentStoreError, OSError, ValueError, TypeError, KeyError):
            return "AMBIGUOUS"
        finally:
            if directory_fd >= 0:
                os.close(directory_fd)

    def _verify_payload_descriptor(
        self,
        payload_fd: int,
        record: AttachmentRecord,
    ) -> None:
        before = os.fstat(payload_fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.geteuid()
            or stat.S_IMODE(before.st_mode) != ATTACHMENT_FILE_MODE
            or before.st_nlink != 1
            or before.st_size != record.byte_size
        ):
            raise AttachmentStoreError(
                "MAT_ATTACHMENT_PERMISSION_INVALID",
                "Attachment payload identity or permissions are unsafe.",
            )
        digest = hashlib.sha256()
        while True:
            chunk = os.read(payload_fd, READ_BLOCK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
        after = os.fstat(payload_fd)
        stable_fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        if any(getattr(before, name) != getattr(after, name) for name in stable_fields):
            raise AttachmentStoreError(
                "MAT_ATTACHMENT_CHANGED",
                "Attachment payload changed while being verified.",
            )
        if digest.hexdigest() != record.sha256:
            raise AttachmentStoreError(
                "MAT_ATTACHMENT_CHANGED",
                "Attachment payload digest no longer matches its binding.",
            )
        os.lseek(payload_fd, 0, os.SEEK_SET)

    def _write_metadata(self, directory_fd: int, record: AttachmentRecord) -> None:
        payload = _record_to_json(record)
        if len(payload) > MAX_METADATA_BYTES:
            raise AttachmentStoreError(
                "MAT_ATTACHMENT_BINDING_FAILED",
                "Attachment binding metadata exceeded its fixed limit.",
            )
        temporary_name = f".metadata-{uuid.uuid4().hex}.tmp"
        metadata_fd = -1
        try:
            metadata_fd = os.open(
                temporary_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                ATTACHMENT_FILE_MODE,
                dir_fd=directory_fd,
            )
            os.fchmod(metadata_fd, ATTACHMENT_FILE_MODE)
            written = os.write(metadata_fd, payload)
            if written != len(payload):
                raise AttachmentStoreError(
                    "MAT_ATTACHMENT_BINDING_FAILED",
                    "Attachment binding metadata was not written completely.",
                )
            os.fsync(metadata_fd)
            os.close(metadata_fd)
            metadata_fd = -1
            os.rename(
                temporary_name,
                METADATA_FILE_NAME,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
            )
        finally:
            if metadata_fd >= 0:
                os.close(metadata_fd)
            try:
                os.unlink(temporary_name, dir_fd=directory_fd)
            except FileNotFoundError:
                pass

    def _read_metadata(self, directory_fd: int) -> AttachmentRecord:
        metadata_fd = os.open(
            METADATA_FILE_NAME,
            os.O_RDONLY | os.O_NOFOLLOW,
            dir_fd=directory_fd,
        )
        try:
            metadata_stat = os.fstat(metadata_fd)
            if (
                not stat.S_ISREG(metadata_stat.st_mode)
                or metadata_stat.st_uid != os.geteuid()
                or stat.S_IMODE(metadata_stat.st_mode) != ATTACHMENT_FILE_MODE
                or metadata_stat.st_nlink != 1
                or metadata_stat.st_size > MAX_METADATA_BYTES
            ):
                raise AttachmentStoreError(
                    "MAT_RECONCILIATION_AMBIGUOUS",
                    "Attachment metadata is unsafe.",
                )
            chunks: list[bytes] = []
            remaining = MAX_METADATA_BYTES + 1
            while remaining > 0:
                chunk = os.read(metadata_fd, min(remaining, READ_BLOCK_SIZE))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            payload = b"".join(chunks)
            if len(payload) > MAX_METADATA_BYTES:
                raise AttachmentStoreError(
                    "MAT_RECONCILIATION_AMBIGUOUS",
                    "Attachment metadata exceeded its fixed limit.",
                )
            metadata_after = os.fstat(metadata_fd)
            stable_fields = (
                "st_dev",
                "st_ino",
                "st_size",
                "st_mtime_ns",
                "st_ctime_ns",
            )
            if any(
                getattr(metadata_stat, name) != getattr(metadata_after, name)
                for name in stable_fields
            ):
                raise AttachmentStoreError(
                    "MAT_RECONCILIATION_AMBIGUOUS",
                    "Attachment metadata changed while being verified.",
                )
            return _record_from_json(payload)
        finally:
            os.close(metadata_fd)

    def _remove_attachment_directory(self, root_fd: int, attachment_id: str) -> bool:
        name = f"att-{attachment_id}"
        directory_fd = -1
        try:
            entry_stat = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise AttachmentStoreError(
                "MAT_CLEANUP_FAILED",
                "Attachment cleanup could not inspect the target.",
            ) from exc
        if not self._safe_directory_stat(entry_stat):
            raise AttachmentStoreError(
                "MAT_RECONCILIATION_AMBIGUOUS",
                "Attachment cleanup refused an ambiguous entry.",
            )
        try:
            directory_fd = self._open_child_directory(root_fd, name)
            with os.scandir(directory_fd) as iterator:
                entries = sorted(entry.name for entry in iterator)
            if set(entries) != {METADATA_FILE_NAME, PAYLOAD_FILE_NAME}:
                raise AttachmentStoreError(
                    "MAT_RECONCILIATION_AMBIGUOUS",
                    "Attachment cleanup refused an unrecognised layout.",
                )
            for child_name in (PAYLOAD_FILE_NAME, METADATA_FILE_NAME):
                child_stat = os.stat(
                    child_name,
                    dir_fd=directory_fd,
                    follow_symlinks=False,
                )
                if (
                    not stat.S_ISREG(child_stat.st_mode)
                    or child_stat.st_uid != os.geteuid()
                    or stat.S_IMODE(child_stat.st_mode) != ATTACHMENT_FILE_MODE
                    or child_stat.st_nlink != 1
                ):
                    raise AttachmentStoreError(
                        "MAT_RECONCILIATION_AMBIGUOUS",
                        "Attachment cleanup refused unsafe payload metadata.",
                    )
            for child_name in (PAYLOAD_FILE_NAME, METADATA_FILE_NAME):
                os.unlink(child_name, dir_fd=directory_fd)
            os.fsync(directory_fd)
        except AttachmentStoreError:
            raise
        except OSError as exc:
            raise AttachmentStoreError(
                "MAT_CLEANUP_FAILED",
                "Attachment cleanup failed.",
            ) from exc
        finally:
            if directory_fd >= 0:
                os.close(directory_fd)
        try:
            os.rmdir(name, dir_fd=root_fd)
            os.fsync(root_fd)
        except OSError as exc:
            raise AttachmentStoreError(
                "MAT_CLEANUP_FAILED",
                "Attachment directory cleanup failed.",
            ) from exc
        return True

    def _remove_allocation(self, root_fd: int, name: str) -> bool:
        if ALLOCATION_NAME_PATTERN.fullmatch(name) is None:
            return False
        directory_fd = -1
        try:
            entry_stat = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
            if not self._safe_directory_stat(entry_stat):
                return False
            directory_fd = self._open_child_directory(root_fd, name)
            with os.scandir(directory_fd) as iterator:
                entries = sorted(entry.name for entry in iterator)
            allowed = {PAYLOAD_FILE_NAME, METADATA_FILE_NAME}
            for child_name in entries:
                if child_name.startswith(".metadata-") and child_name.endswith(".tmp"):
                    pass
                elif child_name not in allowed:
                    return False
                child_stat = os.stat(
                    child_name,
                    dir_fd=directory_fd,
                    follow_symlinks=False,
                )
                if (
                    not stat.S_ISREG(child_stat.st_mode)
                    or child_stat.st_uid != os.geteuid()
                    or stat.S_IMODE(child_stat.st_mode) != ATTACHMENT_FILE_MODE
                ):
                    return False
            for child_name in entries:
                os.unlink(child_name, dir_fd=directory_fd)
            os.fsync(directory_fd)
            os.close(directory_fd)
            directory_fd = -1
            os.rmdir(name, dir_fd=root_fd)
            os.fsync(root_fd)
            return True
        except FileNotFoundError:
            return True
        except OSError:
            return False
        finally:
            if directory_fd >= 0:
                os.close(directory_fd)

    def _open_attachment_directory(self, attachment_id: str) -> int:
        _validate_attachment_id(attachment_id)
        root_fd = self._open_root()
        try:
            return self._open_child_directory(root_fd, f"att-{attachment_id}")
        finally:
            os.close(root_fd)

    @staticmethod
    def _open_child_directory(parent_fd: int, name: str) -> int:
        try:
            child_fd = os.open(
                name,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=parent_fd,
            )
        except OSError as exc:
            raise AttachmentStoreError(
                "MAT_ATTACHMENT_PERMISSION_INVALID",
                "Attachment directory is unavailable or unsafe.",
            ) from exc
        child_stat = os.fstat(child_fd)
        if not OpaqueAttachmentStore._safe_directory_stat(child_stat):
            os.close(child_fd)
            raise AttachmentStoreError(
                "MAT_ATTACHMENT_PERMISSION_INVALID",
                "Attachment directory ownership or permissions are unsafe.",
            )
        return child_fd

    def _open_root(self) -> int:
        try:
            root_fd = os.open(
                self._root,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            )
        except OSError as exc:
            raise AttachmentStoreError(
                "MAT_RUNTIME_ROOT_INVALID",
                "Attachment runtime root is unavailable.",
            ) from exc
        root_stat = os.fstat(root_fd)
        if (
            int(root_stat.st_dev) != self._root_device
            or int(root_stat.st_ino) != self._root_inode
            or not self._safe_directory_stat(root_stat)
        ):
            os.close(root_fd)
            raise AttachmentStoreError(
                "MAT_RUNTIME_ROOT_CHANGED",
                "Attachment runtime root identity changed.",
            )
        return root_fd

    @staticmethod
    def _safe_directory_stat(entry_stat: os.stat_result) -> bool:
        return (
            stat.S_ISDIR(entry_stat.st_mode)
            and entry_stat.st_uid == os.geteuid()
            and stat.S_IMODE(entry_stat.st_mode) == ATTACHMENT_DIRECTORY_MODE
        )

    @staticmethod
    def _initialise_root(configured_root: Path) -> Path:
        if configured_root.is_symlink():
            raise AttachmentStoreError(
                "MAT_RUNTIME_ROOT_INVALID",
                "Attachment runtime root must not be a symbolic link.",
            )
        if not configured_root.exists():
            configured_root.mkdir(parents=True, mode=ATTACHMENT_DIRECTORY_MODE)
            os.chmod(
                configured_root,
                ATTACHMENT_DIRECTORY_MODE,
                follow_symlinks=False,
            )
        if configured_root.is_symlink() or not configured_root.is_dir():
            raise AttachmentStoreError(
                "MAT_RUNTIME_ROOT_INVALID",
                "Attachment runtime root must be a directory.",
            )
        resolved = configured_root.resolve(strict=True)
        entry_stat = os.stat(resolved, follow_symlinks=False)
        if not OpaqueAttachmentStore._safe_directory_stat(entry_stat):
            raise AttachmentStoreError(
                "MAT_RUNTIME_ROOT_PERMISSION_INVALID",
                "Attachment runtime root ownership or permissions are unsafe.",
            )
        return resolved


def _record_to_json(record: AttachmentRecord) -> bytes:
    binding = record.binding
    payload = {
        "schema_version": 2,
        "attachment_id": record.attachment_id,
        "request_id": binding.request_id,
        "request_fingerprint": binding.request_fingerprint,
        "principal_fingerprint": binding.principal_fingerprint,
        "route_fingerprint": binding.route_fingerprint,
        "policy_fingerprint": binding.policy_fingerprint,
        "source_fingerprint": binding.source_fingerprint,
        "selection_fingerprint": binding.selection_fingerprint,
        "correlation_id": binding.correlation_id,
        "audit_id": binding.audit_id,
        "policy_result_id": binding.policy_result_id,
        "route_result_id": binding.route_result_id,
        "route_kind": binding.route_kind,
        "route_identity": binding.route_identity,
        "processor_code": binding.processor_code,
        "processor_profile": binding.processor_profile,
        "processor_version": binding.processor_version,
        "verified_representation": binding.verified_representation,
        "mime_decision": binding.mime_decision,
        "limits_fingerprint": binding.limits_fingerprint,
        "locality_decision_id": binding.locality_decision_id,
        "classification_decision_id": binding.classification_decision_id,
        "consent_decision_id": binding.consent_decision_id,
        "minimisation_decision_id": binding.minimisation_decision_id,
        "created_at": binding.created_at.isoformat(),
        "expires_at": binding.expires_at.isoformat(),
        "cleanup_deadline": binding.cleanup_deadline.isoformat(),
        "byte_size": record.byte_size,
        "sha256": record.sha256,
        "state": record.state,
        "consumed_at": (record.consumed_at.isoformat() if record.consumed_at else None),
        "cleanup_reason": record.cleanup_reason,
    }
    return json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _record_from_json(payload: bytes) -> AttachmentRecord:
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 2:
        raise ValueError("attachment metadata schema is unsupported")
    expected_keys = {
        "schema_version",
        "attachment_id",
        "request_id",
        "request_fingerprint",
        "principal_fingerprint",
        "route_fingerprint",
        "policy_fingerprint",
        "source_fingerprint",
        "selection_fingerprint",
        "correlation_id",
        "audit_id",
        "policy_result_id",
        "route_result_id",
        "route_kind",
        "route_identity",
        "processor_code",
        "processor_profile",
        "processor_version",
        "verified_representation",
        "mime_decision",
        "limits_fingerprint",
        "locality_decision_id",
        "classification_decision_id",
        "consent_decision_id",
        "minimisation_decision_id",
        "created_at",
        "expires_at",
        "cleanup_deadline",
        "byte_size",
        "sha256",
        "state",
        "consumed_at",
        "cleanup_reason",
    }
    if set(value) != expected_keys:
        raise ValueError("attachment metadata fields are not recognised")
    binding = AttachmentBinding(
        request_id=value["request_id"],
        request_fingerprint=value["request_fingerprint"],
        principal_fingerprint=value["principal_fingerprint"],
        route_fingerprint=value["route_fingerprint"],
        policy_fingerprint=value["policy_fingerprint"],
        source_fingerprint=value["source_fingerprint"],
        selection_fingerprint=value["selection_fingerprint"],
        correlation_id=value["correlation_id"],
        audit_id=value["audit_id"],
        policy_result_id=value["policy_result_id"],
        route_result_id=value["route_result_id"],
        route_kind=value["route_kind"],
        route_identity=value["route_identity"],
        processor_code=value["processor_code"],
        processor_profile=value["processor_profile"],
        processor_version=value["processor_version"],
        verified_representation=value["verified_representation"],
        mime_decision=value["mime_decision"],
        limits_fingerprint=value["limits_fingerprint"],
        locality_decision_id=value["locality_decision_id"],
        classification_decision_id=value["classification_decision_id"],
        consent_decision_id=value["consent_decision_id"],
        minimisation_decision_id=value["minimisation_decision_id"],
        created_at=datetime.fromisoformat(value["created_at"]),
        expires_at=datetime.fromisoformat(value["expires_at"]),
        cleanup_deadline=datetime.fromisoformat(value["cleanup_deadline"]),
    )
    consumed_at = value["consumed_at"]
    return AttachmentRecord(
        attachment_id=value["attachment_id"],
        binding=binding,
        byte_size=int(value["byte_size"]),
        sha256=value["sha256"],
        state=value["state"],
        consumed_at=(datetime.fromisoformat(consumed_at) if consumed_at else None),
        cleanup_reason=value["cleanup_reason"],
    )


def _new_attachment_id() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("ascii")


def _validate_attachment_id(value: str) -> None:
    if ATTACHMENT_ID_PATTERN.fullmatch(str(value)) is None:
        raise AttachmentStoreError(
            "MAT_ATTACHMENT_UNKNOWN",
            "Attachment identity is malformed.",
        )


def _canonical_sha256(value: str, *, field_name: str) -> str:
    text = str(value)
    if re.fullmatch(r"[0-9a-f]{64}", text) is None:
        raise ValueError(f"{field_name} must be a canonical SHA-256 digest")
    return text


def _canonical_uuid(value: str, *, field_name: str) -> str:
    try:
        canonical = str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(f"{field_name} must be a canonical UUID") from exc
    if canonical != str(value):
        raise ValueError(f"{field_name} must be a canonical UUID")
    return canonical


def _utc_datetime(value: datetime, *, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _positive_int(value: int, *, field_name: str) -> int:
    canonical = int(value)
    if canonical < 1:
        raise ValueError(f"{field_name} must be positive")
    return canonical
