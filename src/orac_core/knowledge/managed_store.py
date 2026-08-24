"""Own safe content-addressed storage for Core knowledge payloads."""

# Author: Clive Bostock
# Date: 26-Jul-2026
# Description: Streams, promotes, resolves, and verifies managed knowledge bytes.

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
import errno
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time
from typing import BinaryIO
import uuid

from lib.fsutils import project_home

BUFFER_SIZE = 1024 * 1024
DEFAULT_MANAGED_ROOT = project_home() / "var" / "knowledge" / "content"
DIRECTORY_MODE = 0o750
TEMP_DIRECTORY_MODE = 0o700
FILE_MODE = 0o600
LOGICAL_KEY_PREFIX = "sha256:"
TRANSIENT_ERRNOS = {
    errno.EINTR,
    errno.EIO,
    errno.ESTALE,
    errno.EBUSY,
    errno.EMFILE,
    errno.ENFILE,
    errno.ETIMEDOUT,
}
CANONICAL_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
CANONICAL_SHARD_PATTERN = re.compile(r"^[0-9a-f]{2}$")
TEMPORARY_NAME_PATTERN = re.compile(r"^capture-[0-9a-f]{32}\.tmp$")


class ManagedStoreWriteOutcome(StrEnum):
    """Describe whether a managed object was installed or reused."""

    INSTALLED = "installed"
    REUSED = "reused"


