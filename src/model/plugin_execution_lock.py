"""Coordinate maintenance with supported Orac execution on one governed host."""

# Author: Clive Bostock
# Date: 12-Sep-2026
# Description: Provides a stable shared/exclusive host execution lock.

from __future__ import annotations

import fcntl
import os
from pathlib import Path
import stat
from types import TracebackType


class PluginMaintenanceError(RuntimeError):
    """Raised when lifecycle maintenance cannot safely obtain exclusive access."""


class PluginExecutionLock:
    """Hold shared execution or exclusive maintenance access without waiting.

    Args:
        project_root: Governed host checkout used by all supported entrypoints.
        exclusive: Whether the caller mutates installation state.

    This lock is deliberately never unlinked; PID-file cleanup must not create
    a second lock inode. It does not provide distributed coordination.
    """

    def __init__(self, project_root: Path, *, exclusive: bool = False) -> None:
        self.path = project_root.absolute() / "var" / "plugins" / "execution.lock"
        self.exclusive = exclusive
        self._fd: int | None = None

    def __enter__(self) -> PluginExecutionLock:
        """Acquire the lock or fail before any lifecycle mutation."""
        if self._fd is not None:
            raise PluginMaintenanceError("Execution lock is already held.")
        # Walk with directory descriptors so neither a parent symlink nor a
        # concurrent path substitution can redirect this open to another lock.
        directory_fd = os.open(self.path.anchor, os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in self.path.parent.parts[1:]:
                if part == "..":
                    raise PluginMaintenanceError(
                        "Execution lock path must be canonical."
                    )
                try:
                    os.mkdir(part, mode=0o700, dir_fd=directory_fd)
                except FileExistsError:
                    pass
                child_fd = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=directory_fd,
                )
                os.close(directory_fd)
                directory_fd = child_fd
            fd = os.open(
                self.path.name,
                os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory_fd,
            )
        finally:
            os.close(directory_fd)
        try:
            identity = os.fstat(fd)
            if not stat.S_ISREG(identity.st_mode) or identity.st_nlink != 1:
                raise PluginMaintenanceError("Execution lock is not a regular file.")
            mode = fcntl.LOCK_EX if self.exclusive else fcntl.LOCK_SH
            try:
                fcntl.flock(fd, mode | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise PluginMaintenanceError(
                    "Plugin execution or maintenance is active. Stop governed "
                    "Orac runners before lifecycle maintenance; leave Oracle running."
                ) from exc
            self._fd = fd
            return self
        except BaseException:
            os.close(fd)
            raise

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Release access on success, failure or interruption."""
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
