"""Database repository for conversational-memory materialisation and retrieval."""

# Author: Clive Bostock
# Date: 2026-08-28
# Description: Calls the least-privilege ORAC_CODE conversation memory API.

from __future__ import annotations

import json
from typing import Any, Callable

import oracledb

from orac_core.knowledge.repository import default_orac_session


_TEXT_FIELDS = frozenset(
    {
        "content_text",
        "summary_text",
        "summary_embedding",
        "source_text",
        "embedding",
    }
)


class ConversationMemoryRepository:
    """Thin runtime wrapper around the governed conversation-memory package."""

    _PACKAGE = "orac_code.conversation_memory_api"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any] | None = None,
    ) -> None:
        """Initialise the repository with an injectable session factory."""
        self._session_factory = session_factory or default_orac_session

    def reconcile_eligible_ranges(
        self,
        *,
        checkpoint_exchange_count: int,
        materialisation_profile: str,
        prompt_version: str,
        max_attempts: int,
    ) -> int:
        """Idempotently enqueue all currently eligible checkpoint ranges."""
        return int(
            self._call_function(
                "reconcile_eligible_ranges",
                int,
                [
                    checkpoint_exchange_count,
                    materialisation_profile,
                    prompt_version,
                    max_attempts,
                ],
            )
            or 0
        )

    def next_request_id(self) -> int | None:
        """Return the next pending or retryable request for the singleton worker."""
        value = self._call_function("next_request_id", int, [])
        return int(value) if value is not None else None

    def load_request_sources(self, request_id: int) -> list[dict[str, Any]]:
        """Load one request and its authoritative ordered source messages."""
        return self._call_cursor("open_request_sources", [int(request_id)])

    def ensure_message_embedding(
        self,
        *,
        request_id: int,
        message_id: int,
        source_row_version: int,
        source_content_sha256: str,
        source_text: str,
        embedding: list[float],
        embedding_model: str,
        embedding_provider: str,
        token_count: int,
    ) -> None:
        """Create or validate the pinned Phase 1 embedding for one message."""
        self._call_procedure(
            "ensure_message_embedding",
            [
                request_id,
                message_id,
                source_row_version,
                source_content_sha256,
                source_text,
                json.dumps(embedding, separators=(",", ":")),
                embedding_model,
                embedding_provider,
                token_count,
            ],
        )

    def complete_request(
        self,
        *,
        request_id: int,
        source_digest: str,
        summary_text: str,
        summarisation_provider: str,
        summarisation_model: str,
        summary_embedding: list[float],
        embedding_model: str,
        embedding_provider: str,
        source_lineage: list[dict[str, Any]],
    ) -> int:
        """Atomically persist an immutable checkpoint and exact lineage."""
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                checkpoint_var = cursor.var(oracledb.DB_TYPE_NUMBER)
                cursor.callproc(
                    f"{self._PACKAGE}.complete_request",
                    [
                        request_id,
                        source_digest,
                        summary_text,
                        summarisation_provider,
                        summarisation_model,
                        json.dumps(summary_embedding, separators=(",", ":")),
                        embedding_model,
                        embedding_provider,
                        len(summary_embedding),
                        json.dumps(source_lineage, separators=(",", ":")),
                        checkpoint_var,
                    ],
                )
                checkpoint_id = checkpoint_var.getvalue()
            session.commit()
            if checkpoint_id is None:
                raise RuntimeError("conversation memory completion returned no checkpoint")
            return int(checkpoint_id)
        finally:
            _close_quietly(session)

    def record_failure(
        self,
        *,
        request_id: int,
        error_code: str,
        error_message: str,
        retryable: bool,
    ) -> None:
        """Record a bounded retryable or terminal materialisation failure."""
        self._call_procedure(
            "record_failure",
            [
                request_id,
                error_code[:100],
                error_message[:1000],
                "Y" if retryable else "N",
            ],
        )

    def load_summary_candidates(
        self,
        *,
        principal_username: str,
        embedding_model: str,
        embedding_dimensions: int,
        candidate_limit: int,
    ) -> list[dict[str, Any]]:
        """Load bounded checkpoint candidates owned by one principal."""
        return self._call_cursor(
            "open_summary_candidates",
            [
                principal_username,
                embedding_model,
                embedding_dimensions,
                candidate_limit,
            ],
        )

    def load_source_candidates(
        self,
        *,
        principal_username: str,
        checkpoint_ids: tuple[int, ...],
        embedding_model: str,
        embedding_dimensions: int,
        candidate_limit: int,
    ) -> list[dict[str, Any]]:
        """Load supporting source messages for authorised checkpoints."""
        return self._call_cursor(
            "open_source_candidates",
            [
                principal_username,
                json.dumps(checkpoint_ids, separators=(",", ":")),
                embedding_model,
                embedding_dimensions,
                candidate_limit,
            ],
        )

    def _call_function(
        self,
        name: str,
        return_type: Any,
        inputs: list[Any],
    ) -> Any:
        """Call one package function and commit its transaction."""
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                value = cursor.callfunc(
                    f"{self._PACKAGE}.{name}",
                    return_type,
                    inputs,
                )
            session.commit()
            return value
        finally:
            _close_quietly(session)

    def _call_procedure(self, name: str, inputs: list[Any]) -> None:
        """Call one package procedure and commit its transaction."""
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                cursor.callproc(f"{self._PACKAGE}.{name}", inputs)
            session.commit()
        finally:
            _close_quietly(session)

    def _call_cursor(self, name: str, inputs: list[Any]) -> list[dict[str, Any]]:
        """Materialise a package cursor before closing the database session."""
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                result_cursor = session.cursor()
                try:
                    cursor.callproc(
                        f"{self._PACKAGE}.{name}",
                        [*inputs, result_cursor],
                    )
                    columns = [item[0].lower() for item in result_cursor.description]
                    rows = []
                    for values in result_cursor.fetchall():
                        row = {}
                        for column, value in zip(columns, values, strict=True):
                            if column in _TEXT_FIELDS and hasattr(value, "read"):
                                value = value.read()
                            row[column] = value
                        rows.append(row)
                    return rows
                finally:
                    result_cursor.close()
        finally:
            _close_quietly(session)


def _close_quietly(session: Any) -> None:
    """Close a session without masking the primary result or exception."""
    try:
        session.close()
    except Exception:
        pass
