"""Core-managed file capture for knowledge ingestion."""

# Author: Clive Bostock
# Date: 12-Jul-2026
# Description: Copies trusted source files into the Core content-addressed store.

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any

from .managed_store import KnowledgeManagedStore
from .managed_store import ManagedObjectIdentity
from .managed_store import ManagedStoreConfigurationError
from .managed_store import ManagedStoreError
from .managed_store import ManagedStoreWriteResult
from .managed_store import ManagedStoreWriteOutcome
from .models import DropBoxCaptureRequest, ManagedCaptureResult
from .repository import KnowledgeIngestionRepository

MAX_NORMALISED_BYTES = 50 * 1024 * 1024
NORMALISED_OUTPUT_MIME = "text/markdown; charset=utf-8"
DROP_BOX_EXTRACTORS = {
    "dropbox_markdown_passthrough",
    "dropbox_text_to_markdown",
    "dropbox_pandoc_gfm",
}
DROP_BOX_SOURCE_FORMATS = {
    "markdown": "text/markdown",
    "plain_text": "text/plain",
    "docx": (
        "application/vnd.openxmlformats-officedocument." "wordprocessingml.document"
    ),
    "html": "text/html",
    "odt": "application/vnd.oasis.opendocument.text",
    "rtf": "application/rtf",
    "epub": "application/epub+zip",
}
EXTRACTION_METADATA_FIELDS = {
    "schema_version",
    "producer_plugin_id",
    "drop_location_id",
    "drop_job_id",
    "source_format",
    "converter_name",
    "converter_version",
    "fixed_option_identifiers",
}


class KnowledgeCaptureError(RuntimeError):
    """Raised when Core cannot safely capture a source file."""


@dataclass(frozen=True)
class _OpenedDropBoxSource:
    """One authorised source descriptor and its stable provenance facts."""

    stream: Any
    relative_path: Path
    initial_stat: os.stat_result


