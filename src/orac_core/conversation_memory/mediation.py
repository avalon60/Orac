"""Host-owned mediation for governed retrieval domain services."""

# Author: Clive Bostock
# Date: 2026-08-28
# Description: Keeps logical requests separate from trusted runtime authority.

from __future__ import annotations

from typing import Any

from .models import GovernedRetrievalResult
from .models import LogicalRetrievalRequest
from .models import RetrievalDomain
from .models import TrustedRetrievalContext


class HostRetrievalMediator:
    """Small fail-closed seam between trusted callers and governed services."""

    def __init__(
        self,
        *,
        conversation_service: Any,
        project_service: Any | None = None,
    ) -> None:
        """Initialise independently governed conversation and project services."""
        self._conversation_service = conversation_service
        self._project_service = project_service

    def available_domains(
        self,
        *,
        context: TrustedRetrievalContext,
    ) -> tuple[RetrievalDomain, ...]:
        """Return only domains with host-derived authority for this request."""
        domains = [RetrievalDomain.CONVERSATION]
        scope = context.project_scope
        if (
            self._project_service is not None
            and scope is not None
            and getattr(scope, "scope_type", None) == "PROJECT"
        ):
            domains.append(RetrievalDomain.PROJECT)
        if context.plugin_retrieval_bridge is not None:
            domains.append(RetrievalDomain.PLUGIN)
        return tuple(domains)

    def retrieve(
        self,
        request: LogicalRetrievalRequest,
        *,
        context: TrustedRetrievalContext,
    ) -> GovernedRetrievalResult:
        """Invoke the independently governed service for an enabled domain."""
        if request.domain is RetrievalDomain.CONVERSATION:
            return self._retrieve_conversation(request, context=context)
        if request.domain is RetrievalDomain.PROJECT:
            return self._retrieve_project(request, context=context)
        if request.domain is RetrievalDomain.PLUGIN:
            return self._retrieve_plugin(request, context=context)
        return GovernedRetrievalResult(
            domain=request.domain,
            status="failed",
            reason_codes=("retrieval_domain_not_enabled",),
        )

    def _retrieve_conversation(
        self,
        request: LogicalRetrievalRequest,
        *,
        context: TrustedRetrievalContext,
    ) -> GovernedRetrievalResult:
        """Invoke principal-owned conversational memory retrieval."""
        outcome = self._conversation_service.retrieve(request, context=context)
        provenance = None
        if outcome.provenance is not None:
            provenance = {
                "source": "conversation_memory",
                "retrieval_id": outcome.provenance.retrieval_id,
                "initiator": outcome.provenance.initiator.value,
                "checkpoint_ids": outcome.provenance.checkpoint_ids,
                "conversation_ids": outcome.provenance.conversation_ids,
                "message_ids": outcome.provenance.message_ids,
                "checkpoint_ranges": outcome.provenance.checkpoint_ranges,
                "truncated": outcome.provenance.truncated,
            }
        return GovernedRetrievalResult(
            domain=request.domain,
            status=outcome.status,
            reason_codes=outcome.reason_codes,
            evidence=outcome.evidence,
            provenance=provenance,
        )

    def _retrieve_project(
        self,
        request: LogicalRetrievalRequest,
        *,
        context: TrustedRetrievalContext,
    ) -> GovernedRetrievalResult:
        """Invoke existing PROJECT retrieval with an exact host-bound scope."""
        scope = context.project_scope
        if (
            self._project_service is None
            or scope is None
            or getattr(scope, "scope_type", None) != "PROJECT"
        ):
            return GovernedRetrievalResult(
                domain=request.domain,
                status="failed",
                reason_codes=("retrieval_domain_not_enabled",),
            )
        outcome = self._project_service.retrieve(
            request.query,
            principal_username=context.principal_username,
            scope=scope,
            max_chunk_chars=max(256, context.evidence_token_budget * 2),
            max_context_chars=max(256, context.evidence_token_budget * 2),
        )
        return GovernedRetrievalResult(
            domain=request.domain,
            status=outcome.status,
            reason_codes=outcome.reason_codes,
            evidence=outcome.results,
            provenance={
                "source": "project_knowledge",
                "retrieval_id": outcome.retrieval_id,
                "scope_type": outcome.scope.scope_type,
                "scope_key": outcome.scope.scope_key,
                "chunk_ids": tuple(item.chunk_id for item in outcome.results),
            },
        )

    @staticmethod
    def _retrieve_plugin(
        request: LogicalRetrievalRequest,
        *,
        context: TrustedRetrievalContext,
    ) -> GovernedRetrievalResult:
        """Invoke the existing trusted plugin self-scope bridge."""
        bridge = context.plugin_retrieval_bridge
        if bridge is None:
            return GovernedRetrievalResult(
                domain=request.domain,
                status="failed",
                reason_codes=("retrieval_domain_not_enabled",),
            )
        outcome = bridge.retrieve(request.query)
        return GovernedRetrievalResult(
            domain=request.domain,
            status=outcome.status,
            reason_codes=outcome.reason_codes,
            evidence=outcome.evidence,
            provenance={
                "source": "plugin_knowledge",
                "retrieval_id": outcome.retrieval_id,
                "chunk_ids": tuple(item.chunk_id for item in outcome.evidence),
            },
        )
