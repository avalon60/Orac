"""Guard evidence-backed prompts immediately before primary model submission."""

# Author: Clive Bostock
# Date: 14-Aug-2026
# Description: Revalidates immutable evidence prompts against model and context limits.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import math
import re
from typing import Any
import uuid

from .evidence import EVIDENCE_BEGIN_MARKER
from .evidence import EVIDENCE_END_MARKER
from .evidence import EvidenceEnvelope
from .materialisation_policy import MaterialisationApprovalSnapshot
from .scope import KnowledgeScope
from .token_estimation import ConservativeUtf8TokenEstimator


_SAFE_REASON = re.compile(r"^MAT_SUB_[A-Z0-9_]{1,80}$")


@dataclass(frozen=True, slots=True)
class PromptContextSnapshot:
    """Conversation and trusted-policy facts used to assemble one prompt."""

    conversation_id: int
    highest_turn_index: int
    system_prompt_fingerprint: str
    policy_config_fingerprint: str


@dataclass(frozen=True, slots=True)
class ModelRegistrySnapshot:
    """Exact effective model-registry row and explicit provider capabilities."""

    llm_id: int
    row_version: int
    provider_code: str
    model_name: str
    model_type: str
    context_policy_code: str
    max_context_tokens: int
    processing_locality: str
    text_evidence_eligible: bool
    enabled: bool = True
    available: bool = True


@dataclass(frozen=True, slots=True)
class StrictModelInvocationOptions:
    """Adapter restrictions that preserve an approved evidence submission."""

    max_output_tokens: int = 2048
    allow_output_budget_growth: bool = False
    allow_endpoint_fallback: bool = False
    maximum_pre_output_retries: int = 1


@dataclass(frozen=True, slots=True)
class PrepareModelSubmissionRequest:
    """Immutable inputs to the final evidence submission guard."""

    submission_id: str
    request_id: str
    approval: MaterialisationApprovalSnapshot
    envelope: EvidenceEnvelope
    prompt: str
    prompt_context: PromptContextSnapshot
    model: ModelRegistrySnapshot
    reserved_output_tokens: int = 2048


@dataclass(frozen=True, slots=True)
class PreparedModelSubmission:
    """Approved immutable prompt and accounting for one exact model call."""

    request: PrepareModelSubmissionRequest
    final_prompt_safe_tokens: int
    occupied_safe_tokens: int
    evidence_safe_tokens: int
    context_safety_tokens: int
    invocation_options: StrictModelInvocationOptions


@dataclass(frozen=True, slots=True)
class ModelSubmissionRejection:
    """Safe final rejection that never contains evidence or prompt text."""

    submission_id: str
    reason_code: str

    def __post_init__(self) -> None:
        """Reject accidental free-form or unsafe reason codes."""
        if _SAFE_REASON.fullmatch(self.reason_code) is None:
            raise ValueError("model submission reason code is invalid")


@dataclass(frozen=True, slots=True)
class KnowledgeEvidenceTurnState:
    """Content-free bounded state for explicit user-mediated follow-ups."""

    conversation_id: int
    principal_username: str
    scope: KnowledgeScope
    target_type: str
    target_id: int
    registered_artefact_ids: tuple[int, ...]
    registered_chunk_ids: tuple[int, ...]
    rounds_used: int
    cumulative_bytes: int
    cumulative_safe_tokens: int
    cumulative_members: int
    cumulative_chunks: int
    cumulative_rows: int
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class KnowledgeEvidenceFollowUpLimits:
    """Cumulative ceilings for explicit user-mediated evidence follow-ups."""

    max_rounds: int = 2
    max_bytes: int = 512 * 1024
    max_safe_tokens: int = 24_000
    max_members: int = 16
    max_chunks: int = 64
    max_rows: int = 2_000
    max_elapsed_seconds: int = 120

    def __post_init__(self) -> None:
        """Reject disabled or nonsensical cumulative ceilings."""
        if any(
            value <= 0
            for value in (
                self.max_rounds,
                self.max_bytes,
                self.max_safe_tokens,
                self.max_members,
                self.max_chunks,
                self.max_rows,
                self.max_elapsed_seconds,
            )
        ):
            raise ValueError("follow-up limits must be positive")
        if (
            self.max_rounds > 2
            or self.max_bytes > 512 * 1024
            or self.max_safe_tokens > 24_000
            or self.max_members > 16
            or self.max_chunks > 64
            or self.max_rows > 2_000
            or self.max_elapsed_seconds > 120
        ):
            raise ValueError("follow-up limits exceed P1-08 ceilings")


