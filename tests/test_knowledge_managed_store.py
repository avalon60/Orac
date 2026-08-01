"""Tests for the Core-managed streaming content store."""

# Author: Clive Bostock
# Date: 26-Jul-2026
# Description: Verifies streaming, promotion, path, permission, and read safety.

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import errno
import hashlib
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from orac_core.knowledge.managed_store import BUFFER_SIZE  # noqa: E402
from orac_core.knowledge.managed_store import KnowledgeManagedStore  # noqa: E402
from orac_core.knowledge.managed_store import ManagedObjectIdentity  # noqa: E402
from orac_core.knowledge.managed_store import (  # noqa: E402
    ManagedStoreConfigurationError,
)
from orac_core.knowledge.managed_store import ManagedStoreError  # noqa: E402
from orac_core.knowledge.managed_store import ManagedStoreWriteOutcome  # noqa: E402


class _GeneratedStream:
    """Generate a large deterministic payload using bounded reads."""

    def __init__(self, total_size: int) -> None:
        self.remaining = total_size
        self.largest_request = 0

    def read(self, size: int = -1) -> bytes:
        """Return a deterministic bounded block."""
        if size < 0:
            raise AssertionError("The store attempted an unbounded read.")
        self.largest_request = max(self.largest_request, size)
        amount = min(size, self.remaining)
        self.remaining -= amount
        return b"x" * amount


