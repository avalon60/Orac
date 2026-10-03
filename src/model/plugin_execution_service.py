"""Service wrapper for Orac plugin execution coordination."""

# Author: Clive Bostock
# Date: 2026-05-25
# Description: Keeps controller code behind a narrow plugin execution seam.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

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
        candidates = tuple(handoff.candidates if handoff is not None else ())
        eligible_candidates, ineligible_candidates = self._eligible_candidates(
            candidates=candidates,
            meta=meta,
        )
        if not eligible_candidates and len(ineligible_candidates) == 1:
            return self._route_selected_candidate(
                prompt=prompt,
                meta=meta,
                candidate=ineligible_candidates[0],
                auth_user=auth_user,
                request_context=request_context,
                refreshed=bool(handoff.refreshed if handoff is not None else False),
                arbitration={
                    "source": "plugin_eligibility",
                    "decision_type": "policy_blocked",
                },
            )
        arbitration_kwargs = {
            "utterance": prompt,
            "candidates": eligible_candidates,
            "pending_context": scoped_pending_context,
        }
        if isinstance(self._plugin_arbiter, PluginArbiter):
            arbitration_kwargs["adviser_allowed"] = callable(
                getattr(self._plugin_router, "candidate_eligibility", None)
            )
        decision = self._plugin_arbiter.arbitrate(**arbitration_kwargs)
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
        if decision.reason == "llm_adviser_selected_plugin":
            selected = _selected_eligible_candidate(decision, eligible_candidates)
        else:
            selected = _selected_candidate(decision)
        eligible_keys = {_candidate_key(candidate) for candidate in eligible_candidates}
        if (
            selected is None or _candidate_key(selected) not in eligible_keys
        ) and decision.selected_plugin_id is not None:
            self._logger.log_warning(
                "Plugin arbiter returned a candidate outside the eligible set."
            )
            return PluginExecutionResult(
                plugin_id="orac_core",
                content="The requested plugin capability is not available.",
                handled=True,
                provenance={"source": "plugin_arbitration", "status": "rejected"},
            )
        if selected is None:
            return None
        if decision.reason == "llm_adviser_selected_plugin":
            revalidate = getattr(self._plugin_router, "candidate_eligibility", None)
            try:
                revalidated = bool(
                    callable(revalidate) and revalidate(selected, meta=meta).executable
                )
            except Exception:
                revalidated = False
            if not revalidated:
                self._logger.log_warning(
                    "LLM arbitration candidate failed deterministic revalidation."
                )
                return None
            self._logger.log_debug(
                "LLM arbitration candidate passed deterministic revalidation: "
                f"candidate={_candidate_key(selected)}"
            )
        return self._route_selected_candidate(
            prompt=prompt,
            meta=meta,
            candidate=selected,
            auth_user=auth_user,
            request_context=request_context,
            refreshed=bool(handoff.refreshed if handoff is not None else False),
            arbitration=_arbitration_provenance(decision),
        )

    def _eligible_candidates(
        self,
        *,
        candidates: tuple[Any, ...],
        meta: dict[str, Any] | None,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
        """Partition candidates using side-effect-free host policy checks."""
        check = getattr(self._plugin_router, "candidate_eligibility", None)
        if not callable(check):
            return candidates, ()
        eligible: list[Any] = []
        ineligible: list[Any] = []
        for candidate in candidates:
            result = check(candidate, meta=meta)
            (eligible if result.executable else ineligible).append(candidate)
        return tuple(eligible), tuple(ineligible)

    def _route_selected_candidate(
        self,
        *,
        prompt: str,
        meta: dict[str, Any] | None,
        candidate: Any,
        auth_user: str,
        request_context: dict[str, Any] | None,
        refreshed: bool,
        arbitration: dict[str, Any],
    ) -> PluginExecutionResult | None:
        """Invoke final policy and execution for exactly one selected route."""
        if self._plugin_router is None:
            return None
        result = self._plugin_router.route(
            prompt,
            meta,
            PluginRoutingHandoff(candidates=(candidate,), refreshed=refreshed),
            auth_user,
            audit_adapter=self._plugin_audit_adapter,
            request_context={
                **(request_context or {}),
                "arbitration": arbitration,
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


def _selected_eligible_candidate(
    decision: ArbitrationDecision,
    eligible_candidates: tuple[PluginRouteCandidate, ...],
) -> PluginRouteCandidate | None:
    """Resolve a selection to the original core-eligible candidate object."""
    selected_key = (
        str(decision.selected_plugin_id or ""),
        str(decision.selected_capability_id or ""),
        str(decision.selected_intent_name or "default"),
    )
    if not all(selected_key):
        return None
    for candidate in eligible_candidates:
        if _candidate_key(candidate) == selected_key:
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


def _candidate_key(candidate: Any) -> tuple[str, str, str]:
    """Return the authority-relevant identity of a route candidate."""
    return (
        str(getattr(candidate, "plugin_id", "")),
        str(getattr(candidate, "capability_id", "")),
        str(getattr(candidate, "intent_name", "") or "default"),
    )


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
