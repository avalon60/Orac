"""Host-owned bridge for request-bound plugin knowledge retrieval."""
# Author: Clive Bostock
# Date: 2026-08-26
# Description: Binds plugin self-scope retrieval to trusted host runtime state.

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any
import uuid

from orac_core.knowledge import KnowledgeRetrievalOutcome
from orac_core.knowledge import KnowledgeRetrievalService


SELF_SCOPE_RETRIEVAL_ENTITLEMENT = "knowledge.self_scope_retrieval"
PLUGIN_KNOWLEDGE_DEFAULT_LIMIT = 5
PLUGIN_KNOWLEDGE_MAX_LIMIT = 6
PLUGIN_KNOWLEDGE_MAX_QUERY_CHARS = 2048
PLUGIN_KNOWLEDGE_MAX_CHUNK_CHARS = 2200
PLUGIN_KNOWLEDGE_MAX_CONTEXT_CHARS = 12000


@dataclass(frozen=True)
class PluginKnowledgeEvidence:
    """One bounded piece of Core evidence returned to an executing plugin."""

    document_id: int
    document_version_id: int
    chunk_id: int
    chunk_no: int
    title: str | None
    relevance_score: float
    text: str


@dataclass(frozen=True)
class PluginKnowledgeRetrievalResult:
    """Controlled immutable result of plugin self-scope retrieval."""

    status: str
    reason_codes: tuple[str, ...]
    retrieval_id: str | None = None
    evidence: tuple[PluginKnowledgeEvidence, ...] = ()


@dataclass(frozen=True)
class PluginKnowledgeRetrievalBridge:
    """Immutable authority captured by the host for one plugin request."""

    _plugin_id: str
    _principal_username: str
    _retrieval_service: KnowledgeRetrievalService | None
    _correlation_id: str | None
    _entitled: bool
    _logger: Any

    def retrieve(
        self,
        query: str,
        *,
        limit: int = PLUGIN_KNOWLEDGE_DEFAULT_LIMIT,
    ) -> PluginKnowledgeRetrievalResult:
        """Retrieve evidence only from the bridge's host-bound plugin scope."""
        validation_failure = _validate_request(query, limit)
        if validation_failure is not None:
            return validation_failure
        if not self._entitled:
            return _failure("capability_not_entitled")
        if not self._principal_username:
            return _failure("authentication_required")
        if self._retrieval_service is None:
            return _failure("retrieval_unavailable")

        normalised_query = query.strip()
        try:
            outcome = self._retrieval_service.retrieve_for_plugin(
                normalised_query,
                principal_username=self._principal_username,
                plugin_id=self._plugin_id,
                max_selected_chunks=limit,
                correlation_id=self._correlation_id,
            )
            return _plugin_result_from_outcome(
                outcome,
                plugin_id=self._plugin_id,
                limit=limit,
            )
        except Exception as exc:
            _log_bridge_failure(self._logger, self._plugin_id, exc)
            return _failure("retrieval_unavailable")


def plugin_knowledge_bridge(
    *,
    plugin_id: str,
    principal_username: str,
    retrieval_service: KnowledgeRetrievalService | None,
    correlation_id: str | None,
    entitled: bool,
    logger: Any,
) -> PluginKnowledgeRetrievalBridge:
    """Create a bridge from trusted host state rather than plugin input."""
    principal = str(principal_username or "").strip()
    capability_enabled = bool(entitled) and bool(principal)
    return PluginKnowledgeRetrievalBridge(
        _plugin_id=str(plugin_id or "").strip(),
        _principal_username=principal,
        _retrieval_service=(retrieval_service if capability_enabled else None),
        _correlation_id=_bounded_correlation_id(correlation_id),
        _entitled=bool(entitled),
        _logger=logger,
    )


def _validate_request(
    query: object,
    limit: object,
) -> PluginKnowledgeRetrievalResult | None:
    """Validate the deliberately small public plugin request contract."""
    if not isinstance(query, str) or not query.strip():
        return _failure("invalid_query")
    if len(query) > PLUGIN_KNOWLEDGE_MAX_QUERY_CHARS:
        return _failure("query_too_long")
    if isinstance(limit, bool) or not isinstance(limit, int):
        return _failure("invalid_limit")
    if not 1 <= limit <= PLUGIN_KNOWLEDGE_MAX_LIMIT:
        return _failure("invalid_limit")
    return None


