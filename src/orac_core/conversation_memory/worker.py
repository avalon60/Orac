"""Scheduled materialisation worker for conversational memory checkpoints."""

# Author: Clive Bostock
# Date: 2026-08-28
# Description: Embeds source messages and creates immutable bounded summaries.

from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol

from model.plugin_routing.embeddings import EmbeddingProvider

from .embeddings import conversation_embedding_provider
from .repository import ConversationMemoryRepository


class ConversationSummariser(Protocol):
    """Narrow injectable summary provider contract."""

    @property
    def provider_id(self) -> str:
        """Return the provider identity recorded in checkpoint provenance."""

    @property
    def model_id(self) -> str:
        """Return the model/profile identity recorded in provenance."""

    def summarise(self, messages: tuple[dict[str, Any], ...]) -> str:
        """Return a bounded summary for ordered source messages."""


class DeterministicConversationSummariser:
    """Deterministic extractive Phase 1 summary provider."""

    provider_id = "orac-host"
    model_id = "deterministic-conversation-summary-v1"

    def __init__(self, *, max_chars: int = 12000) -> None:
        """Initialise the maximum immutable summary size."""
        self._max_chars = max(512, max_chars)

    def summarise(self, messages: tuple[dict[str, Any], ...]) -> str:
        """Preserve source wording while producing a bounded discovery aid."""
        lines = ["Conversation checkpoint (derived; verify against source messages):"]
        for message in messages:
            role = str(message["role"]).upper()
            text = str(message["content_text"]).strip()
            if text:
                lines.append(f"{role}: {text}")
        summary = "\n".join(lines)
        if len(summary) > self._max_chars:
            summary = summary[: self._max_chars - 1].rstrip() + "…"
        return summary


class ConversationMemoryMaterialisationService:
    """Process a bounded batch of durable conversation-memory requests."""

    def __init__(
        self,
        logger: Any | None = None,
        config_mgr: Any | None = None,
        manifest: Any | None = None,
        *,
        repository: ConversationMemoryRepository | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        summariser: ConversationSummariser | None = None,
    ) -> None:
        """Initialise the worker with configurable, injectable dependencies."""
        del manifest
        self._logger = logger
        self._config_mgr = config_mgr
        self._enabled = self._config_bool("enabled", False)
        self._repository = repository or ConversationMemoryRepository()
        self._embedding_provider = embedding_provider or conversation_embedding_provider(
            config_mgr
        )
        self._summariser = summariser or DeterministicConversationSummariser(
            max_chars=self._config_int("summary_max_chars", 12000)
        )
        self._checkpoint_exchange_count = max(
            1, self._config_int("checkpoint_exchange_count", 20)
        )
        self._batch_size = max(1, self._config_int("batch_size", 4))
        self._max_attempts = max(1, self._config_int("max_attempts", 5))
        self._prompt_version = self._config_value("prompt_version", "conversation-v1")
        self._profile = self._config_value(
            "materialisation_profile", "conversation-memory-v1"
        )
        self.last_error: str | None = None
        self.last_checkpoint_id: int | None = None

    def tick(self, context: Any) -> None:
        """Reconcile eligible ranges and process a bounded request batch."""
        del context
        self.last_error = None
        if not self._enabled:
            return
        self._repository.reconcile_eligible_ranges(
            checkpoint_exchange_count=self._checkpoint_exchange_count,
            materialisation_profile=self._profile,
            prompt_version=self._prompt_version,
            max_attempts=self._max_attempts,
        )
        for _index in range(self._batch_size):
            request_id = self._repository.next_request_id()
            if request_id is None:
                return
            try:
                self.last_checkpoint_id = self._process_request(request_id)
            except Exception as exc:
                self.last_error = str(exc)
                self._repository.record_failure(
                    request_id=request_id,
                    error_code="CONVERSATION_MEMORY_WORKER_ERROR",
                    error_message=str(exc),
                    retryable=True,
                )
                self._log_warning(
                    f"Conversation memory request {request_id} failed: {exc}"
                )

    def health(self, context: Any) -> bool:
        """Return whether the most recent worker tick was error free."""
        del context
        return self.last_error is None

    def _process_request(self, request_id: int) -> int:
        """Materialise one request without persisting intermediate stages."""
        rows = self._repository.load_request_sources(request_id)
        if not rows:
            raise LookupError("conversation memory request has no source messages")
        source_digest = _source_digest(rows)
        lineage: list[dict[str, Any]] = []
        for position, row in enumerate(rows, start=1):
            text = str(row["content_text"])
            content_sha256 = _sha256_text(text)
            vector = self._embedding_provider.embed_text(text)
            self._repository.ensure_message_embedding(
                request_id=request_id,
                message_id=int(row["message_id"]),
                source_row_version=int(row["row_version"]),
                source_content_sha256=content_sha256,
                source_text=text,
                embedding=vector,
                embedding_model=self._embedding_provider.model_id,
                embedding_provider="orac-host",
                token_count=_estimate_tokens(text),
            )
            lineage.append(
                {
                    "message_id": int(row["message_id"]),
                    "source_position": position,
                    "turn_index": int(row["turn_index"]),
                    "message_row_version": int(row["row_version"]),
                    "source_content_sha256": content_sha256,
                }
            )
        ordered_rows = tuple(rows)
        summary = self._summariser.summarise(ordered_rows)
        if not summary.strip():
            raise ValueError("conversation summariser returned empty text")
        summary_vector = self._embedding_provider.embed_text(summary)
        return self._repository.complete_request(
            request_id=request_id,
            source_digest=source_digest,
            summary_text=summary,
            summarisation_provider=self._summariser.provider_id,
            summarisation_model=self._summariser.model_id,
            summary_embedding=summary_vector,
            embedding_model=self._embedding_provider.model_id,
            embedding_provider="orac-host",
            source_lineage=lineage,
        )

    def _config_value(self, key: str, default: str) -> str:
        """Read one conversation-memory setting with a safe default."""
        manager = self._config_mgr
        if manager is None:
            return default
        return str(manager.config_value("conversation_memory", key, default=default))

    def _config_int(self, key: str, default: int) -> int:
        """Read one integer conversation-memory setting."""
        manager = self._config_mgr
        if manager is None:
            return default
        return int(manager.int_config_value("conversation_memory", key, default=default))

    def _config_bool(self, key: str, default: bool) -> bool:
        """Read one boolean conversation-memory setting."""
        manager = self._config_mgr
        if manager is None:
            return default
        return bool(manager.bool_config_value("conversation_memory", key, default=default))

    def _log_warning(self, message: str) -> None:
        """Emit a warning through the repository logger convention."""
        method = getattr(self._logger, "log_warning", None)
        if callable(method):
            method(message)


def _source_digest(rows: list[dict[str, Any]]) -> str:
    """Hash exact source identities, versions, roles, and content."""
    payload = [
        {
            "message_id": int(row["message_id"]),
            "turn_index": int(row["turn_index"]),
            "role": str(row["role"]),
            "row_version": int(row["row_version"]),
            "content_text": str(row["content_text"]),
        }
        for row in rows
    ]
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _sha256_text(text: str) -> str:
    """Return a lowercase SHA-256 digest for UTF-8 text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _estimate_tokens(text: str) -> int:
    """Return the Phase 1 conservative embedding token estimate."""
    return max(1, len(text.encode("utf-8")) // 4)
