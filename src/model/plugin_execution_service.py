"""Service wrapper for Orac plugin execution coordination."""
# Author: Clive Bostock
# Date: 2026-05-25
# Description: Keeps controller code behind a narrow plugin execution seam.

from __future__ import annotations

from dataclasses import replace
from typing import Any

from model.plugin_arbitration import PluginArbiter
from model.plugin_audit_adapter import PluginAuditAdapter
from model.plugin_routing.handoff import PluginRoutingHandoff
from model.plugin_routing.models import ArbitrationDecision, PluginRouteCandidate
from model.plugin_runtime import PluginExecutionResult


class PluginExecutionService:
    """Coordinates plugin execution through the policy-aware plugin router."""

    def __init__(
        self,
        *,
        plugin_router: Any | None,
        logger: Any,
        plugin_audit_adapter: PluginAuditAdapter | None = None,
        plugin_arbiter: PluginArbiter | None = None,
    ) -> None:
        """Initialise the service with the existing router dependency.

        Args:
            plugin_router: Policy-aware plugin router used for plugin
                selection and invocation.
            logger: Project logger used for debug messages.
            plugin_audit_adapter: Optional runtime-facing plugin audit adapter.
        """
        self._plugin_router = plugin_router
        self._logger = logger
        self._plugin_audit_adapter = plugin_audit_adapter
        self.plugin_audit_adapter = plugin_audit_adapter
        self._plugin_arbiter = plugin_arbiter or PluginArbiter(logger=logger)

    def execute(
        self,
        *,
        prompt: str,
        meta: dict[str, Any] | None,
        handoff: PluginRoutingHandoff | None,
        auth_user: str,
        request_context: dict[str, Any] | None = None,
        pending_context: dict[str, Any] | None = None,
    ) -> PluginExecutionResult | None:
        """Return a handled plugin result, or ``None`` for LLM fallback."""
        scoped_pending_context = _scoped_pending_context(
            pending_context=pending_context,
            request_context=request_context,
            meta=meta,
            auth_user=auth_user,
        )
        decision = self._plugin_arbiter.arbitrate(
            utterance=prompt,
            candidates=tuple(handoff.candidates if handoff is not None else ()),
            pending_context=scoped_pending_context,
        )
        if decision.decision_type == "llm_fallback":
            if self._plugin_router is None:
                self._logger.log_debug(
                    "Plugin execution unavailable; falling back to conversational flow."
                )
            return None
        if decision.decision_type == "core_command":
            return PluginExecutionResult(
                plugin_id="orac_core",
                content="Okay.",
                provenance=_arbitration_provenance(decision),
            )
        if decision.decision_type in {"clarify", "reject"}:
            return PluginExecutionResult(
                plugin_id="orac_core",
                content=decision.clarification_prompt or decision.reason,
                provenance=_arbitration_provenance(decision),
            )
        selected = _selected_candidate(decision)
        if selected is None:
            return None
        selected_handoff = PluginRoutingHandoff(
            candidates=(selected,),
            refreshed=bool(handoff.refreshed if handoff is not None else False),
        )

        if self._plugin_router is None:
            self._logger.log_debug(
                "Plugin execution unavailable; falling back to conversational flow."
            )
            return None

        result = self._plugin_router.route(
            prompt,
            meta,
            selected_handoff,
            auth_user,
            audit_adapter=self._plugin_audit_adapter,
            request_context={
                **(request_context or {}),
                "arbitration": _arbitration_provenance(decision),
            },
        )
        if result is None or not result.handled:
            return None

        if result.provenance:
            return result

        return replace(
            result,
            provenance={
                "source": "plugin_execution",
                "plugin_id": result.plugin_id,
                "status": "allowed",
            },
        )


def _selected_candidate(decision: ArbitrationDecision) -> PluginRouteCandidate | None:
    """Return the candidate selected by an arbitration decision."""
    for candidate in decision.candidates:
        if (
            candidate.plugin_id == decision.selected_plugin_id
            and candidate.capability_id == decision.selected_capability_id
            and candidate.intent_name == decision.selected_intent_name
        ):
            return candidate
    return None


def _arbitration_provenance(decision: ArbitrationDecision) -> dict[str, Any]:
    """Return compact provenance for a core arbitration decision."""
    return {
        "source": "plugin_arbitration",
        "decision_type": decision.decision_type,
        "selected_plugin_id": decision.selected_plugin_id,
        "selected_capability_id": decision.selected_capability_id,
        "selected_intent_name": decision.selected_intent_name,
        "reason": decision.reason,
        "utterance": decision.utterance,
        "candidates": [
            {
                "plugin_id": candidate.plugin_id,
                "capability_id": candidate.capability_id,
                "intent_name": candidate.intent_name,
                "confidence": candidate.confidence,
                "match_reasons": list(candidate.match_reasons),
            }
            for candidate in decision.candidates
        ],
    }


def _scoped_pending_context(
    *,
    pending_context: dict[str, Any] | None,
    request_context: dict[str, Any] | None,
    meta: dict[str, Any] | None,
    auth_user: str,
) -> dict[str, Any] | None:
    """Return pending context only when request identity boundaries match."""
    if not pending_context:
        return None

    current = {**(meta or {}), **(request_context or {})}
    current.setdefault("auth_user", auth_user)

    for pending_key, current_keys in {
        "auth_user": ("auth_user", "user_name"),
        "user_name": ("auth_user", "user_name"),
        "user_id": ("user_id",),
        "session_id": ("session_id",),
        "conversation_id": ("conversation_id",),
        "voice_session_id": ("voice_session_id", "session_id"),
    }.items():
        pending_value = _normalised_context_value(pending_context.get(pending_key))
        if not pending_value:
            continue
        current_values = {
            _normalised_context_value(current.get(current_key))
            for current_key in current_keys
        }
        current_values.discard("")
        if current_values and pending_value not in current_values:
            return None

    return pending_context


def _normalised_context_value(value: Any) -> str:
    """Return a stable string value for request-boundary comparisons."""
    return str(value or "").strip()
