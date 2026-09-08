"""Capability evidence and effective governed-tool mode resolution."""
# Author: Clive Bostock
# Date: 2026-08-29
# Description: Keeps governed model evidence separate from runtime health suppression.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from orac_core.knowledge.repository import default_orac_session

from .health import StreamingHealthKey, StreamingHealthState, StreamingToolHealthTracker
from .protocol import ToolDecisionMode


DEMONSTRATED_EVIDENCE_STATE = "BOUNDED_PROBE_VERIFIED"
PROVISIONAL_EVIDENCE_STATE = "MODEL_METADATA_VERIFIED"


@dataclass(frozen=True, slots=True)
class ModelToolCapabilityEvidence:
    """Immutable view of governed model capability evidence.

    ``MODEL_METADATA_VERIFIED`` verifies the provider's declaration for the
    exact model revision.  It does not demonstrate model behaviour, so the
    effective booleans are true only for bounded-probe evidence.
    """

    structured_tool_calling: bool = False
    streamed_structured_tool_calling: bool = False
    model_revision: str = ""
    structured_evidence_state: str = ""
    streamed_evidence_state: str = ""


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
        current = {
            str(capability).lower(): (str(state).upper(), str(revision or ""))
            for capability, state, revision in rows
        }
        revision = ""
        for _, value in current.items():
            if value[1]:
                revision = value[1]
                break
        structured_state = current.get("structured_tool_calling", ("", ""))[0]
        streamed_state = current.get(
            "streamed_structured_tool_calling", ("", "")
        )[0]
        return ModelToolCapabilityEvidence(
            structured_tool_calling=(
                structured_state == DEMONSTRATED_EVIDENCE_STATE
            ),
            streamed_structured_tool_calling=(
                streamed_state == DEMONSTRATED_EVIDENCE_STATE
            ),
            model_revision=revision,
            structured_evidence_state=structured_state,
            streamed_evidence_state=streamed_state,
        )


class CapabilityEvidenceWriter:
    """Persist narrow capability lifecycle decisions through ORAC_CODE."""

    _PACKAGE = "orac_code.llm_capability_evidence_api"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any] | None = None,
    ) -> None:
        """Initialise with the least-privilege Orac runtime session."""
        self._session_factory = session_factory or default_orac_session

    def reconcile_tool_metadata(
        self,
        *,
        llm_id: int,
        provider_code: str,
        model_identity: str,
        model_revision: str,
        tools_declared: bool,
    ) -> None:
        """Record the exact provider's provisional tool declaration."""
        self._call(
            "reconcile_tool_metadata",
            [
                llm_id,
                provider_code,
                model_identity,
                model_revision,
                "Y" if tools_declared else "N",
            ],
        )

    def record_probe_outcome(
        self,
        *,
        llm_id: int,
        provider_code: str,
        model_identity: str,
        model_revision: str,
        capability_code: str,
        outcome_code: str,
        probe_identity: str,
    ) -> None:
        """Record a demonstrated success or genuine model rejection."""
        self._call(
            "record_probe_outcome",
            [
                llm_id,
                provider_code,
                model_identity,
                model_revision,
                capability_code,
                outcome_code,
                probe_identity,
            ],
        )

    def _call(self, name: str, parameters: list[Any]) -> None:
        """Call one allowlisted package operation and commit atomically."""
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                cursor.callproc(f"{self._PACKAGE}.{name}", parameters)
            session.commit()
        finally:
            close = getattr(session, "close", None)
            if callable(close):
                close()


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
        if not provider_structured_supported:
            return ToolDecisionMode.NONE, "STRUCTURED_TOOL_CAPABILITY_NOT_VERIFIED"
        if not evidence.structured_tool_calling:
            if evidence.structured_evidence_state == PROVISIONAL_EVIDENCE_STATE:
                return ToolDecisionMode.NONE, "STRUCTURED_TOOL_PROBE_PENDING"
            if evidence.structured_evidence_state == "REJECTED":
                return ToolDecisionMode.NONE, "STRUCTURED_TOOL_MODEL_REJECTED"
            return ToolDecisionMode.NONE, "STRUCTURED_TOOL_CAPABILITY_NOT_VERIFIED"
        if not evidence.streamed_structured_tool_calling or not provider_streamed_supported:
            return ToolDecisionMode.BUFFERED, "STREAMED_TOOL_CAPABILITY_NOT_VERIFIED"
        health, reason = self._health_tracker.state(health_key)
        if health is StreamingHealthState.SUPPRESSED:
            return ToolDecisionMode.BUFFERED, reason
        return ToolDecisionMode.STREAMING, reason