class KnowledgeManagedStoreTests(unittest.TestCase):
    """Verify managed-store security and durability contracts."""

    def test_streams_large_generated_payload_without_unbounded_read(self) -> None:
        total_size = BUFFER_SIZE * 5 + 123
        stream = _GeneratedStream(total_size)
        with tempfile.TemporaryDirectory() as temp:
            store = KnowledgeManagedStore(Path(temp) / "managed")

            result = store.put_stream(stream)

            expected_hash = hashlib.sha256(b"x" * total_size).hexdigest()
            self.assertEqual(
                result.identity,
                ManagedObjectIdentity(expected_hash, total_size),
            )
            self.assertEqual(stream.largest_request, BUFFER_SIZE)
            self.assertEqual(result.outcome, ManagedStoreWriteOutcome.INSTALLED)

    def test_put_file_and_bytes_share_the_streaming_pool(self) -> None:
        payload = b"shared raw and normalised bytes"
        identity = ManagedObjectIdentity(
            hashlib.sha256(payload).hexdigest(),
            len(payload),
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.bin"
            source.write_bytes(payload)
            store = KnowledgeManagedStore(root / "managed")

            raw = store.put_file(source, identity)
            normalised = store.put_bytes(payload)

            self.assertEqual(raw.outcome, ManagedStoreWriteOutcome.INSTALLED)
            self.assertEqual(normalised.outcome, ManagedStoreWriteOutcome.REUSED)
            self.assertEqual(raw.storage_key, f"sha256:{identity.sha256}")
            self.assertEqual(raw.identity, normalised.identity)

    def test_accepts_logical_and_exact_legacy_keys(self) -> None:
        payload = b"legacy-compatible"
        with tempfile.TemporaryDirectory() as temp:
            store = KnowledgeManagedStore(Path(temp) / "managed")
            result = store.put_bytes(payload)
            digest = result.identity.sha256
            legacy = f"sha256/{digest[:2]}/{digest[2:4]}/{digest}"

            for key in (result.storage_key, legacy):
                with store.open_verified(key, result.identity) as stream:
                    self.assertEqual(stream.read(), payload)

    def test_rejects_malformed_and_mismatched_keys(self) -> None:
        digest = hashlib.sha256(b"payload").hexdigest()
        identity = ManagedObjectIdentity(digest, len(b"payload"))
        malformed = (
            "/etc/passwd",
            "../sha256/" + digest,
            f"sha256:{digest.upper()}",
            f"sha256/ff/{digest[2:4]}/{digest}",
            f"sha256\\{digest[:2]}\\{digest[2:4]}\\{digest}",
        )
        with tempfile.TemporaryDirectory() as temp:
            store = KnowledgeManagedStore(Path(temp) / "managed")
            for key in malformed:
                with self.subTest(key=key):
                    with self.assertRaisesRegex(
                        ManagedStoreError,
                        "storage key|Legacy managed",
                    ):
                        with store.open_verified(key, identity):
                            pass

    def test_open_verified_returns_the_descriptor_that_was_hashed(self) -> None:
        payload = b"verified inode"
        replacement = b"replacement"
        with tempfile.TemporaryDirectory() as temp:
            store = KnowledgeManagedStore(Path(temp) / "managed")
            result = store.put_bytes(payload)
            digest = result.identity.sha256
            object_path = (
                store.managed_root / "sha256" / digest[:2] / digest[2:4] / digest
            )

            with store.open_verified(result.storage_key, result.identity) as stream:
                original_inode = os.fstat(stream.fileno()).st_ino
                object_path.unlink()
                object_path.write_bytes(replacement)
                os.chmod(object_path, 0o600)
                self.assertNotEqual(original_inode, object_path.stat().st_ino)
                self.assertEqual(stream.read(), payload)

    def test_open_verified_rejects_hash_and_size_corruption(self) -> None:
        payload = b"registered managed payload"
        for replacement, reason_code in (
            (b"x" * len(payload), "MANAGED_OBJECT_HASH_MISMATCH"),
            (payload + b"x", "MANAGED_OBJECT_SIZE_MISMATCH"),
        ):
            with self.subTest(reason_code=reason_code):
                with tempfile.TemporaryDirectory() as temp:
                    store = KnowledgeManagedStore(Path(temp) / "managed")
                    result = store.put_bytes(payload)
                    digest = result.identity.sha256
                    object_path = (
                        store.managed_root
                        / "sha256"
                        / digest[:2]
                        / digest[2:4]
                        / digest
                    )
                    object_path.write_bytes(replacement)
                    object_path.chmod(0o600)

                    with self.assertRaises(ManagedStoreError) as raised:
                        with store.open_verified(
                            result.storage_key,
                            result.identity,
                        ):
                            pass

                    self.assertEqual(raised.exception.reason_code, reason_code)

    def test_open_verified_rejects_managed_object_symlink(self) -> None:
        payload = b"registered managed payload"
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            store = KnowledgeManagedStore(base / "managed")
            result = store.put_bytes(payload)
            digest = result.identity.sha256
            object_path = (
                store.managed_root / "sha256" / digest[:2] / digest[2:4] / digest
            )
            outside = base / "outside"
            outside.write_bytes(payload)
            object_path.unlink()
            object_path.symlink_to(outside)

            with self.assertRaises(ManagedStoreError) as raised:
                with store.open_verified(result.storage_key, result.identity):
                    pass

            self.assertEqual(raised.exception.reason_code, "MANAGED_OBJECT_SYMLINK")

    def test_rejects_root_symlink_and_unsafe_existing_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            target = base / "target"
            target.mkdir()
            link = base / "managed"
            link.symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(
                ManagedStoreConfigurationError,
                "symbolic link",
            ):
                KnowledgeManagedStore(link)

            unsafe = base / "unsafe"
            unsafe.mkdir(mode=0o775)
            os.chmod(unsafe, 0o775)
            with self.assertRaisesRegex(
                ManagedStoreConfigurationError,
                "permissions",
            ):
                KnowledgeManagedStore(unsafe)

    def test_created_modes_are_independent_of_umask(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            previous = os.umask(0)
            try:
                store = KnowledgeManagedStore(Path(temp) / "managed")
                result = store.put_bytes(b"mode")
            finally:
                os.umask(previous)
            digest = result.identity.sha256
            object_path = (
                store.managed_root / "sha256" / digest[:2] / digest[2:4] / digest
            )
            self.assertEqual(store.managed_root.stat().st_mode & 0o777, 0o750)
            self.assertEqual(
                (store.managed_root / ".tmp").stat().st_mode & 0o777,
                0o700,
            )
            self.assertEqual(object_path.stat().st_mode & 0o777, 0o600)

    def test_startup_rejects_unsupported_hard_links(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with patch(
                "orac_core.knowledge.managed_store.os.link",
                side_effect=OSError(errno.EOPNOTSUPP, "unsupported"),
            ):
                with self.assertRaises(ManagedStoreConfigurationError) as raised:
                    KnowledgeManagedStore(Path(temp) / "managed")
            self.assertEqual(raised.exception.reason_code, "STORE_HARDLINK_UNSUPPORTED")

    def test_startup_rejects_different_temporary_and_object_devices(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(
                KnowledgeManagedStore,
                "_stat_directory",
                side_effect=(
                    SimpleNamespace(st_dev=1),
                    SimpleNamespace(st_dev=2),
                ),
            ):
                with self.assertRaises(ManagedStoreConfigurationError) as raised:
                    KnowledgeManagedStore(Path(temp) / "managed")
            self.assertEqual(
                raised.exception.reason_code,
                "STORE_FILESYSTEM_MISMATCH",
            )

    def test_concurrent_streams_install_once_and_reuse_without_temp_leaks(
        self,
    ) -> None:
        payload = b"concurrent managed payload" * 4096
        with tempfile.TemporaryDirectory() as temp:
            store = KnowledgeManagedStore(Path(temp) / "managed")

            with ThreadPoolExecutor(max_workers=8) as executor:
                results = list(
                    executor.map(
                        lambda _index: store.put_bytes(payload),
                        range(16),
                    )
                )

            outcomes = [result.outcome for result in results]
            self.assertEqual(outcomes.count(ManagedStoreWriteOutcome.INSTALLED), 1)
            self.assertEqual(outcomes.count(ManagedStoreWriteOutcome.REUSED), 15)
            self.assertEqual(list((store.managed_root / ".tmp").iterdir()), [])

    def test_promotion_failure_cleans_owned_temporary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = KnowledgeManagedStore(Path(temp) / "managed")
            with patch(
                "orac_core.knowledge.managed_store.os.link",
                side_effect=OSError(errno.EOPNOTSUPP, "unsupported"),
            ):
                with self.assertRaises(ManagedStoreConfigurationError):
                    store.put_bytes(b"payload")
            self.assertEqual(list((store.managed_root / ".tmp").iterdir()), [])

    def test_temporary_fsync_failure_is_reason_coded_and_cleans(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = KnowledgeManagedStore(Path(temp) / "managed")
            real_fsync = os.fsync
            calls = 0

            def fail_first_fsync(file_descriptor: int) -> None:
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise OSError(errno.EIO, "injected fsync failure")
                real_fsync(file_descriptor)

            with patch(
                "orac_core.knowledge.managed_store.os.fsync",
                side_effect=fail_first_fsync,
            ):
                with self.assertRaises(ManagedStoreError) as raised:
                    store.put_bytes(b"payload")
            self.assertEqual(
                raised.exception.reason_code,
                "MANAGED_STORE_TRANSIENT_IO",
            )
            self.assertEqual(list((store.managed_root / ".tmp").iterdir()), [])

    def test_destination_fsync_failure_keeps_valid_object_for_retry(self) -> None:
        payload = b"durable retry"
        with tempfile.TemporaryDirectory() as temp:
            store = KnowledgeManagedStore(Path(temp) / "managed")
            digest = hashlib.sha256(payload).hexdigest()
            destination_directory = (
                store.managed_root / "sha256" / digest[:2] / digest[2:4]
            )
            destination_directory.mkdir(parents=True)
            for directory in (
                destination_directory.parent,
                destination_directory,
            ):
                directory.chmod(0o750)
            real_fsync = os.fsync
            calls = 0

            def fail_second_fsync(file_descriptor: int) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError(errno.EIO, "injected directory fsync failure")
                real_fsync(file_descriptor)

            with patch(
                "orac_core.knowledge.managed_store.os.fsync",
                side_effect=fail_second_fsync,
            ):
                with self.assertRaises(ManagedStoreError):
                    store.put_bytes(payload)

            retry = store.put_bytes(payload)
            self.assertEqual(retry.outcome, ManagedStoreWriteOutcome.REUSED)
            self.assertEqual(list((store.managed_root / ".tmp").iterdir()), [])

    def test_unlink_failure_has_stable_cleanup_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = KnowledgeManagedStore(Path(temp) / "managed")
            real_unlink = os.unlink

            def fail_capture_unlink(
                path: str | bytes,
                *,
                dir_fd: int | None = None,
            ) -> None:
                if str(path).startswith("capture-"):
                    raise OSError(errno.EIO, "injected unlink failure")
                real_unlink(path, dir_fd=dir_fd)

            with patch(
                "orac_core.knowledge.managed_store.os.unlink",
                side_effect=fail_capture_unlink,
            ):
                with self.assertRaises(ManagedStoreError) as raised:
                    store.put_bytes(b"payload")
            self.assertEqual(
                raised.exception.reason_code,
                "STORE_TEMP_CLEANUP_FAILED",
            )
            stale = list((store.managed_root / ".tmp").iterdir())
            self.assertEqual(len(stale), 1)
            stale[0].unlink()

    def test_hash_and_size_mismatch_leave_no_object_or_temporary(self) -> None:
        payload = b"payload"
        wrong = ManagedObjectIdentity("0" * 64, len(payload) + 1)
        with tempfile.TemporaryDirectory() as temp:
            store = KnowledgeManagedStore(Path(temp) / "managed")
            with self.assertRaises(ManagedStoreError) as raised:
                store.put_bytes(payload, wrong)
            self.assertEqual(
                raised.exception.reason_code,
                "MANAGED_OBJECT_SIZE_MISMATCH",
            )
            self.assertEqual(list((store.managed_root / ".tmp").iterdir()), [])
            self.assertEqual(
                list((store.managed_root / "sha256").rglob("*")),
                [],
            )


if __name__ == "__main__":
    unittest.main()
