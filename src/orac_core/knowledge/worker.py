"""Scheduled worker for Core knowledge ingestion requests."""

# Author: Clive Bostock
# Date: 12-Jul-2026
# Description: Extracts, chunks, embeds, and completes Core knowledge requests.

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import socket
from typing import Any

from lib.fsutils import project_home
from model.plugin_routing.embeddings import EmbeddingProvider, HashEmbeddingProvider

from .repository import KnowledgeIngestionRepository

EXTRACTOR_CODE = "core_text_v1"
EXTRACTOR_VERSION = "1"
CHUNKER_CODE = "core_word_window"
CHUNKER_VERSION = "1"


@dataclass(frozen=True)
class TextChunk:
    """One extracted text chunk with source character offsets."""

    chunk_no: int
    span_start: int
    span_end: int
    text: str
    token_count: int


class KnowledgeIngestionService:
    """Scheduled service that processes Core knowledge ingestion requests."""

    def __init__(
        self,
        logger: Any | None = None,
        config_mgr: Any | None = None,
        manifest: Any | None = None,
        *,
        repository: KnowledgeIngestionRepository | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        managed_root: Path | None = None,
    ) -> None:
        """Initialise the worker with injectable dependencies."""
        self._logger = logger
        self._config_mgr = config_mgr
        self._manifest = manifest
        self._repository = repository or KnowledgeIngestionRepository()
        self._managed_root = (
            Path(managed_root)
            if managed_root
            else self._config_path(
                "managed_root",
                project_home() / "var" / "knowledge" / "content",
            )
        )
        chunk_size = self._config_int("chunk_size_tokens", 384)
        overlap = self._config_int("chunk_overlap_tokens", 48)
        dimensions = self._config_int("embedding_dimensions", 32)
        model_id = self._config_value("embedding_model_id", "hash-embedding-v1")
        self._chunk_size_tokens = max(1, chunk_size)
        self._overlap_tokens = max(0, min(overlap, self._chunk_size_tokens - 1))
        self._embedding_provider = embedding_provider or HashEmbeddingProvider(
            model_id=model_id,
            dimensions=dimensions,
        )
        self._lease_seconds = self._config_int("request_lease_seconds", 300)
        self._batch_size = max(1, self._config_int("batch_size", 5))
        self._owner_id = f"knowledge:{socket.gethostname()}:{os.getpid()}"
        self.last_processed_request_id: int | None = None
        self.last_error: str | None = None

    def tick(self, context: Any) -> None:
        """Process a bounded batch of available ingestion requests."""
        del context
        first_error: str | None = None
        processed = 0
        for _index in range(self._batch_size):
            request_id = self._repository.try_claim_next_request(
                owner_id=self._owner_id,
                lease_seconds=self._lease_seconds,
            )
            if request_id is None:
                break
            processed += 1
            self.last_processed_request_id = request_id
            detail = self._repository.request_detail(request_id)
            owner_id = str(detail["lease_owner"])
            lease_token = str(detail["lease_token"])
            try:
                self._process_request(
                    detail, owner_id=owner_id, lease_token=lease_token
                )
            except Exception as exc:
                if first_error is None:
                    first_error = str(exc)
                self._fail_request(
                    request_id=request_id,
                    owner_id=owner_id,
                    lease_token=lease_token,
                    error_code="KNOWLEDGE_WORKER_ERROR",
                    error_message=str(exc),
                    retryable=True,
                )
                self._log_warning(
                    f"Knowledge ingestion request {request_id} failed: {exc}"
                )
        self.last_error = first_error if processed else None

    def health(self, context: Any) -> bool:
        """Return whether the last worker tick finished without an error."""
        del context
        return self.last_error is None

    def _process_request(
        self,
        detail: dict[str, Any],
        *,
        owner_id: str,
        lease_token: str,
    ) -> None:
        request_id = int(detail["ingestion_request_id"])
        content_uri = str(detail["content_uri"])
        payload_path = self._managed_root / content_uri
        if not payload_path.is_file():
            self._fail_request(
                request_id=request_id,
                owner_id=owner_id,
                lease_token=lease_token,
                error_code="MISSING_MANAGED_PAYLOAD",
                error_message=f"Managed payload is missing: {content_uri}",
                retryable=True,
            )
            return
        if _sha256_file(payload_path) != str(detail["content_sha256"]).lower():
            raise RuntimeError(
                "Managed payload hash no longer matches the registered source object."
            )

        self._repository.mark_stage(
            ingestion_request_id=request_id,
            owner_id=owner_id,
            lease_token=lease_token,
            status="PROCESSING",
            stage="EXTRACT",
        )
        text = payload_path.read_text(encoding="utf-8")
        if not text.strip():
            self._fail_request(
                request_id=request_id,
                owner_id=owner_id,
                lease_token=lease_token,
                error_code="EMPTY_MANAGED_PAYLOAD",
                error_message="Managed Markdown/text payload is empty or whitespace-only.",
                retryable=False,
            )
            return
        text_sha = _sha256_text(text)
        document_version_id = self._repository.ensure_document_version(
            ingestion_request_id=request_id,
            title=str(detail.get("original_filename") or ""),
            source_modified_on=detail.get("source_modified_on"),
        )
        extraction_id = self._repository.create_extraction(
            document_version_id=document_version_id,
            extractor_code=EXTRACTOR_CODE,
            extractor_version=EXTRACTOR_VERSION,
            extracted_text=text,
            text_sha256=text_sha,
        )

        self._repository.mark_stage(
            ingestion_request_id=request_id,
            owner_id=owner_id,
            lease_token=lease_token,
            status="PROCESSING",
            stage="CHUNK",
        )
        chunks = chunk_text(
            text,
            chunk_size_tokens=self._chunk_size_tokens,
            overlap_tokens=self._overlap_tokens,
        )
        chunk_set_id = self._repository.create_chunk_set(
            extraction_id=extraction_id,
            chunker_code=CHUNKER_CODE,
            chunker_version=CHUNKER_VERSION,
            chunk_size_tokens=self._chunk_size_tokens,
            overlap_tokens=self._overlap_tokens,
        )
        chunk_ids: list[tuple[int, TextChunk]] = []
        for chunk in chunks:
            chunk_id = self._repository.insert_chunk(
                chunk_set_id=chunk_set_id,
                chunk_no=chunk.chunk_no,
                span_start=chunk.span_start,
                span_end=chunk.span_end,
                chunk_text=chunk.text,
                token_count=chunk.token_count,
                content_sha256=_sha256_text(chunk.text),
            )
            chunk_ids.append((chunk_id, chunk))

        self._repository.mark_stage(
            ingestion_request_id=request_id,
            owner_id=owner_id,
            lease_token=lease_token,
            status="PROCESSING",
            stage="EMBED",
        )
        vectors = self._embedding_provider.embed_texts(
            [chunk.text for _, chunk in chunk_ids]
        )
        dimensions = (
            len(vectors[0]) if vectors else self._config_int("embedding_dimensions", 32)
        )
        embedding_model_id = self._repository.upsert_embedding_model(
            provider_code="hash",
            model_name=self._embedding_provider.model_id,
            model_revision="default",
            dimensions=dimensions,
        )
        for (chunk_id, chunk), vector in zip(chunk_ids, vectors, strict=True):
            self._repository.insert_embedding(
                chunk_id=chunk_id,
                embedding_model_id=embedding_model_id,
                vector=vector,
                embedding_text_sha256=_sha256_text(chunk.text),
            )

        self._repository.complete_request(
            ingestion_request_id=request_id,
            owner_id=owner_id,
            lease_token=lease_token,
        )

    def _fail_request(
        self,
        *,
        request_id: int,
        owner_id: str,
        lease_token: str,
        error_code: str,
        error_message: str,
        retryable: bool,
    ) -> None:
        try:
            self._repository.fail_request(
                ingestion_request_id=request_id,
                owner_id=owner_id,
                lease_token=lease_token,
                error_code=error_code,
                error_message=error_message,
                retryable=retryable,
            )
        except Exception as exc:
            self._log_warning(
                f"Could not mark knowledge request {request_id} failed: {exc}"
            )

    def _config_value(self, key: str, default: str) -> str:
        if self._config_mgr is None:
            return default
        return str(self._config_mgr.config_value("knowledge", key, default=default))

    def _config_int(self, key: str, default: int) -> int:
        if self._config_mgr is None:
            return default
        return int(self._config_mgr.int_config_value("knowledge", key, default=default))

    def _config_path(self, key: str, default: Path) -> Path:
        if self._config_mgr is None:
            return default
        raw = self._config_mgr.config_value("knowledge", key, default=str(default))
        return Path(raw)

    def _log_warning(self, message: str) -> None:
        if self._logger is not None and hasattr(self._logger, "log_warning"):
            self._logger.log_warning(message)


def chunk_text(
    text: str,
    *,
    chunk_size_tokens: int,
    overlap_tokens: int,
) -> list[TextChunk]:
    """Split text into word-window chunks with stable character spans."""
    matches = list(re.finditer(r"\S+", text))
    if not matches:
        return []
    chunks: list[TextChunk] = []
    step = max(1, chunk_size_tokens - overlap_tokens)
    chunk_no = 1
    for start_index in range(0, len(matches), step):
        end_index = min(len(matches), start_index + chunk_size_tokens)
        span_start = matches[start_index].start()
        span_end = matches[end_index - 1].end()
        chunks.append(
            TextChunk(
                chunk_no=chunk_no,
                span_start=span_start,
                span_end=span_end,
                text=text[span_start:span_end],
                token_count=end_index - start_index,
            )
        )
        chunk_no += 1
        if end_index == len(matches):
            break
    return chunks


def _sha256_text(text: str) -> str:
    """Return the SHA-256 of UTF-8 text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 of a local file."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
