"""Process queued semantic searches from authenticated plugin APEX applications."""
# Author: Clive Bostock
# Date: 25-Oct-2026
# Description: Uses the Core embedding path for session-bound plugin APEX searches.
# Purpose: Process authenticated plugin APEX semantic search requests.
# Usage: Registered as the Core knowledge_apex_search scheduled service.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

import json
import os
import socket
from typing import Any, Callable

import oracledb

from .embeddings import knowledge_embedding_provider
from .repository import default_orac_session
from .retrieval import KnowledgeRetrievalService


def _close_session(session: Any) -> None:
    """Close a session without masking an earlier database failure."""
    try:
        session.close()
    except Exception:
        pass


class KnowledgeApexSearchRepository:
    """Call worker-only PL/SQL operations through the trusted ORAC identity."""

    _PACKAGE = "orac_code.knowledge_apex_search_worker_api"

    def __init__(self, session_factory: Callable[[], Any] | None = None) -> None:
        """Store the database session factory."""
        self._session_factory = session_factory or default_orac_session

    def claim_next(self, worker_id: str) -> dict[str, Any] | None:
        """Claim one request and return its immutable routing facts."""
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                request_id = cursor.var(oracledb.DB_TYPE_NUMBER)
                lease_token = cursor.var(oracledb.DB_TYPE_VARCHAR)
                username = cursor.var(oracledb.DB_TYPE_VARCHAR)
                plugin_id = cursor.var(oracledb.DB_TYPE_VARCHAR)
                query = cursor.var(oracledb.DB_TYPE_VARCHAR)
                cursor.callproc(
                    f"{self._PACKAGE}.claim_next",
                    [worker_id, request_id, lease_token, username, plugin_id, query],
                )
                claimed = request_id.getvalue()
                result = (
                    {
                        "request_id": int(claimed),
                        "lease_token": str(lease_token.getvalue()),
                        "username": str(username.getvalue()),
                        "plugin_id": str(plugin_id.getvalue()),
                        "query": str(query.getvalue()),
                    }
                    if claimed is not None
                    else None
                )
            session.commit()
            return result
        finally:
            _close_session(session)

    def complete(
        self, request_id: int, worker_id: str, lease_token: str, refs: list[dict]
    ) -> None:
        """Persist bounded result identities without passage text."""
        self._call(
            "complete_search",
            [request_id, worker_id, lease_token, json.dumps(refs)],
        )

    def fail(
        self,
        request_id: int,
        worker_id: str,
        lease_token: str,
        failure_code: str,
        *,
        retryable: bool,
    ) -> None:
        """Record a content-free failure and optional retry."""
        self._call(
            "fail_search",
            [request_id, worker_id, lease_token, failure_code,
             "Y" if retryable else "N"],
        )

    def purge_expired(self) -> None:
        """Delete search requests after their one-day lifetime."""
        self._call("purge_expired", [])

    def _call(self, name: str, arguments: list[Any]) -> None:
        """Call one worker package procedure and commit its transaction."""
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                cursor.callproc(f"{self._PACKAGE}.{name}", arguments)
            session.commit()
        finally:
            _close_session(session)


class KnowledgeApexSearchService:
    """Scheduled Core worker for plugin APEX search requests."""

    def __init__(
        self,
        logger: Any | None = None,
        config_mgr: Any | None = None,
        manifest: Any | None = None,
        *,
        repository: KnowledgeApexSearchRepository | None = None,
        retrieval_service: KnowledgeRetrievalService | None = None,
    ) -> None:
        """Initialise the worker with injectable persistence and retrieval."""
        del manifest
        self._logger = logger
        self._repository = repository or KnowledgeApexSearchRepository()
        self._retrieval = retrieval_service or KnowledgeRetrievalService(
            embedding_provider=knowledge_embedding_provider(config_mgr)
        )
        self._worker_id = f"apex-search:{socket.gethostname()}:{os.getpid()}"
        self.last_error: str | None = None

    def tick(self, context: Any) -> None:
        """Purge expired requests and process at most five queued searches."""
        del context
        self._repository.purge_expired()
        self.last_error = None
        for _ in range(5):
            request = self._repository.claim_next(self._worker_id)
            if request is None:
                break
            try:
                outcome = self._retrieval.retrieve_for_plugin(
                    request["query"],
                    principal_username=request["username"],
                    plugin_id=request["plugin_id"],
                    max_selected_chunks=6,
                    correlation_id=str(request["request_id"]),
                )
                if outcome.status not in {"grounded", "no_evidence"}:
                    self._repository.fail(
                        request["request_id"], self._worker_id,
                        request["lease_token"], "RETRIEVAL_UNAVAILABLE",
                        retryable=False,
                    )
                    continue
                refs = [
                    {
                        "document_id": item.document_id,
                        "document_version_id": item.document_version_id,
                        "chunk_id": item.chunk_id,
                        "chunk_no": item.chunk_no,
                        "relevance_score": round(item.fused_score, 8),
                    }
                    for item in outcome.results[:6]
                ]
                self._repository.complete(
                    request["request_id"], self._worker_id,
                    request["lease_token"], refs,
                )
            except Exception as exc:
                self.last_error = type(exc).__name__
                if self._logger is not None:
                    self._logger.log_warning(
                        "Plugin APEX knowledge search failed: "
                        f"request_id={request['request_id']} "
                        f"error={type(exc).__name__}"
                    )
                self._repository.fail(
                    request["request_id"], self._worker_id,
                    request["lease_token"], "RETRIEVAL_UNAVAILABLE",
                    retryable=True,
                )

    def health(self, context: Any) -> bool:
        """Report whether the most recent tick encountered a failure."""
        del context
        return self.last_error is None