class KnowledgeEvidenceFollowUpTracker:
    """Maintain content-free registered-target state under cumulative ceilings."""

    def __init__(self, limits: KnowledgeEvidenceFollowUpLimits | None = None) -> None:
        """Initialise the tracker with the approved P1-08 ceilings."""
        self._limits = limits or KnowledgeEvidenceFollowUpLimits()

    def register_initial(
        self,
        *,
        conversation_id: int,
        principal_username: str,
        scope: KnowledgeScope,
        target_type: str,
        target_id: int,
        registered_artefact_ids: tuple[int, ...],
        registered_chunk_ids: tuple[int, ...],
        envelope: EvidenceEnvelope,
        now: datetime | None = None,
    ) -> KnowledgeEvidenceTurnState | ModelSubmissionRejection:
        """Register the initial approved evidence without retaining its content."""
        current = now or datetime.now(timezone.utc)
        rejection = self._ceiling_failure(
            rounds=0,
            byte_count=envelope.byte_size,
            safe_tokens=envelope.safe_token_count,
            members=envelope.member_count,
            chunks=envelope.chunk_count,
            rows=envelope.row_count,
        )
        if rejection is not None:
            return ModelSubmissionRejection(str(uuid.uuid4()), rejection)
        return KnowledgeEvidenceTurnState(
            conversation_id=conversation_id,
            principal_username=principal_username,
            scope=scope,
            target_type=target_type,
            target_id=target_id,
            registered_artefact_ids=tuple(sorted(set(registered_artefact_ids))),
            registered_chunk_ids=tuple(sorted(set(registered_chunk_ids))),
            rounds_used=0,
            cumulative_bytes=envelope.byte_size,
            cumulative_safe_tokens=envelope.safe_token_count,
            cumulative_members=envelope.member_count,
            cumulative_chunks=envelope.chunk_count,
            cumulative_rows=envelope.row_count,
            expires_at=current + timedelta(seconds=self._limits.max_elapsed_seconds),
        )

    def register_follow_up(
        self,
        state: KnowledgeEvidenceTurnState,
        *,
        principal_username: str,
        scope: KnowledgeScope,
        target_type: str,
        target_id: int,
        envelope: EvidenceEnvelope,
        evidence_artefact_ids: tuple[int, ...] = (),
        evidence_chunk_ids: tuple[int, ...] = (),
        now: datetime | None = None,
    ) -> KnowledgeEvidenceTurnState | ModelSubmissionRejection:
        """Advance one explicit same-target round or return a safe rejection."""
        current = now or datetime.now(timezone.utc)
        if current >= state.expires_at:
            return ModelSubmissionRejection(str(uuid.uuid4()), "MAT_SUB_FOLLOW_UP_LIMIT")
        if principal_username != state.principal_username:
            return ModelSubmissionRejection(
                str(uuid.uuid4()),
                "MAT_SUB_PRINCIPAL_MISMATCH",
            )
        if scope != state.scope:
            return ModelSubmissionRejection(str(uuid.uuid4()), "MAT_SUB_SCOPE_MISMATCH")
        if target_type != state.target_type or target_id != state.target_id:
            return ModelSubmissionRejection(
                str(uuid.uuid4()),
                "MAT_SUB_REAUTHORISATION_REQUIRED",
            )
        if not set(evidence_artefact_ids).issubset(state.registered_artefact_ids):
            return ModelSubmissionRejection(
                str(uuid.uuid4()),
                "MAT_SUB_REAUTHORISATION_REQUIRED",
            )
        if not set(evidence_chunk_ids).issubset(state.registered_chunk_ids):
            return ModelSubmissionRejection(
                str(uuid.uuid4()),
                "MAT_SUB_REAUTHORISATION_REQUIRED",
            )
        rounds = state.rounds_used + 1
        byte_count = state.cumulative_bytes + envelope.byte_size
        safe_tokens = state.cumulative_safe_tokens + envelope.safe_token_count
        members = state.cumulative_members + envelope.member_count
        chunks = state.cumulative_chunks + envelope.chunk_count
        rows = state.cumulative_rows + envelope.row_count
        rejection = self._ceiling_failure(
            rounds=rounds,
            byte_count=byte_count,
            safe_tokens=safe_tokens,
            members=members,
            chunks=chunks,
            rows=rows,
        )
        if rejection is not None:
            return ModelSubmissionRejection(str(uuid.uuid4()), rejection)
        return KnowledgeEvidenceTurnState(
            conversation_id=state.conversation_id,
            principal_username=state.principal_username,
            scope=state.scope,
            target_type=state.target_type,
            target_id=state.target_id,
            registered_artefact_ids=state.registered_artefact_ids,
            registered_chunk_ids=state.registered_chunk_ids,
            rounds_used=rounds,
            cumulative_bytes=byte_count,
            cumulative_safe_tokens=safe_tokens,
            cumulative_members=members,
            cumulative_chunks=chunks,
            cumulative_rows=rows,
            expires_at=state.expires_at,
        )

    def _ceiling_failure(
        self,
        *,
        rounds: int,
        byte_count: int,
        safe_tokens: int,
        members: int,
        chunks: int,
        rows: int,
    ) -> str | None:
        """Return the common safe limit reason when any cumulative ceiling fails."""
        limits = self._limits
        if (
            rounds > limits.max_rounds
            or byte_count > limits.max_bytes
            or safe_tokens > limits.max_safe_tokens
            or members > limits.max_members
            or chunks > limits.max_chunks
            or rows > limits.max_rows
        ):
            return "MAT_SUB_FOLLOW_UP_LIMIT"
        return None


