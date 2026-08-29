"""Capability evidence and effective governed-tool mode resolution."""
# Author: Clive Bostock
# Date: 2026-08-29
# Description: Keeps governed model evidence separate from runtime health suppression.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .health import StreamingHealthKey, StreamingHealthState, StreamingToolHealthTracker
from .protocol import ToolDecisionMode


VERIFIED_EVIDENCE_STATES = frozenset(
    {"MODEL_METADATA_VERIFIED", "BOUNDED_PROBE_VERIFIED"}
)


@dataclass(frozen=True, slots=True)
class ModelToolCapabilityEvidence:
    """Immutable view of administratively governed model capability evidence."""

    structured_tool_calling: bool = False
    streamed_structured_tool_calling: bool = False
    model_revision: str = ""


class CapabilityEvidenceRepository:
    """Read current governed capability evidence through the Orac code layer."""

    def __init__(self, *, session_factory: Callable[[], Any]) -> None:
        """Initialise with an injectable least-privilege session factory."""
        self._session_factory = session_factory

    def load(self, llm_id: int) -> ModelToolCapabilityEvidence:
        """Load positive evidence for one exact registered model."""
        if llm_id <= 0:
            return ModelToolCapabilityEvidence()
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                cursor.execute(
                    """
                    select capability_code, evidence_state, model_revision
                      from orac_code.llm_current_model_evidence_v
                     where llm_id = :llm_id
                       and capability_code in (
                         'structured_tool_calling',
                         'streamed_structured_tool_calling'
                       )
                    """,
                    {"llm_id": llm_id},
                )
                rows = cursor.fetchall()
        finally:
            close = getattr(session, "close", None)
            if callable(close):
                close()
        rejected = {
            str(capability).lower()
            for capability, state, _ in rows
            if str(state).upper() == "REJECTED"
        }
        positive = {
            str(capability).lower(): (str(state).upper(), str(revision or ""))
            for capability, state, revision in rows
            if str(state).upper() in VERIFIED_EVIDENCE_STATES
            and str(capability).lower() not in rejected
        }
        revision = ""
        for _, value in positive.items():
            if value[1]:
                revision = value[1]
                break
        return ModelToolCapabilityEvidence(
            structured_tool_calling="structured_tool_calling" in positive,
            streamed_structured_tool_calling=(
                positive.get("streamed_structured_tool_calling", ("", ""))[0]
                == "BOUNDED_PROBE_VERIFIED"
            ),
            model_revision=revision,
        )


class EffectiveToolModeResolver:
    """Resolve NONE, BUFFERED, or STREAMING without model-name conditions."""

    def __init__(self, *, health_tracker: StreamingToolHealthTracker) -> None:
        """Initialise with the Phase 2A-local health tracker."""
        self._health_tracker = health_tracker

    def resolve(
        self,
        *,
        enabled: bool,
        evidence: ModelToolCapabilityEvidence,
        provider_structured_supported: bool,
        provider_streamed_supported: bool,
        health_key: StreamingHealthKey,
        authority_available: bool,
        context_safe: bool,
    ) -> tuple[ToolDecisionMode, str]:
        """Return an effective mode and content-free reason code."""
        if not enabled:
            return ToolDecisionMode.NONE, "GOVERNED_RETRIEVAL_DISABLED"
        if not authority_available:
            return ToolDecisionMode.NONE, "GOVERNED_RETRIEVAL_AUTHORITY_UNAVAILABLE"
        if not context_safe:
            return ToolDecisionMode.NONE, "GOVERNED_RETRIEVAL_CONTEXT_UNSAFE"
        if not evidence.structured_tool_calling or not provider_structured_supported:
            return ToolDecisionMode.NONE, "STRUCTURED_TOOL_CAPABILITY_NOT_VERIFIED"
        if not evidence.streamed_structured_tool_calling or not provider_streamed_supported:
            return ToolDecisionMode.BUFFERED, "STREAMED_TOOL_CAPABILITY_NOT_VERIFIED"
        health, reason = self._health_tracker.state(health_key)
        if health is StreamingHealthState.SUPPRESSED:
            return ToolDecisionMode.BUFFERED, reason
        return ToolDecisionMode.STREAMING, reason
