"""Filesystem scanner for stable drop-box candidate files."""
# Author: Clive Bostock
# Date: 27-Jun-2026
# Description: Discovers stable files and hashes them without database coupling.

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from fnmatch import fnmatch
import hashlib
from pathlib import Path
from typing import Protocol

from .models import CandidateFile, DropLocation, FileObservation, HashedCandidate
from .models import ScanResult, datetime_from_mtime_ns

__author__ = "Clive Bostock"
__date__ = "27-Jun-2026"
__description__ = "Discovers stable files and hashes them without database coupling."


class FileSystem(Protocol):
    """Small filesystem protocol used to make scanner tests deterministic."""

    def stat(self, path: Path):
        """Return an os.stat_result-like object for ``path``."""

    def is_dir(self, path: Path) -> bool:
        """Return whether ``path`` is a directory."""

    def is_file(self, path: Path) -> bool:
        """Return whether ``path`` is a regular file."""

    def is_symlink(self, path: Path) -> bool:
        """Return whether ``path`` is a symbolic link."""

    def iterdir(self, path: Path) -> Iterable[Path]:
        """Yield direct children of ``path``."""

    def rglob(self, path: Path) -> Iterable[Path]:
        """Yield recursive descendants of ``path``."""

    def open_binary(self, path: Path):
        """Open ``path`` for binary reading."""


class LocalFileSystem:
    """Default filesystem implementation backed by ``pathlib``."""

    def stat(self, path: Path):
        """Return filesystem metadata for ``path``."""
        return path.stat()

    def is_dir(self, path: Path) -> bool:
        """Return whether ``path`` is a directory."""
        return path.is_dir()

    def is_file(self, path: Path) -> bool:
        """Return whether ``path`` is a regular file."""
        return path.is_file()

    def is_symlink(self, path: Path) -> bool:
        """Return whether ``path`` is a symbolic link."""
        return path.is_symlink()

    def iterdir(self, path: Path) -> Iterable[Path]:
        """Yield direct children of ``path``."""
        return path.iterdir()

    def rglob(self, path: Path) -> Iterable[Path]:
        """Yield recursive descendants of ``path``."""
        return path.rglob("*")

    def open_binary(self, path: Path):
        """Open ``path`` for binary reading."""
        return path.open("rb")


@dataclass(frozen=True)
class _ObservedState:
    size_bytes: int
    mtime_ns: int
    observed_at: datetime


class DropBoxScanner:
    """Discover candidate files and prove stability before hashing."""

    def __init__(
        self,
        *,
        filesystem: FileSystem | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Initialise the scanner."""
        self._filesystem = filesystem or LocalFileSystem()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._observations: dict[tuple[int, str], _ObservedState] = {}

    def scan_locations(self, locations: Iterable[DropLocation]) -> ScanResult:
        """Scan all enabled drop locations and return currently stable files."""
        result = ScanResult()
        for location in locations:
            self._scan_location(location, result)
        return result

    def hash_candidate(self, candidate: CandidateFile) -> HashedCandidate | None:
        """Hash a candidate and return ``None`` if it changed while hashing."""
        digest = hashlib.sha256()
        with self._filesystem.open_binary(candidate.observation.path) as file_handle:
            for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
                digest.update(chunk)

        latest = self._observe(candidate.observation.path)
        if (
            latest.size_bytes != candidate.observation.size_bytes
            or latest.mtime_ns != candidate.observation.mtime_ns
        ):
            return None
        return HashedCandidate(candidate=candidate, source_hash=digest.hexdigest())

    def _scan_location(self, location: DropLocation, result: ScanResult) -> None:
        if not self._filesystem.is_dir(location.path):
            result.missing_paths += 1
            return
        paths = (
            self._filesystem.rglob(location.path)
            if location.recursive
            else self._filesystem.iterdir(location.path)
        )
        for path in sorted(paths, key=lambda item: str(item)):
            if self._filesystem.is_symlink(path):
                result.skipped_symlink += 1
                continue
            if not self._filesystem.is_file(path):
                continue
            if self._is_ignored(path, location):
                result.skipped_ignored += 1
                continue
            if not self._extension_allowed(path, location.allowed_extensions):
                result.skipped_disallowed_type += 1
                continue

            observation = self._observe(path)
            result.observed_candidates += 1
            if (
                location.max_file_size_bytes is not None
                and observation.size_bytes > location.max_file_size_bytes
            ):
                result.skipped_too_large += 1
                continue
            if self._is_stable(location, observation):
                result.stable_candidates.append(
                    CandidateFile(location=location, observation=observation)
                )
            else:
                result.deferred_unstable += 1

    def _observe(self, path: Path) -> FileObservation:
        stat_result = self._filesystem.stat(path)
        mtime_ns = int(stat_result.st_mtime_ns)
        return FileObservation(
            path=path,
            size_bytes=int(stat_result.st_size),
            mtime_ns=mtime_ns,
            source_mtime=datetime_from_mtime_ns(mtime_ns),
            observed_at=self._clock(),
        )

    def _is_stable(self, location: DropLocation, observation: FileObservation) -> bool:
        key = (location.drop_location_id, str(observation.path))
        previous = self._observations.get(key)
        self._observations[key] = _ObservedState(
            size_bytes=observation.size_bytes,
            mtime_ns=observation.mtime_ns,
            observed_at=observation.observed_at,
        )
        if previous is None:
            return False
        if (
            previous.size_bytes != observation.size_bytes
            or previous.mtime_ns != observation.mtime_ns
        ):
            return False
        return (
            observation.observed_at - previous.observed_at
        ).total_seconds() >= location.stability_seconds

    @staticmethod
    def _extension_allowed(path: Path, allowed_extensions: tuple[str, ...]) -> bool:
        if not allowed_extensions:
            return True
        suffix = path.suffix.lower().lstrip(".")
        allowed = {item.lower().lstrip(".") for item in allowed_extensions}
        return suffix in allowed

    @staticmethod
    def _is_ignored(path: Path, location: DropLocation) -> bool:
        if path.name.startswith("."):
            return True
        relative = _relative_for_match(path, location.path)
        candidates = (path.name, relative)
        return any(
            fnmatch(candidate, pattern)
            for pattern in location.ignore_patterns
            for candidate in candidates
        )


def _relative_for_match(path: Path, root: Path) -> str:
    """Return a stable POSIX-like relative path for ignore pattern matching."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name