class KnowledgeModelSubmissionGuard:
    """Fail closed on stale model, policy, framing, or conservative budgets."""

    def __init__(
        self,
        *,
        estimator: ConservativeUtf8TokenEstimator | None = None,
        registry_reader: Callable[[int], ModelRegistrySnapshot] | None = None,
        decision_recorder: Callable[..., None] | None = None,
        context_safety_percent: int = 5,
        context_safety_min_tokens: int = 256,
        max_evidence_context_percent: int = 25,
    ) -> None:
        """Initialise final checks with injectable registry and audit boundaries."""
        if not 5 <= context_safety_percent <= 100:
            raise ValueError("context_safety_percent cannot relax the 5% minimum")
        if context_safety_min_tokens < 256:
            raise ValueError("context_safety_min_tokens cannot relax the 256 minimum")
        if not 1 <= max_evidence_context_percent <= 25:
            raise ValueError("max_evidence_context_percent cannot exceed 25")
        self._estimator = estimator or ConservativeUtf8TokenEstimator()
        self._registry_reader = registry_reader
        self._decision_recorder = decision_recorder
        self._context_safety_percent = context_safety_percent
        self._context_safety_min_tokens = context_safety_min_tokens
        self._max_evidence_context_percent = max_evidence_context_percent

    def prepare(
        self,
        request: PrepareModelSubmissionRequest,
    ) -> PreparedModelSubmission | ModelSubmissionRejection:
        """Re-read the approved model and guard the exact rendered prompt."""
        invalid = _request_identity_failure(request)
        if invalid is not None:
            return self._reject(request, invalid)
        if request.reserved_output_tokens > 2048:
            return self._reject(request, "MAT_SUB_OUTPUT_RESERVE_EXCEEDED")
        if request.reserved_output_tokens != 2048:
            return self._reject(request, "MAT_SUB_OUTPUT_RESERVE_EXCEEDED")
        approval = request.approval
        if (
            approval.policy_config_fingerprint
            != request.prompt_context.policy_config_fingerprint
        ):
            return self._reject(request, "MAT_SUB_POLICY_STALE")
        if self._registry_reader is not None:
            try:
                current_model = self._registry_reader(approval.llm_id)
            except Exception:
                return self._reject(request, "MAT_SUB_MODEL_UNAVAILABLE")
        else:
            current_model = request.model
        model_failure = _model_failure(
            approved=request.model,
            current=current_model,
            approval=approval,
        )
        if model_failure is not None:
            return self._reject(request, model_failure)
        if request.prompt.count(request.envelope.text) != 1:
            return self._reject(request, "MAT_SUB_INJECTION_BOUNDARY_FAILED")
        prompt_lines = request.prompt.splitlines()
        if sum(line == EVIDENCE_BEGIN_MARKER for line in prompt_lines) != 1:
            return self._reject(request, "MAT_SUB_INJECTION_BOUNDARY_FAILED")
        if sum(line == EVIDENCE_END_MARKER for line in prompt_lines) != 1:
            return self._reject(request, "MAT_SUB_INJECTION_BOUNDARY_FAILED")

        prompt_estimate = self._estimator.estimate_prompt(request.prompt)
        envelope_estimate = self._estimator.estimate_envelope(request.envelope.text)
        if envelope_estimate.safe_token_count != request.envelope.safe_token_count:
            return self._reject(request, "MAT_SUB_VERIFICATION_FAILED")
        maximum = current_model.max_context_tokens
        safety = max(
            math.ceil(maximum * self._context_safety_percent / 100),
            self._context_safety_min_tokens,
        )
        usable = maximum - safety - request.reserved_output_tokens
        if usable <= 0 or prompt_estimate.safe_token_count > usable:
            return self._reject(request, "MAT_SUB_CONTEXT_OVERFLOW")
        evidence_cap = usable * self._max_evidence_context_percent // 100
        if envelope_estimate.safe_token_count > evidence_cap:
            return self._reject(request, "MAT_SUB_EVIDENCE_SHARE_EXCEEDED")

        occupied = max(
            0,
            prompt_estimate.safe_token_count - envelope_estimate.safe_token_count,
        )
        prepared = PreparedModelSubmission(
            request=request,
            final_prompt_safe_tokens=prompt_estimate.safe_token_count,
            occupied_safe_tokens=occupied,
            evidence_safe_tokens=envelope_estimate.safe_token_count,
            context_safety_tokens=safety,
            invocation_options=StrictModelInvocationOptions(
                max_output_tokens=request.reserved_output_tokens,
            ),
        )
        if self._decision_recorder is not None:
            try:
                self._decision_recorder(
                    request=prepared.request,
                    prepared=prepared,
                    reason_code="MAT_SUB_APPROVED",
                )
            except Exception:
                return self._reject(request, "MAT_SUB_AUDIT_FAILURE")
        return prepared

    @staticmethod
    def _reject(
        request: PrepareModelSubmissionRequest,
        reason_code: str,
    ) -> ModelSubmissionRejection:
        """Return one content-free safe rejection."""
        return ModelSubmissionRejection(request.submission_id, reason_code)