def _plugin_result_from_outcome(
    outcome: object,
    *,
    plugin_id: str,
    limit: int,
) -> PluginKnowledgeRetrievalResult:
    """Validate the Core response before adapting it to the plugin DTO."""
    if not isinstance(outcome, KnowledgeRetrievalOutcome):
        return _failure("invalid_retrieval_response")
    if outcome.scope.scope_type != "PLUGIN" or outcome.scope.scope_key != plugin_id:
        return _failure("invalid_retrieval_response")
    if outcome.status not in {"grounded", "no_evidence", "failed"}:
        return _failure("invalid_retrieval_response")
    if (
        not isinstance(outcome.reason_codes, tuple)
        or not 1 <= len(outcome.reason_codes) <= 4
        or any(
            not isinstance(reason, str) or not reason or len(reason) > 100
            for reason in outcome.reason_codes
        )
        or not isinstance(outcome.results, tuple)
    ):
        return _failure("invalid_retrieval_response")
    if outcome.retrieval_id is not None:
        try:
            uuid.UUID(outcome.retrieval_id)
        except (AttributeError, TypeError, ValueError):
            return _failure("invalid_retrieval_response")
    if len(outcome.results) > limit:
        return _failure("invalid_retrieval_response")
    if outcome.status == "grounded" and not outcome.results:
        return _failure("invalid_retrieval_response")
    if outcome.status != "grounded" and outcome.results:
        return _failure("invalid_retrieval_response")

    evidence: list[PluginKnowledgeEvidence] = []
    used_chars = 0
    for item in outcome.results:
        identity_values = (
            item.document_id,
            item.document_version_id,
            item.chunk_id,
            item.chunk_no,
        )
        if (
            item.scope != outcome.scope
            or any(
                isinstance(value, bool) or not isinstance(value, int) or value <= 0
                for value in identity_values
            )
            or not isinstance(item.chunk_text, str)
            or not isinstance(item.score, float)
            or not math.isfinite(item.score)
            or not 0.0 <= item.score <= 1.0
            or (
                item.document_title is not None
                and not isinstance(item.document_title, str)
            )
        ):
            return _failure("invalid_retrieval_response")
        text = item.chunk_text[:PLUGIN_KNOWLEDGE_MAX_CHUNK_CHARS]
        remaining = PLUGIN_KNOWLEDGE_MAX_CONTEXT_CHARS - used_chars
        if remaining <= 0:
            break
        text = text[:remaining]
        used_chars += len(text)
        evidence.append(
            PluginKnowledgeEvidence(
                document_id=item.document_id,
                document_version_id=item.document_version_id,
                chunk_id=item.chunk_id,
                chunk_no=item.chunk_no,
                title=(item.document_title[:500] if item.document_title else None),
                relevance_score=item.score,
                text=text,
            )
        )

    reason_codes = outcome.reason_codes
    if outcome.status == "failed":
        reason_codes = ("not_authorised_or_ineligible",)
    return PluginKnowledgeRetrievalResult(
        status=outcome.status,
        reason_codes=reason_codes,
        retrieval_id=outcome.retrieval_id,
        evidence=tuple(evidence),
    )


def _failure(reason_code: str) -> PluginKnowledgeRetrievalResult:
    """Return one controlled plugin-facing failure."""
    return PluginKnowledgeRetrievalResult(
        status="failed",
        reason_codes=(reason_code,),
    )


def _bounded_correlation_id(value: object) -> str | None:
    """Return a compact host correlation identifier for audit metadata."""
    normalised = str(value or "").strip()
    return normalised[:128] or None


def _log_bridge_failure(logger: Any, plugin_id: str, exc: Exception) -> None:
    """Log internal failure detail without returning it to plugin code."""
    log_error = getattr(logger, "log_error", None)
    if callable(log_error):
        log_error(
            f"Plugin self-scope knowledge retrieval failed for '{plugin_id}': {exc}"
        )