@dataclass(frozen=True)
class ManagedObjectIdentity:
    """Content identity for one immutable managed object."""

    sha256: str
    byte_size: int

    def __post_init__(self) -> None:
        """Validate and canonicalise the immutable identity."""
        digest = str(self.sha256)
        if (
            len(digest) != 64
            or digest != digest.lower()
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError(
                "SHA-256 must contain 64 lower-case hexadecimal characters."
            )
        if int(self.byte_size) < 0:
            raise ValueError("Managed object byte size must be zero or greater.")


@dataclass(frozen=True)
class ManagedStoreWriteResult:
    """Result of one managed-store write or immutable reuse."""

    identity: ManagedObjectIdentity
    storage_key: str
    outcome: ManagedStoreWriteOutcome


@dataclass(frozen=True)
class ManagedStoreFacts:
    """Bounded configuration and filesystem facts for operator inspection."""

    configured_root: Path
    resolved_root: Path
    configuration_source: str
    root_device: int
    root_inode: int
    temporary_device: int
    object_device: int
    promotion_method: str = "hard_link_no_replace"
    logical_key_format: str = "sha256:<64-lowercase-hex>"
    legacy_key_reads: bool = True


@dataclass(frozen=True)
class ManagedStoreInspection:
    """Non-sensitive result of inspecting one managed reference."""

    ok: bool
    reason_code: str
    identity: ManagedObjectIdentity | None = None


@dataclass(frozen=True, slots=True)
class ManagedStoreInventoryLimits:
    """Hard bounds applied to one physical managed-store inventory."""

    max_filesystem_entries: int
    max_hashed_bytes: int
    max_temporary_files_hashed: int
    max_elapsed_seconds: int
    stale_temporary_age_seconds: int
    max_traversal_depth: int = 4

    def __post_init__(self) -> None:
        """Reject non-positive or unsafe inventory limits."""
        for name in (
            "max_filesystem_entries",
            "max_hashed_bytes",
            "max_temporary_files_hashed",
            "max_elapsed_seconds",
            "stale_temporary_age_seconds",
            "max_traversal_depth",
        ):
            if int(getattr(self, name)) < 1:
                raise ValueError(f"{name} must be positive.")
        if self.max_traversal_depth > 4:
            raise ValueError("max_traversal_depth cannot exceed 4.")


@dataclass(frozen=True, slots=True)
class ManagedStoreInventoryEntry:
    """Private identity-bearing facts for one bounded physical entry."""

    entry_kind: str
    reason_codes: tuple[str, ...]
    byte_size: int
    age_seconds: int
    stable: bool
    identity_digest: str | None = field(default=None, repr=False)
    content_digest: str | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class ManagedStoreInventory:
    """Bounded physical inventory without public paths or entry names."""

    entries: tuple[ManagedStoreInventoryEntry, ...] = field(repr=False)
    complete: bool
    incomplete_reason_codes: tuple[str, ...]
    filesystem_entries: int
    hashed_bytes: int
    temporary_files_hashed: int
    elapsed_milliseconds: int
    root_identity_stable: bool
    object_directory_stable: bool
    temporary_directory_stable: bool


class ManagedStoreError(RuntimeError):
    """Raised when a managed-store operation fails safely."""

    def __init__(
        self,
        reason_code: str,
        message: str,
        *,
        transient: bool = False,
    ) -> None:
        """Initialise a stable reason-coded managed-store error."""
        super().__init__(message)
        self.reason_code = reason_code
        self.transient = transient


class ManagedStoreConfigurationError(ManagedStoreError):
    """Raised when managed-store configuration cannot operate safely."""


class KnowledgeManagedStore:
    """Stream immutable objects into one Core-owned content-addressed store."""

    def __init__(
        self,
        managed_root: Path,
        *,
        configuration_source: str = "injected",
    ) -> None:
        """Initialise and validate one fixed managed-store root."""
        self._configured_root = Path(managed_root).expanduser()
        self._configuration_source = configuration_source
        self._root = self._initialise_root(self._configured_root)
        root_stat = self._stat_root()
        self._root_device = int(root_stat.st_dev)
        self._root_inode = int(root_stat.st_ino)
        self._ensure_directory((".tmp",), mode=TEMP_DIRECTORY_MODE)
        self._ensure_directory(("sha256",), mode=DIRECTORY_MODE)
        temporary_stat = self._stat_directory((".tmp",))
        object_stat = self._stat_directory(("sha256",))
        if temporary_stat.st_dev != object_stat.st_dev:
            raise ManagedStoreConfigurationError(
                "STORE_FILESYSTEM_MISMATCH",
                "Managed temporary and object directories must share a filesystem.",
            )
        self._temporary_device = int(temporary_stat.st_dev)
        self._object_device = int(object_stat.st_dev)
        self._probe_hard_links()

    @classmethod
    def from_config(
        cls,
        config_mgr: object | None,
        *,
        root_override: Path | None = None,
    ) -> "KnowledgeManagedStore":
        """Build a store from the authoritative knowledge configuration."""
        if root_override is not None:
            return cls(root_override, configuration_source="explicit override")
        if config_mgr is None:
            return cls(DEFAULT_MANAGED_ROOT, configuration_source="runtime fallback")
        path_loader = getattr(config_mgr, "path_config_value", None)
        if callable(path_loader):
            root = path_loader(
                "knowledge",
                "managed_root",
                default=str(DEFAULT_MANAGED_ROOT),
                suppress_warnings=True,
            )
        else:
            value_loader = getattr(config_mgr, "config_value")
            raw_root = value_loader(
                "knowledge",
                "managed_root",
                default=str(DEFAULT_MANAGED_ROOT),
            )
            root = Path(os.path.expandvars(os.path.expanduser(str(raw_root))))
        return cls(Path(root), configuration_source="[knowledge].managed_root")

    @classmethod
    def for_read_only_inspection(
        cls,
        managed_root: Path,
        *,
        configuration_source: str = "injected",
    ) -> "KnowledgeManagedStore":
        """Open an existing store without creating or probing filesystem state.

        Args:
            managed_root: Existing configured managed-store root.
            configuration_source: Non-sensitive source label for reporting.

        Returns:
            A store instance restricted by convention to inspection methods.

        Raises:
            ManagedStoreConfigurationError: If the existing layout is unsafe.
        """
        configured_root = Path(managed_root).expanduser()
        if configured_root.is_symlink():
            raise ManagedStoreConfigurationError(
                "STORE_ROOT_SYMLINK",
                "Configured managed-store root must not be a symbolic link.",
            )
        if not configured_root.is_dir():
            raise ManagedStoreConfigurationError(
                "STORE_ROOT_NOT_DIRECTORY",
                "Configured managed-store root must already be a directory.",
            )
        store = cls.__new__(cls)
        store._configured_root = configured_root
        store._configuration_source = configuration_source
        store._root = configured_root.resolve(strict=True)
        root_stat = store._stat_root()
        store._root_device = int(root_stat.st_dev)
        store._root_inode = int(root_stat.st_ino)
        temporary_stat = store._stat_directory((".tmp",))
        object_stat = store._stat_directory(("sha256",))
        store._temporary_device = int(temporary_stat.st_dev)
        store._object_device = int(object_stat.st_dev)
        if temporary_stat.st_dev != object_stat.st_dev:
            raise ManagedStoreConfigurationError(
                "STORE_FILESYSTEM_MISMATCH",
                "Managed temporary and object directories must share a filesystem.",
            )
        return store

    @property
    def managed_root(self) -> Path:
        """Return the fixed resolved root for Core diagnostics."""
        return self._root

    def facts(self) -> ManagedStoreFacts:
        """Return bounded configuration and filesystem facts."""
        return ManagedStoreFacts(
            configured_root=self._configured_root,
            resolved_root=self._root,
            configuration_source=self._configuration_source,
            root_device=self._root_device,
            root_inode=self._root_inode,
            temporary_device=self._temporary_device,
            object_device=self._object_device,
        )

    def assert_ready(self) -> None:
        """Fail if the fixed store root has changed or become unsafe."""
        root_fd = self._open_root()
        os.close(root_fd)
        for parts, mode in (
            ((".tmp",), TEMP_DIRECTORY_MODE),
            (("sha256",), DIRECTORY_MODE),
        ):
            directory_fd = self._open_directory(parts, create=False, mode=mode)
            os.close(directory_fd)

    def put_stream(
        self,
        stream: BinaryIO,
        expected_identity: ManagedObjectIdentity | None = None,
    ) -> ManagedStoreWriteResult:
        """Stream bytes into the store and atomically install or reuse them."""
        self.assert_ready()
        temporary_fd = self._open_directory(
            (".tmp",),
            create=False,
            mode=TEMP_DIRECTORY_MODE,
        )
        temporary_name = f"capture-{uuid.uuid4().hex}.tmp"
        file_fd: int | None = None
        try:
            file_fd = os.open(
                temporary_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                FILE_MODE,
                dir_fd=temporary_fd,
            )
            os.fchmod(file_fd, FILE_MODE)
            digest = hashlib.sha256()
            byte_size = 0
            with os.fdopen(file_fd, "wb", closefd=True) as temporary_stream:
                file_fd = None
                while True:
                    chunk = stream.read(BUFFER_SIZE)
                    if chunk in (b"", None):
                        break
                    if not isinstance(chunk, bytes):
                        raise ManagedStoreError(
                            "STORE_STREAM_INVALID",
                            "Managed-store streams must return binary bytes.",
                        )
                    digest.update(chunk)
                    byte_size += len(chunk)
                    temporary_stream.write(chunk)
                temporary_stream.flush()
                os.fsync(temporary_stream.fileno())
            identity = ManagedObjectIdentity(digest.hexdigest(), byte_size)
            if expected_identity is not None and identity != expected_identity:
                reason = (
                    "MANAGED_OBJECT_SIZE_MISMATCH"
                    if identity.byte_size != expected_identity.byte_size
                    else "MANAGED_OBJECT_HASH_MISMATCH"
                )
                raise ManagedStoreError(
                    reason,
                    "Streamed bytes do not match the expected managed identity.",
                )
            result = self._promote(
                temporary_fd=temporary_fd,
                temporary_name=temporary_name,
                identity=identity,
            )
        except Exception as exc:
            cleanup_error = self._remove_temporary(temporary_fd, temporary_name)
            if file_fd is not None:
                os.close(file_fd)
            os.close(temporary_fd)
            if cleanup_error is not None:
                raise cleanup_error from exc
            if isinstance(exc, OSError):
                raise self._object_os_error(exc, operation="write") from exc
            raise
        cleanup_error = self._remove_temporary(temporary_fd, temporary_name)
        os.close(temporary_fd)
        if cleanup_error is not None:
            raise cleanup_error
        return result

    def put_file(
        self,
        source_path: Path,
        expected_identity: ManagedObjectIdentity | None = None,
    ) -> ManagedStoreWriteResult:
        """Securely open a regular source file and delegate to ``put_stream``."""
        try:
            source_fd = os.open(
                Path(source_path),
                os.O_RDONLY | os.O_NOFOLLOW,
            )
        except OSError as exc:
            raise self._object_os_error(exc, operation="open source") from exc
        try:
            source_stat = os.fstat(source_fd)
            if not stat.S_ISREG(source_stat.st_mode):
                raise ManagedStoreError(
                    "SOURCE_NOT_REGULAR",
                    "Managed-store file input must be a regular file.",
                )
            with os.fdopen(source_fd, "rb", closefd=True) as source:
                source_fd = -1
                return self.put_stream(source, expected_identity)
        finally:
            if source_fd >= 0:
                os.close(source_fd)

    def put_bytes(
        self,
        payload: bytes,
        expected_identity: ManagedObjectIdentity | None = None,
    ) -> ManagedStoreWriteResult:
        """Delegate an in-memory binary payload to ``put_stream``."""
        return self.put_stream(io.BytesIO(payload), expected_identity)

    @contextmanager
    def open_verified(
        self,
        storage_key: str,
        expected_identity: ManagedObjectIdentity,
    ) -> Iterator[BinaryIO]:
        """Yield the same managed-object descriptor used for verification."""
        digest = self._parse_storage_key(storage_key)
        if digest != expected_identity.sha256:
            raise ManagedStoreError(
                "STORAGE_KEY_IDENTITY_MISMATCH",
                "Managed storage key does not match the registered hash.",
            )
        object_fd = self._open_object_descriptor(digest)
        stream: BinaryIO | None = None
        try:
            object_stat = os.fstat(object_fd)
            if not stat.S_ISREG(object_stat.st_mode):
                raise ManagedStoreError(
                    "MANAGED_OBJECT_NOT_REGULAR",
                    "Managed object is not a regular file.",
                )
            self._validate_file_permissions(object_stat)
            if object_stat.st_size != expected_identity.byte_size:
                raise ManagedStoreError(
                    "MANAGED_OBJECT_SIZE_MISMATCH",
                    "Managed object size does not match its registered identity.",
                )
            stream = os.fdopen(object_fd, "rb", buffering=0, closefd=True)
            object_fd = -1
            digest_calculator = hashlib.sha256()
            while True:
                chunk = stream.read(BUFFER_SIZE)
                if not chunk:
                    break
                digest_calculator.update(chunk)
            if digest_calculator.hexdigest() != expected_identity.sha256:
                raise ManagedStoreError(
                    "MANAGED_OBJECT_HASH_MISMATCH",
                    "Managed object hash does not match its registered identity.",
                )
            stream.seek(0)
            yield stream
        finally:
            if stream is not None:
                stream.close()
            elif object_fd >= 0:
                os.close(object_fd)

    def inspect_reference(
        self,
        storage_key: str,
        expected_identity: ManagedObjectIdentity,
    ) -> ManagedStoreInspection:
        """Inspect one reference without exposing content or host paths."""
        try:
            with self.open_verified(storage_key, expected_identity):
                pass
        except ManagedStoreError as exc:
            return ManagedStoreInspection(ok=False, reason_code=exc.reason_code)
        return ManagedStoreInspection(
            ok=True,
            reason_code="OK",
            identity=expected_identity,
        )

    def inventory(
        self,
        limits: ManagedStoreInventoryLimits,
        *,
        observed_at: float | None = None,
    ) -> ManagedStoreInventory:
        """Enumerate and verify the physical store within fixed read-only bounds.

        The scan holds directory descriptors while enumerating, never follows
        symbolic links, and retains entry names only on the Python stack. Returned
        records contain private digests needed for reconciliation but no paths.

        Args:
            limits: Hard ceilings for traversal and hashing.
            observed_at: Optional wall-clock timestamp used by deterministic tests.

        Returns:
            Immutable physical inventory and resource usage.
        """
        started = time.monotonic()
        wall_clock = time.time() if observed_at is None else float(observed_at)
        entries: list[ManagedStoreInventoryEntry] = []
        incomplete_reasons: list[str] = []
        filesystem_entries = 0
        hashed_bytes = 0
        temporary_files_hashed = 0
        root_stable = True
        object_stable = True
        temporary_stable = True

        class _InventoryCeilingReached(Exception):
            pass

        def elapsed_seconds() -> float:
            return time.monotonic() - started

        def stop(reason_code: str) -> None:
            if reason_code not in incomplete_reasons:
                incomplete_reasons.append(reason_code)
            raise _InventoryCeilingReached

        def check_time() -> None:
            if elapsed_seconds() >= limits.max_elapsed_seconds:
                stop("RECON_ELAPSED_TIME_LIMIT_EXCEEDED")

        def count_entry() -> None:
            nonlocal filesystem_entries
            check_time()
            if filesystem_entries >= limits.max_filesystem_entries:
                stop("RECON_FILESYSTEM_ENTRY_LIMIT_EXCEEDED")
            filesystem_entries += 1

        def permission_reasons(
            entry_stat: os.stat_result,
            *,
            directory: bool,
            temporary_directory: bool = False,
        ) -> list[str]:
            reasons: list[str] = []
            if entry_stat.st_uid != os.geteuid():
                reasons.append("STORE_ENTRY_OWNER_INVALID")
            mode = stat.S_IMODE(entry_stat.st_mode)
            if directory:
                allowed = TEMP_DIRECTORY_MODE if temporary_directory else 0o755
                if mode & ~allowed or mode & 0o022 or mode & 0o700 != 0o700:
                    reasons.append("STORE_ENTRY_MODE_INVALID")
            elif mode & ~FILE_MODE:
                reasons.append("STORE_ENTRY_MODE_INVALID")
            return reasons

        def hash_regular(
            directory_fd: int,
            name: str,
            entry_stat: os.stat_result,
        ) -> tuple[str | None, bool]:
            nonlocal hashed_bytes
            file_fd = -1
            try:
                file_fd = os.open(
                    name,
                    os.O_RDONLY | os.O_NOFOLLOW,
                    dir_fd=directory_fd,
                )
                before = os.fstat(file_fd)
                if not stat.S_ISREG(before.st_mode):
                    return None, False
                calculator = hashlib.sha256()
                while True:
                    check_time()
                    chunk = os.read(file_fd, BUFFER_SIZE)
                    if not chunk:
                        break
                    if hashed_bytes + len(chunk) > limits.max_hashed_bytes:
                        stop("RECON_HASH_BYTE_LIMIT_EXCEEDED")
                    hashed_bytes += len(chunk)
                    calculator.update(chunk)
                after = os.fstat(file_fd)
                stable_fields = (
                    "st_dev",
                    "st_ino",
                    "st_size",
                    "st_mtime_ns",
                    "st_ctime_ns",
                )
                stable = all(
                    getattr(before, field_name)
                    == getattr(after, field_name)
                    == getattr(entry_stat, field_name)
                    for field_name in stable_fields
                )
                return calculator.hexdigest(), stable
            except OSError:
                return None, False
            finally:
                if file_fd >= 0:
                    os.close(file_fd)

        def add_regular(
            directory_fd: int,
            name: str,
            relative_parts: tuple[str, ...],
            entry_stat: os.stat_result,
        ) -> None:
            nonlocal temporary_files_hashed
            full_parts = (*relative_parts, name)
            reasons = permission_reasons(entry_stat, directory=False)
            age_seconds = max(0, int(wall_clock - entry_stat.st_mtime))
            identity_digest: str | None = None
            content_digest: str | None = None
            stable = True
            entry_kind = "UNEXPECTED_FILE"

            if full_parts[0] == ".tmp" and len(full_parts) == 2:
                entry_kind = "TEMPORARY"
                if not TEMPORARY_NAME_PATTERN.fullmatch(name):
                    reasons.append("STORE_TEMP_NAME_UNEXPECTED")
                if temporary_files_hashed >= limits.max_temporary_files_hashed:
                    stop("RECON_TEMP_HASH_FILE_LIMIT_EXCEEDED")
                temporary_files_hashed += 1
                content_digest, stable = hash_regular(directory_fd, name, entry_stat)
                reasons.append(
                    "STORE_TEMP_STALE"
                    if age_seconds >= limits.stale_temporary_age_seconds
                    else "STORE_TEMP_ACTIVE"
                )
            elif full_parts[0] == "sha256" and len(full_parts) == 4:
                entry_kind = "OBJECT"
                first_shard, second_shard = full_parts[1], full_parts[2]
                if not CANONICAL_DIGEST_PATTERN.fullmatch(name):
                    reasons.append("MANAGED_OBJECT_FILENAME_INVALID")
                elif first_shard != name[:2] or second_shard != name[2:4]:
                    reasons.append("MANAGED_OBJECT_SHARD_INVALID")
                else:
                    identity_digest = name
                    content_digest, stable = hash_regular(
                        directory_fd,
                        name,
                        entry_stat,
                    )
                    if content_digest is None:
                        reasons.append("MANAGED_OBJECT_NOT_REGULAR")
                    elif content_digest != identity_digest:
                        reasons.append("MANAGED_OBJECT_HASH_MISMATCH")
                    if entry_stat.st_nlink != 1:
                        reasons.append("MANAGED_OBJECT_LINK_COUNT_UNEXPECTED")
            else:
                reasons.append("STORE_UNEXPECTED_REGULAR_FILE")

            if not stable:
                reasons.append("STORE_ENTRY_CHANGED_DURING_SCAN")
            entries.append(
                ManagedStoreInventoryEntry(
                    entry_kind=entry_kind,
                    reason_codes=tuple(dict.fromkeys(reasons)),
                    byte_size=int(entry_stat.st_size),
                    age_seconds=age_seconds,
                    stable=stable,
                    identity_digest=identity_digest,
                    content_digest=content_digest,
                )
            )

        def walk(directory_fd: int, relative_parts: tuple[str, ...]) -> None:
            check_time()
            with os.scandir(directory_fd) as iterator:
                names = sorted(entry.name for entry in iterator)
            for name in names:
                count_entry()
                try:
                    entry_stat = os.stat(
                        name,
                        dir_fd=directory_fd,
                        follow_symlinks=False,
                    )
                except OSError:
                    entries.append(
                        ManagedStoreInventoryEntry(
                            entry_kind="UNREADABLE",
                            reason_codes=("STORE_ENTRY_CHANGED_DURING_SCAN",),
                            byte_size=0,
                            age_seconds=0,
                            stable=False,
                        )
                    )
                    continue
                full_parts = (*relative_parts, name)
                if stat.S_ISLNK(entry_stat.st_mode):
                    entries.append(
                        ManagedStoreInventoryEntry(
                            entry_kind="SYMLINK",
                            reason_codes=("STORE_SYMLINK_FOUND",),
                            byte_size=0,
                            age_seconds=max(0, int(wall_clock - entry_stat.st_mtime)),
                            stable=True,
                        )
                    )
                    continue
                if stat.S_ISREG(entry_stat.st_mode):
                    add_regular(directory_fd, name, relative_parts, entry_stat)
                    continue
                if not stat.S_ISDIR(entry_stat.st_mode):
                    entries.append(
                        ManagedStoreInventoryEntry(
                            entry_kind="UNSUPPORTED",
                            reason_codes=("STORE_UNSUPPORTED_FILE_TYPE",),
                            byte_size=int(entry_stat.st_size),
                            age_seconds=max(0, int(wall_clock - entry_stat.st_mtime)),
                            stable=True,
                        )
                    )
                    continue

                reasons = permission_reasons(
                    entry_stat,
                    directory=True,
                    temporary_directory=full_parts == (".tmp",),
                )
                expected_directory = (
                    full_parts in {(".tmp",), ("sha256",)}
                    or (
                        len(full_parts) == 2
                        and full_parts[0] == "sha256"
                        and CANONICAL_SHARD_PATTERN.fullmatch(name) is not None
                    )
                    or (
                        len(full_parts) == 3
                        and full_parts[0] == "sha256"
                        and CANONICAL_SHARD_PATTERN.fullmatch(name) is not None
                    )
                )
                if not expected_directory:
                    reasons.append(
                        "MANAGED_OBJECT_SHARD_INVALID"
                        if full_parts[0] == "sha256" and len(full_parts) <= 3
                        else "STORE_UNEXPECTED_DIRECTORY"
                    )
                entries.append(
                    ManagedStoreInventoryEntry(
                        entry_kind="DIRECTORY",
                        reason_codes=tuple(dict.fromkeys(reasons)),
                        byte_size=0,
                        age_seconds=max(0, int(wall_clock - entry_stat.st_mtime)),
                        stable=True,
                    )
                )
                if len(full_parts) >= limits.max_traversal_depth:
                    if expected_directory:
                        entries.append(
                            ManagedStoreInventoryEntry(
                                entry_kind="DEPTH_LIMIT",
                                reason_codes=("STORE_UNEXPECTED_DIRECTORY",),
                                byte_size=0,
                                age_seconds=0,
                                stable=True,
                            )
                        )
                    continue
                try:
                    child_fd = os.open(
                        name,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=directory_fd,
                    )
                except OSError:
                    entries.append(
                        ManagedStoreInventoryEntry(
                            entry_kind="UNREADABLE_DIRECTORY",
                            reason_codes=("STORE_ENTRY_CHANGED_DURING_SCAN",),
                            byte_size=0,
                            age_seconds=0,
                            stable=False,
                        )
                    )
                    continue
                try:
                    walk(child_fd, full_parts)
                finally:
                    os.close(child_fd)

        root_before = self._stat_root()
        object_before = self._stat_directory(("sha256",))
        temporary_before = self._stat_directory((".tmp",))
        root_fd = self._open_root()
        try:
            try:
                walk(root_fd, ())
            except _InventoryCeilingReached:
                pass
        finally:
            os.close(root_fd)

        def stable_directory(
            before: os.stat_result,
            after: os.stat_result,
        ) -> bool:
            return all(
                getattr(before, field_name) == getattr(after, field_name)
                for field_name in (
                    "st_dev",
                    "st_ino",
                    "st_mtime_ns",
                    "st_ctime_ns",
                )
            )

        try:
            root_after = self._stat_root()
            root_stable = stable_directory(root_before, root_after)
        except ManagedStoreError:
            root_stable = False
        try:
            object_after = self._stat_directory(("sha256",))
            object_stable = stable_directory(object_before, object_after)
        except ManagedStoreError:
            object_stable = False
        try:
            temporary_after = self._stat_directory((".tmp",))
            temporary_stable = stable_directory(temporary_before, temporary_after)
        except ManagedStoreError:
            temporary_stable = False
        for stable, reason in (
            (root_stable, "STORE_ROOT_CHANGED_DURING_SCAN"),
            (object_stable, "STORE_OBJECT_DIRECTORY_CHANGED_DURING_SCAN"),
            (temporary_stable, "STORE_TEMP_DIRECTORY_CHANGED_DURING_SCAN"),
        ):
            if not stable and reason not in incomplete_reasons:
                incomplete_reasons.append(reason)

        return ManagedStoreInventory(
            entries=tuple(entries),
            complete=not incomplete_reasons,
            incomplete_reason_codes=tuple(incomplete_reasons),
            filesystem_entries=filesystem_entries,
            hashed_bytes=hashed_bytes,
            temporary_files_hashed=temporary_files_hashed,
            elapsed_milliseconds=max(0, int(elapsed_seconds() * 1000)),
            root_identity_stable=root_stable,
            object_directory_stable=object_stable,
            temporary_directory_stable=temporary_stable,
        )

    def _promote(
        self,
        *,
        temporary_fd: int,
        temporary_name: str,
        identity: ManagedObjectIdentity,
    ) -> ManagedStoreWriteResult:
        destination_fd = self._open_digest_directory(identity.sha256, create=True)
        try:
            try:
                os.link(
                    temporary_name,
                    identity.sha256,
                    src_dir_fd=temporary_fd,
                    dst_dir_fd=destination_fd,
                    follow_symlinks=False,
                )
            except FileExistsError:
                with self.open_verified(
                    self.storage_key(identity.sha256),
                    identity,
                ):
                    pass
                outcome = ManagedStoreWriteOutcome.REUSED
            except OSError as exc:
                if exc.errno in {errno.EPERM, errno.EOPNOTSUPP, errno.EXDEV}:
                    raise ManagedStoreConfigurationError(
                        "STORE_HARDLINK_UNSUPPORTED",
                        "Managed-store no-clobber promotion is unavailable.",
                    ) from exc
                raise self._object_os_error(exc, operation="promote") from exc
            else:
                os.fsync(destination_fd)
                outcome = ManagedStoreWriteOutcome.INSTALLED
        finally:
            os.close(destination_fd)
        return ManagedStoreWriteResult(
            identity=identity,
            storage_key=self.storage_key(identity.sha256),
            outcome=outcome,
        )

    def _open_object_descriptor(self, digest: str) -> int:
        directory_fd = self._open_digest_directory(digest, create=False)
        try:
            try:
                return os.open(
                    digest,
                    os.O_RDONLY | os.O_NOFOLLOW,
                    dir_fd=directory_fd,
                )
            except FileNotFoundError as exc:
                raise ManagedStoreError(
                    "MANAGED_OBJECT_MISSING",
                    "Managed object is missing.",
                ) from exc
            except OSError as exc:
                if exc.errno == errno.ELOOP:
                    raise ManagedStoreError(
                        "MANAGED_OBJECT_SYMLINK",
                        "Managed object must not be a symbolic link.",
                    ) from exc
                raise self._object_os_error(exc, operation="open object") from exc
        finally:
            os.close(directory_fd)

    def _open_digest_directory(self, digest: str, *, create: bool) -> int:
        return self._open_directory(
            ("sha256", digest[:2], digest[2:4]),
            create=create,
            mode=DIRECTORY_MODE,
        )

    def _ensure_directory(self, parts: tuple[str, ...], *, mode: int) -> None:
        directory_fd = self._open_directory(parts, create=True, mode=mode)
        os.close(directory_fd)

    def _open_directory(
        self,
        parts: tuple[str, ...],
        *,
        create: bool,
        mode: int,
    ) -> int:
        current_fd = self._open_root()
        try:
            for index, part in enumerate(parts):
                part_mode = mode if index == len(parts) - 1 else DIRECTORY_MODE
                try:
                    next_fd = os.open(
                        part,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=current_fd,
                    )
                except FileNotFoundError:
                    if not create:
                        raise ManagedStoreError(
                            "MANAGED_OBJECT_MISSING",
                            "Managed object directory is missing.",
                        )
                    created = False
                    try:
                        os.mkdir(part, part_mode, dir_fd=current_fd)
                        created = True
                    except FileExistsError:
                        pass
                    next_fd = os.open(
                        part,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=current_fd,
                    )
                    if created:
                        os.fchmod(next_fd, part_mode)
                        os.fsync(current_fd)
                except OSError as exc:
                    if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
                        raise ManagedStoreError(
                            "UNSAFE_STORE_LAYOUT",
                            "Managed-store directory layout is unsafe.",
                        ) from exc
                    raise self._object_os_error(
                        exc,
                        operation="open directory",
                    ) from exc
                directory_stat = os.fstat(next_fd)
                self._validate_directory_permissions(
                    directory_stat,
                    temporary=parts[: index + 1] == (".tmp",),
                )
                os.close(current_fd)
                current_fd = next_fd
            return current_fd
        except Exception:
            os.close(current_fd)
            raise

    def _open_root(self) -> int:
        try:
            root_fd = os.open(
                self._root,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            )
        except OSError as exc:
            raise ManagedStoreConfigurationError(
                "STORE_ROOT_IDENTITY_CHANGED",
                "Managed-store root is no longer available as configured.",
                transient=exc.errno in TRANSIENT_ERRNOS,
            ) from exc
        root_stat = os.fstat(root_fd)
        if (
            int(root_stat.st_dev) != self._root_device
            or int(root_stat.st_ino) != self._root_inode
        ):
            os.close(root_fd)
            raise ManagedStoreConfigurationError(
                "STORE_ROOT_IDENTITY_CHANGED",
                "Managed-store root identity changed during service lifetime.",
            )
        self._validate_directory_permissions(root_stat, temporary=False)
        return root_fd

    def _stat_root(self) -> os.stat_result:
        try:
            root_stat = os.stat(self._root, follow_symlinks=False)
        except OSError as exc:
            raise ManagedStoreConfigurationError(
                "STORE_ROOT_NOT_DIRECTORY",
                "Managed-store root is unavailable.",
            ) from exc
        self._validate_directory_permissions(root_stat, temporary=False)
        return root_stat

    def _stat_directory(self, parts: tuple[str, ...]) -> os.stat_result:
        directory_fd = self._open_directory(
            parts,
            create=False,
            mode=TEMP_DIRECTORY_MODE if parts == (".tmp",) else DIRECTORY_MODE,
        )
        try:
            return os.fstat(directory_fd)
        finally:
            os.close(directory_fd)

    def _probe_hard_links(self) -> None:
        temporary_fd = self._open_directory(
            (".tmp",),
            create=False,
            mode=TEMP_DIRECTORY_MODE,
        )
        try:
            object_fd = self._open_directory(
                ("sha256",),
                create=False,
                mode=DIRECTORY_MODE,
            )
        except Exception:
            os.close(temporary_fd)
            raise
        source_name = f".capability-{uuid.uuid4().hex}"
        target_name = f"{source_name}.link"
        source_fd: int | None = None
        try:
            source_fd = os.open(
                source_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                FILE_MODE,
                dir_fd=temporary_fd,
            )
            os.fchmod(source_fd, FILE_MODE)
            os.fsync(source_fd)
            os.close(source_fd)
            source_fd = None
            try:
                os.link(
                    source_name,
                    target_name,
                    src_dir_fd=temporary_fd,
                    dst_dir_fd=object_fd,
                    follow_symlinks=False,
                )
            except OSError as exc:
                raise ManagedStoreConfigurationError(
                    "STORE_HARDLINK_UNSUPPORTED",
                    "Managed-store filesystem does not support hard-link promotion.",
                ) from exc
        finally:
            if source_fd is not None:
                os.close(source_fd)
            cleanup_failed = False
            for directory_fd, name in (
                (object_fd, target_name),
                (temporary_fd, source_name),
            ):
                try:
                    os.unlink(name, dir_fd=directory_fd)
                except FileNotFoundError:
                    pass
                except OSError:
                    cleanup_failed = True
            for directory_fd in (object_fd, temporary_fd):
                try:
                    os.fsync(directory_fd)
                except OSError:
                    cleanup_failed = True
            os.close(object_fd)
            os.close(temporary_fd)
            if cleanup_failed:
                raise ManagedStoreConfigurationError(
                    "STORE_CAPABILITY_CLEANUP_FAILED",
                    "Managed-store capability probe cleanup failed.",
                )

    def _remove_temporary(
        self,
        temporary_fd: int,
        temporary_name: str,
    ) -> ManagedStoreError | None:
        try:
            os.unlink(temporary_name, dir_fd=temporary_fd)
            os.fsync(temporary_fd)
        except FileNotFoundError:
            return None
        except OSError:
            return ManagedStoreError(
                "STORE_TEMP_CLEANUP_FAILED",
                "Managed-store temporary cleanup failed.",
            )
        return None

    def _initialise_root(self, configured_root: Path) -> Path:
        if configured_root.is_symlink():
            raise ManagedStoreConfigurationError(
                "STORE_ROOT_SYMLINK",
                "Configured managed-store root must not be a symbolic link.",
            )
        if not configured_root.exists():
            missing: list[Path] = []
            candidate = configured_root
            while not candidate.exists():
                missing.append(candidate)
                candidate = candidate.parent
            for directory in reversed(missing):
                try:
                    directory.mkdir(mode=DIRECTORY_MODE)
                    os.chmod(directory, DIRECTORY_MODE, follow_symlinks=False)
                except OSError as exc:
                    raise ManagedStoreConfigurationError(
                        "STORE_ROOT_CREATE_FAILED",
                        "Configured managed-store root could not be created.",
                    ) from exc
        if configured_root.is_symlink():
            raise ManagedStoreConfigurationError(
                "STORE_ROOT_SYMLINK",
                "Configured managed-store root must not be a symbolic link.",
            )
        if not configured_root.is_dir():
            raise ManagedStoreConfigurationError(
                "STORE_ROOT_NOT_DIRECTORY",
                "Configured managed-store root must be a directory.",
            )
        return configured_root.resolve(strict=True)

    @staticmethod
    def storage_key(digest: str) -> str:
        """Return the canonical logical key for one validated digest."""
        ManagedObjectIdentity(digest, 0)
        return f"{LOGICAL_KEY_PREFIX}{digest}"

    @staticmethod
    def legacy_storage_key(digest: str) -> str:
        """Return the exact supported legacy shard locator for one digest."""
        ManagedObjectIdentity(digest, 0)
        return f"sha256/{digest[:2]}/{digest[2:4]}/{digest}"

    @staticmethod
    def _parse_storage_key(storage_key: str) -> str:
        value = str(storage_key)
        if value.startswith(LOGICAL_KEY_PREFIX):
            digest = value.removeprefix(LOGICAL_KEY_PREFIX)
            try:
                ManagedObjectIdentity(digest, 0)
            except ValueError as exc:
                raise ManagedStoreError(
                    "INVALID_STORAGE_KEY",
                    "Managed storage key is malformed.",
                ) from exc
            return digest
        parts = PurePosixPath(value).parts
        if (
            len(parts) == 4
            and parts[0] == "sha256"
            and len(parts[1]) == 2
            and len(parts[2]) == 2
        ):
            digest = parts[3]
            try:
                ManagedObjectIdentity(digest, 0)
            except ValueError as exc:
                raise ManagedStoreError(
                    "INVALID_STORAGE_KEY",
                    "Legacy managed storage key is malformed.",
                ) from exc
            if parts[1] == digest[:2] and parts[2] == digest[2:4]:
                return digest
        raise ManagedStoreError(
            "INVALID_STORAGE_KEY",
            "Managed storage key is malformed.",
        )

    @staticmethod
    def _validate_directory_permissions(
        directory_stat: os.stat_result,
        *,
        temporary: bool,
    ) -> None:
        if not stat.S_ISDIR(directory_stat.st_mode):
            raise ManagedStoreConfigurationError(
                "STORE_ROOT_NOT_DIRECTORY",
                "Managed-store directory is not a directory.",
            )
        if directory_stat.st_uid != os.geteuid():
            raise ManagedStoreConfigurationError(
                "STORE_ROOT_OWNER_INVALID",
                "Managed-store directories must be owned by the runtime user.",
            )
        mode = stat.S_IMODE(directory_stat.st_mode)
        allowed = TEMP_DIRECTORY_MODE if temporary else 0o755
        if mode & ~allowed or mode & 0o022 or mode & 0o700 != 0o700:
            raise ManagedStoreConfigurationError(
                "STORE_ROOT_MODE_INVALID",
                "Managed-store directory permissions are unsafe.",
            )

    @staticmethod
    def _validate_file_permissions(file_stat: os.stat_result) -> None:
        if (
            file_stat.st_uid != os.geteuid()
            or stat.S_IMODE(file_stat.st_mode) & ~FILE_MODE
        ):
            raise ManagedStoreError(
                "MANAGED_OBJECT_PERMISSION_INVALID",
                "Managed object permissions are unsafe.",
            )

    @staticmethod
    def _object_os_error(exc: OSError, *, operation: str) -> ManagedStoreError:
        if exc.errno in {errno.EACCES, errno.EPERM}:
            return ManagedStoreError(
                "MANAGED_OBJECT_PERMISSION_INVALID",
                f"Managed-store {operation} was denied.",
            )
        return ManagedStoreError(
            (
                "MANAGED_STORE_TRANSIENT_IO"
                if exc.errno in TRANSIENT_ERRNOS
                else "MANAGED_STORE_IO_ERROR"
            ),
            f"Managed-store {operation} failed.",
            transient=exc.errno in TRANSIENT_ERRNOS,
        )