def _request_identity_failure(request: PrepareModelSubmissionRequest) -> str | None:
    """Validate canonical IDs and immutable approval/model correlations."""
    for value in (request.submission_id, request.request_id):
        try:
            if str(uuid.UUID(str(value))) != str(value).lower():
                return "MAT_SUB_INTERNAL_FAILURE"
        except (TypeError, ValueError, AttributeError):
            return "MAT_SUB_INTERNAL_FAILURE"
    approval = request.approval
    model = request.model
    if approval.llm_id != model.llm_id:
        return "MAT_SUB_MODEL_STALE"
    if approval.registry_row_version != model.row_version:
        return "MAT_SUB_MODEL_STALE"
    if approval.context_policy_code != model.context_policy_code:
        return "MAT_SUB_POLICY_STALE"
    if not approval.principal_username.strip():
        return "MAT_SUB_PRINCIPAL_MISMATCH"
    return None


def _model_failure(
    *,
    approved: ModelRegistrySnapshot,
    current: ModelRegistrySnapshot,
    approval: MaterialisationApprovalSnapshot,
) -> str | None:
    """Return a safe reason when the exact registry row is no longer eligible."""
    if current.llm_id != approval.llm_id or current.llm_id != approved.llm_id:
        return "MAT_SUB_MODEL_STALE"
    if current.row_version != approval.registry_row_version:
        return "MAT_SUB_MODEL_STALE"
    if not current.enabled:
        return "MAT_SUB_MODEL_DISABLED"
    if not current.available:
        return "MAT_SUB_MODEL_UNAVAILABLE"
    if current.max_context_tokens <= 0:
        return "MAT_SUB_MODEL_CONTEXT_UNKNOWN"
    if current.model_type.strip().upper() != "TEXT":
        return "MAT_SUB_MEDIA_UNSUPPORTED"
    if current.processing_locality.strip().upper() != "LOCAL":
        return "MAT_SUB_LOCALITY_RESTRICTED"
    if not current.text_evidence_eligible:
        return "MAT_SUB_LOCALITY_RESTRICTED"
    if current != approved:
        return "MAT_SUB_MODEL_STALE"
    return None


def model_registry_snapshot_from_row(
    row: dict[str, Any],
    *,
    processing_locality: str,
    text_evidence_eligible: bool,
    available: bool = True,
) -> ModelRegistrySnapshot:
    """Build a strict registry snapshot from one database row and provider facts."""
    properties = row.get("PROPERTIES") or row.get("properties") or {}
    if isinstance(properties, str):
        try:
            properties = json.loads(properties)
        except json.JSONDecodeError:
            properties = {}
    model_type = "TEXT"
    if isinstance(properties, dict) and properties.get("model_type"):
        model_type = str(properties["model_type"])
    return ModelRegistrySnapshot(
        llm_id=int(row.get("LLM_ID") or row.get("llm_id")),
        row_version=int(row.get("ROW_VERSION") or row.get("row_version")),
        provider_code=str(row.get("PROVIDER") or row.get("provider") or ""),
        model_name=str(row.get("MODEL") or row.get("model") or ""),
        model_type=model_type,
        context_policy_code=str(
            row.get("CONTEXT_POLICY") or row.get("context_policy") or ""
        ).strip().upper(),
        max_context_tokens=int(
            row.get("MAX_CONTEXT_TOKENS") or row.get("max_context_tokens") or 0
        ),
        processing_locality=processing_locality,
        text_evidence_eligible=text_evidence_eligible,
        enabled=str(row.get("IS_ENABLED") or row.get("is_enabled") or "N").upper()
        == "Y",
        available=available,
    )