class KnowledgeManagedFileCaptureService:
    """Capture source files into the Core-managed content-addressed store."""

    def __init__(
        self,
        *,
        managed_root: Path | None = None,
        managed_store: KnowledgeManagedStore | None = None,
        config_mgr: Any | None = None,
        repository: KnowledgeIngestionRepository | None = None,
        logger: Any | None = None,
    ) -> None:
        """Initialise the capture service."""
        if managed_store is not None and managed_root is not None:
            raise ValueError("Provide managed_store or managed_root, not both.")
        self._managed_store = managed_store or KnowledgeManagedStore.from_config(
            config_mgr,
            root_override=managed_root,
        )
        self._repository = repository or KnowledgeIngestionRepository()
        self._logger = logger
        self._max_file_size_bytes = 100 * 1024 * 1024

    @property
    def managed_root(self) -> Path:
        """Return the managed content root."""
        return self._managed_store.managed_root

    def capture_drop_box_file(
        self, request: DropBoxCaptureRequest
    ) -> ManagedCaptureResult:
        """Capture a Drop Box file, register it with Core, and return request id."""
        with self._open_source(request) as opened_source:
            request = self._upgrade_legacy_native_request(
                request,
                opened_source.stream,
            )
            mime_type = str(request.source_mime_type or "").strip()
            if not mime_type:
                raise KnowledgeCaptureError("Drop Box source MIME type is required.")
            if (
                DROP_BOX_SOURCE_FORMATS.get(str(request.source_format_code or ""))
                != mime_type
            ):
                raise KnowledgeCaptureError(
                    "Drop Box source format and MIME type are inconsistent."
                )
            self._validate_normalised_content(request)
            opened_source.stream.seek(0)
            write_result = self._put_raw_source(request, opened_source.stream)
            normalised_result = self._put_normalised_markdown(request)
            output_set_json = self._single_output_set_json(normalised_result)
            source_key = self._source_key(request, opened_source.relative_path)
        try:
            ingestion_request_id = self._repository.submit_managed_file(
                source_type="DROP_BOX",
                source_reference=self._source_reference(source_key),
                parent_source_reference=source_key,
                content_sha256=write_result.identity.sha256,
                content_uri=write_result.storage_key,
                mime_type=mime_type,
                original_filename=request.source_filename,
                byte_size=write_result.identity.byte_size,
                target_scope_type=request.target_scope_type,
                target_scope_key=request.target_scope_key,
                processing_profile_code=request.processing_profile,
                processing_instruction=request.processing_instruction,
                source_modified_on=request.source_mtime,
                legacy_parent_source_reference=request.legacy_source_key,
                source_format_code=request.source_format_code,
                normalised_markdown=request.normalised_markdown,
                normalised_text_sha256=request.normalised_text_sha256,
                normalised_byte_size=request.normalised_byte_size,
                output_mime_type=request.output_mime_type,
                extractor_code=request.extractor_code,
                extractor_version=request.extractor_version,
                extraction_metadata_json=request.extraction_metadata_json,
                classification_tags_json=request.classification_tags_json,
                output_set_json=output_set_json,
            )
        except Exception as exc:
            if "ORA-20409" in str(exc).upper():
                raise KnowledgeCaptureError(
                    "The requested knowledge scope is not available for capture."
                ) from exc
            raise
        status_code = "QUEUED"
        content_uri = write_result.storage_key
        detail_loader = getattr(self._repository, "request_detail", None)
        if callable(detail_loader):
            detail = detail_loader(ingestion_request_id)
            status_code = str(detail.get("status_code") or status_code)
            content_uri = str(detail.get("content_uri") or content_uri)
        return ManagedCaptureResult(
            ingestion_request_id=ingestion_request_id,
            content_uri=content_uri,
            content_sha256=write_result.identity.sha256,
            status_code=status_code,
            duplicate_payload=(write_result.outcome is ManagedStoreWriteOutcome.REUSED),
        )

    @contextmanager
    def _open_source(
        self,
        request: DropBoxCaptureRequest,
    ) -> Iterator[_OpenedDropBoxSource]:
        """Open one authorised, stable Drop Box source without symlink following."""
        root_path = Path(request.location_root).expanduser().absolute()
        source_path = Path(request.source_path).expanduser().absolute()
        try:
            relative = source_path.relative_to(root_path)
        except ValueError as exc:
            raise KnowledgeCaptureError(
                "Drop Box source path is outside the configured location root."
            ) from exc
        if not relative.parts or any(
            part in {"", ".", ".."} for part in relative.parts
        ):
            raise KnowledgeCaptureError("Drop Box source path is invalid.")
        if source_path.name != request.source_filename:
            raise KnowledgeCaptureError(
                "Drop Box source filename does not match the authorised source path."
            )
        if request.source_size_bytes < 0:
            raise KnowledgeCaptureError("Drop Box source file size is invalid.")
        if request.source_size_bytes > self._max_file_size_bytes:
            raise KnowledgeCaptureError(
                "Drop Box source file is larger than the Core capture limit."
            )
        try:
            root_fd = os.open(
                root_path,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            )
        except OSError as exc:
            raise KnowledgeCaptureError(
                "Drop Box source path could not be opened safely."
            ) from exc
        current_fd = root_fd
        source_fd: int | None = None
        try:
            for part in relative.parts[:-1]:
                next_fd = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=current_fd,
                )
                if current_fd != root_fd:
                    os.close(current_fd)
                current_fd = next_fd
            source_fd = os.open(
                relative.name,
                os.O_RDONLY | os.O_NOFOLLOW,
                dir_fd=current_fd,
            )
            source_stat = os.fstat(source_fd)
            if not stat.S_ISREG(source_stat.st_mode):
                raise KnowledgeCaptureError(
                    "Drop Box source path is not a regular file."
                )
            if source_stat.st_size != int(request.source_size_bytes):
                raise KnowledgeCaptureError(
                    "Drop Box source file size changed before capture."
                )
            with os.fdopen(source_fd, "rb", closefd=True) as stream:
                source_fd = None
                opened = _OpenedDropBoxSource(
                    stream=stream,
                    relative_path=relative,
                    initial_stat=source_stat,
                )
                yield opened
                final_stat = os.fstat(stream.fileno())
                fingerprint = (
                    "st_dev",
                    "st_ino",
                    "st_size",
                    "st_mtime_ns",
                )
                if any(
                    getattr(final_stat, field) != getattr(source_stat, field)
                    for field in fingerprint
                ):
                    raise KnowledgeCaptureError(
                        "Drop Box source file changed during capture."
                    )
        except OSError as exc:
            raise KnowledgeCaptureError(
                "Drop Box source path could not be opened safely."
            ) from exc
        finally:
            if source_fd is not None:
                os.close(source_fd)
            if current_fd != root_fd:
                os.close(current_fd)
            os.close(root_fd)

    def _put_raw_source(
        self,
        request: DropBoxCaptureRequest,
        source_stream: Any,
    ) -> ManagedStoreWriteResult:
        """Store a raw source stream using its mandatory observed identity."""
        try:
            identity = ManagedObjectIdentity(
                request.source_sha256.lower().strip(),
                int(request.source_size_bytes),
            )
            return self._managed_store.put_stream(source_stream, identity)
        except ManagedStoreConfigurationError:
            raise
        except (ManagedStoreError, ValueError) as exc:
            raise KnowledgeCaptureError(
                "Captured file does not match the authorised source identity."
            ) from exc

    def _put_normalised_markdown(
        self,
        request: DropBoxCaptureRequest,
    ) -> ManagedStoreWriteResult:
        """Store canonical Markdown under its producer-supplied identity."""
        try:
            payload = str(request.normalised_markdown).encode("utf-8")
            identity = ManagedObjectIdentity(
                str(request.normalised_text_sha256).lower().strip(),
                int(request.normalised_byte_size),
            )
            return self._managed_store.put_bytes(payload, identity)
        except (ManagedStoreError, ValueError, TypeError) as exc:
            raise KnowledgeCaptureError(
                "Canonical Markdown does not match its managed identity."
            ) from exc

    @staticmethod
    def _single_output_set_json(
        result: ManagedStoreWriteResult,
    ) -> str:
        """Build the version-one single-member registration envelope."""
        return json.dumps(
            {
                "schema_version": 1,
                "set_kind": "SINGLE",
                "members": [
                    {
                        "role": "PRIMARY",
                        "media_type": NORMALISED_OUTPUT_MIME,
                        "content_sha256": result.identity.sha256,
                        "storage_key": result.storage_key,
                        "byte_size": result.identity.byte_size,
                        "logical_name": "primary.md",
                        "ordinal": 1,
                        "metadata": None,
                    }
                ],
            },
            separators=(",", ":"),
            sort_keys=True,
        )

    def _validate_normalised_content(self, request: DropBoxCaptureRequest) -> None:
        text = request.normalised_markdown
        if text is None or not text.strip():
            raise KnowledgeCaptureError("Canonical Markdown is required.")
        if text.startswith("\ufeff") or "\r" in text or not text.endswith("\n"):
            raise KnowledgeCaptureError(
                "Canonical Markdown must not contain a BOM or CR and must end with LF."
            )
        try:
            encoded = text.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise KnowledgeCaptureError(
                "Canonical Markdown contains invalid Unicode."
            ) from exc
        if len(encoded) > MAX_NORMALISED_BYTES:
            raise KnowledgeCaptureError("Canonical Markdown exceeds 50 MiB.")
        if request.normalised_byte_size != len(encoded):
            raise KnowledgeCaptureError("Canonical Markdown byte size is inconsistent.")
        digest = hashlib.sha256(encoded).hexdigest()
        if digest != str(request.normalised_text_sha256 or "").lower():
            raise KnowledgeCaptureError("Canonical Markdown hash is inconsistent.")
        if request.output_mime_type != NORMALISED_OUTPUT_MIME:
            raise KnowledgeCaptureError(
                "Canonical Markdown output MIME type is invalid."
            )
        if request.extractor_code not in DROP_BOX_EXTRACTORS:
            raise KnowledgeCaptureError("Drop Box extractor identity is invalid.")
        if request.extractor_version != "1":
            raise KnowledgeCaptureError("Drop Box extractor version is unsupported.")
        if len((request.extraction_metadata_json or "").encode("utf-8")) > 16 * 1024:
            raise KnowledgeCaptureError("Extraction metadata exceeds 16 KiB.")
        self._validate_extraction_metadata(request)
        self._validate_classification_tags(request)
        if len((request.processing_instruction or "").encode("utf-8")) > 16 * 1024:
            raise KnowledgeCaptureError("Ingestion notes exceed 16 KiB.")

    @staticmethod
    def _validate_extraction_metadata(request: DropBoxCaptureRequest) -> None:
        """Validate the bounded producer-owned extraction provenance shape."""
        try:
            metadata = json.loads(request.extraction_metadata_json or "")
        except (json.JSONDecodeError, TypeError) as exc:
            raise KnowledgeCaptureError(
                "Extraction metadata must be valid JSON."
            ) from exc
        if not isinstance(metadata, dict):
            raise KnowledgeCaptureError("Extraction metadata must be an object.")
        unknown = set(metadata) - EXTRACTION_METADATA_FIELDS
        if unknown:
            raise KnowledgeCaptureError(
                "Extraction metadata contains unsupported fields."
            )
        if (
            metadata.get("schema_version") != 1
            or metadata.get("producer_plugin_id") != "drop_box"
            or metadata.get("drop_location_id") != request.drop_location_id
            or metadata.get("drop_job_id") != request.drop_job_id
            or metadata.get("source_format") != request.source_format_code
        ):
            raise KnowledgeCaptureError(
                "Extraction metadata does not match the Drop Box handoff."
            )
        option_ids = metadata.get("fixed_option_identifiers")
        if not isinstance(option_ids, list) or any(
            not isinstance(value, str) for value in option_ids
        ):
            raise KnowledgeCaptureError(
                "Extraction fixed-option identifiers are invalid."
            )

    @staticmethod
    def _validate_classification_tags(request: DropBoxCaptureRequest) -> None:
        """Validate Drop Box tag JSON before the database active-tag check."""
        payload = request.classification_tags_json
        if payload is None or len(payload.encode("utf-8")) > 4096:
            raise KnowledgeCaptureError(
                "Drop Box requires bounded classification tag JSON."
            )
        try:
            tags = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise KnowledgeCaptureError(
                "Classification tags must be valid JSON."
            ) from exc
        if (
            not isinstance(tags, list)
            or not 1 <= len(tags) <= 10
            or any(
                not isinstance(tag, str)
                or not tag
                or not tag.isascii()
                or not tag[0].isalpha()
                or tag != tag.upper()
                or any(
                    not (
                        character.isupper()
                        or character.isdigit()
                        or character == "_"
                    )
                    for character in tag
                )
                for tag in tags
            )
            or len(set(tags)) != len(tags)
        ):
            raise KnowledgeCaptureError(
                "Drop Box requires one to ten distinct uppercase DOC_CLASS codes."
            )

    def _upgrade_legacy_native_request(
        self,
        request: DropBoxCaptureRequest,
        source_stream: Any,
    ) -> DropBoxCaptureRequest:
        """Supply canonical native content for an already queued legacy request."""
        if request.normalised_markdown is not None:
            return request
        suffix = Path(request.source_filename).suffix.lower()
        if suffix not in {".md", ".txt"}:
            raise KnowledgeCaptureError(
                "Legacy Drop Box requests without canonical Markdown are limited "
                "to Markdown and plain text."
            )
        payload = source_stream.read()
        if payload.startswith(b"\xef\xbb\xbf"):
            payload = payload[3:]
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise KnowledgeCaptureError(
                "Legacy Drop Box Markdown/text must be valid UTF-8."
            ) from exc
        if "\x00" in text:
            raise KnowledgeCaptureError(
                "Legacy Drop Box Markdown/text contains a NUL character."
            )
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        if not text.endswith("\n"):
            text += "\n"
        if not text.strip():
            raise KnowledgeCaptureError(
                "Legacy Drop Box Markdown/text is empty or whitespace-only."
            )
        encoded = text.encode("utf-8")
        extractor_code = (
            "dropbox_markdown_passthrough"
            if suffix == ".md"
            else "dropbox_text_to_markdown"
        )
        source_format = "markdown" if suffix == ".md" else "plain_text"
        mime_type = "text/markdown" if suffix == ".md" else "text/plain"
        return DropBoxCaptureRequest(
            **{
                **request.__dict__,
                "source_format_code": source_format,
                "source_mime_type": mime_type,
                "normalised_markdown": text,
                "normalised_text_sha256": hashlib.sha256(encoded).hexdigest(),
                "normalised_byte_size": len(encoded),
                "output_mime_type": NORMALISED_OUTPUT_MIME,
                "extractor_code": extractor_code,
                "extractor_version": "1",
                "extraction_metadata_json": json.dumps(
                    {
                        "schema_version": 1,
                        "producer_plugin_id": "drop_box",
                        "drop_location_id": request.drop_location_id,
                        "drop_job_id": request.drop_job_id,
                        "source_format": source_format,
                        "fixed_option_identifiers": ["legacy_native_transition_v1"],
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                ),
                "classification_tags_json": request.classification_tags_json,
            }
        )

    def _source_key(self, request: DropBoxCaptureRequest, relative: Path) -> str:
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

    def _log_warning(self, message: str) -> None:
        if self._logger is not None and hasattr(self._logger, "log_warning"):
            self._logger.log_warning(message)
