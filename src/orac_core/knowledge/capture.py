"""Core-managed file capture for knowledge ingestion."""

# Author: Clive Bostock
# Date: 12-Jul-2026
# Description: Copies trusted source files into the Core content-addressed store.

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

from lib.fsutils import project_home

from .models import DropBoxCaptureRequest, ManagedCaptureResult
from .repository import KnowledgeIngestionRepository

SUPPORTED_SUFFIXES = {".txt": "text/plain", ".md": "text/markdown"}


class KnowledgeCaptureError(RuntimeError):
    """Raised when Core cannot safely capture a source file."""


class KnowledgeManagedFileCaptureService:
    """Capture source files into the Core-managed content-addressed store."""

    def __init__(
        self,
        *,
        managed_root: Path | None = None,
        repository: KnowledgeIngestionRepository | None = None,
        logger: Any | None = None,
    ) -> None:
        """Initialise the capture service."""
        self._managed_root = (
            Path(managed_root)
            if managed_root
            else (project_home() / "var" / "knowledge" / "content")
        )
        self._repository = repository or KnowledgeIngestionRepository()
        self._logger = logger
        self._max_file_size_bytes = 100 * 1024 * 1024

    @property
    def managed_root(self) -> Path:
        """Return the managed content root."""
        return self._managed_root

    def capture_drop_box_file(
        self, request: DropBoxCaptureRequest
    ) -> ManagedCaptureResult:
        """Capture a Drop Box file, register it with Core, and return request id."""
        source_path = self._validate_source_path(request)
        mime_type = self._mime_type_for(source_path)
        temp_path: Path | None = None
        retain_temp = False
        try:
            temp_path, copied_sha = self._copy_to_temp(source_path)
            supplied_sha = request.source_sha256.lower().strip()
            if copied_sha != supplied_sha:
                raise KnowledgeCaptureError(
                    "Captured file hash does not match the Drop Box job hash."
                )
            self._validate_utf8(temp_path)
            existed_before_install = self._content_path(copied_sha).exists()
            content_uri = self._install_temp_file(temp_path, copied_sha)
            if not existed_before_install:
                temp_path = None
            source_key = self._source_key(request, source_path)
            try:
                ingestion_request_id = self._repository.submit_managed_file(
                    source_type="DROP_BOX",
                    source_reference=self._source_reference(source_key),
                    parent_source_reference=source_key,
                    content_sha256=copied_sha,
                    content_uri=content_uri,
                    mime_type=mime_type,
                    original_filename=request.source_filename,
                    byte_size=request.source_size_bytes,
                    target_scope_type=request.target_scope_type,
                    target_scope_key=request.target_scope_key,
                    processing_profile_code=request.processing_profile,
                    processing_instruction=request.processing_instruction,
                    source_modified_on=request.source_mtime,
                    legacy_parent_source_reference=request.legacy_source_key,
                )
            except Exception as exc:
                if "ORA-20409" in str(exc).upper():
                    raise KnowledgeCaptureError(
                        "The requested knowledge scope is not available for capture."
                    ) from exc
                raise
            status_code = "QUEUED"
            status_loader = getattr(self._repository, "request_status", None)
            if callable(status_loader):
                status_code = str(status_loader(ingestion_request_id))
            return ManagedCaptureResult(
                ingestion_request_id=ingestion_request_id,
                content_uri=content_uri,
                content_sha256=copied_sha,
                status_code=status_code,
                duplicate_payload=existed_before_install,
            )
        finally:
            if temp_path is not None and not retain_temp:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    self._log_warning(
                        f"Could not remove temporary capture file: {temp_path}"
                    )

    def _validate_source_path(self, request: DropBoxCaptureRequest) -> Path:
        root = Path(request.location_root).expanduser().resolve(strict=True)
        source = Path(request.source_path).expanduser().resolve(strict=True)
        try:
            source.relative_to(root)
        except ValueError as exc:
            raise KnowledgeCaptureError(
                "Drop Box source path is outside the configured location root."
            ) from exc
        if not source.is_file():
            raise KnowledgeCaptureError("Drop Box source path is not a regular file.")
        if source.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise KnowledgeCaptureError("Drop Box source file type is not supported.")
        if request.source_size_bytes < 0:
            raise KnowledgeCaptureError("Drop Box source file size is invalid.")
        if request.source_size_bytes > self._max_file_size_bytes:
            raise KnowledgeCaptureError(
                "Drop Box source file is larger than the Core capture limit."
            )
        actual_size = source.stat().st_size
        if actual_size != int(request.source_size_bytes):
            raise KnowledgeCaptureError(
                "Drop Box source file size changed before capture."
            )
        return source

    def _copy_to_temp(self, source_path: Path) -> tuple[Path, str]:
        temp_dir = self._managed_root / ".tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        hasher = hashlib.sha256()
        fd, temp_name = tempfile.mkstemp(prefix="capture-", suffix=".tmp", dir=temp_dir)
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as output:
                with source_path.open("rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        hasher.update(chunk)
                        output.write(chunk)
            return temp_path, hasher.hexdigest()
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

    def _validate_utf8(self, path: Path) -> None:
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise KnowledgeCaptureError(
                "Drop Box source file is not valid UTF-8."
            ) from exc

    def _install_temp_file(self, temp_path: Path, content_sha256: str) -> str:
        destination = self._content_path(content_sha256)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if self._sha256_file(destination) != content_sha256:
                raise KnowledgeCaptureError(
                    "Existing managed file hash is inconsistent."
                )
            return self._content_uri(content_sha256)
        shutil.move(str(temp_path), str(destination))
        if self._sha256_file(destination) != content_sha256:
            destination.unlink(missing_ok=True)
            raise KnowledgeCaptureError(
                "Managed file hash verification failed after rename."
            )
        return self._content_uri(content_sha256)

    def _content_uri(self, content_sha256: str) -> str:
        return f"sha256/{content_sha256[0:2]}/{content_sha256[2:4]}/{content_sha256}"

    def _content_path(self, content_sha256: str) -> Path:
        return self._managed_root / self._content_uri(content_sha256)

    def _source_key(self, request: DropBoxCaptureRequest, source_path: Path) -> str:
        root = Path(request.location_root).expanduser().resolve(strict=True)
        relative = source_path.resolve(strict=True).relative_to(root)
        location_code = (request.location_code or str(request.drop_location_id)).strip()
        if not location_code:
            raise KnowledgeCaptureError(
                "Drop Box location code is required for source identity."
            )
        return f"{location_code}:{relative.as_posix()}"

    @staticmethod
    def _source_reference(source_key: str) -> str:
        digest = hashlib.sha256(source_key.encode("utf-8")).hexdigest()
        return f"drop_box:source:{digest}"

    @staticmethod
    def _mime_type_for(path: Path) -> str:
        return SUPPORTED_SUFFIXES[path.suffix.lower()]

    @staticmethod
    def _sha256_file(path: Path) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _log_warning(self, message: str) -> None:
        if self._logger is not None and hasattr(self._logger, "log_warning"):
            self._logger.log_warning(message)
