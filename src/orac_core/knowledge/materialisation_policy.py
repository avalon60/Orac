"""Deterministic progressive policy for normalised knowledge materialisation."""

# Author: Clive Bostock
# Date: 14-Aug-2026
# Description: Selects the narrowest authorised bounded normalised representation.

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
import hashlib
from types import MappingProxyType
from typing import Mapping, Sequence
import uuid

from .scope import KnowledgeScope
from .repository import KnowledgeRetrievalRepository
from .token_estimation import TokenEstimate
from .token_estimation import ConservativeUtf8TokenEstimator
from .materialisation import KnowledgeMaterialisationRequest
from .materialisation import KnowledgeMaterialisationResult
from .materialisation import KnowledgeMaterialisationService
from .materialisation import KnowledgeRetrievedPart
from .models import KnowledgeSearchResult


class MaterialisationLevel(str, Enum):
    """Supported progressive normalised materialisation levels."""

    METADATA_STRUCTURE = "METADATA_STRUCTURE"
    RELEVANT_CHUNKS = "RELEVANT_CHUNKS"
    SURROUNDING_CONTEXT = "SURROUNDING_CONTEXT"
    LOGICAL_SELECTION = "LOGICAL_SELECTION"
    SELECTED_ARTEFACTS = "SELECTED_ARTEFACTS"
    COMPLETE_NORMALISED_DOCUMENT = "COMPLETE_NORMALISED_DOCUMENT"


class MaterialisationDecisionCode(str, Enum):
    """Terminal policy outcomes exposed to callers."""

    APPROVED = "APPROVED"
    DOWNGRADED = "DOWNGRADED"
    NEEDS_EVIDENCE = "NEEDS_EVIDENCE"
    REJECTED = "REJECTED"


class MaterialisationPurpose(str, Enum):
    """Controlled caller purposes used by the default-level policy."""

    INSPECT_STRUCTURE = "INSPECT_STRUCTURE"
    QUESTION_ANSWERING = "QUESTION_ANSWERING"
    FOLLOW_UP = "FOLLOW_UP"
    SUMMARISE = "SUMMARISE"
    REVIEW = "REVIEW"
    EXTRACT = "EXTRACT"
    ANALYSE = "ANALYSE"
    COMPARE = "COMPARE"


class LogicalSelectorType(str, Enum):
    """Controlled logical selector kinds backed by registered provenance."""

    SECTION = "SECTION"
    PAGE_RANGE = "PAGE_RANGE"
    SHEET = "SHEET"
    TABLE = "TABLE"
    ARTEFACT_MEMBERS = "ARTEFACT_MEMBERS"
    CELL_RANGE = "CELL_RANGE"
    CHUNK_RANGE = "CHUNK_RANGE"
    SURROUNDING_CONTEXT = "SURROUNDING_CONTEXT"


@dataclass(frozen=True, slots=True)
class LogicalMaterialisationSelector:
    """A selector expressed only with controlled identities and bounded coordinates."""

    selector_type: LogicalSelectorType
    artefact_ids: tuple[int, ...] = ()
    first_chunk_id: int | None = None
    last_chunk_id: int | None = None
    anchor_chunk_ids: tuple[int, ...] = ()
    context_before: int = 0
    context_after: int = 0
    cell_range: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    registered_provenance: bool = True

    def __post_init__(self) -> None:
        """Reject names, paths, locators, and unbounded selector values."""
        ids = (*self.artefact_ids, *self.anchor_chunk_ids)
        optional_ids = (self.first_chunk_id, self.last_chunk_id)
        if any(_invalid_positive_id(value) for value in ids):
            raise ValueError("selector identities must be positive integers")
        if any(
            value is not None and _invalid_positive_id(value)
            for value in optional_ids
        ):
            raise ValueError("chunk boundary identities must be positive integers")
        if len(set(self.artefact_ids)) != len(self.artefact_ids):
            raise ValueError("artefact identities must be unique")
        if len(set(self.anchor_chunk_ids)) != len(self.anchor_chunk_ids):
            raise ValueError("anchor chunk identities must be unique")
        if not 0 <= self.context_before <= 8 or not 0 <= self.context_after <= 8:
            raise ValueError("surrounding context must be between zero and eight")
        if self.page_start is not None or self.page_end is not None:
            if (
                _invalid_positive_id(self.page_start)
                or _invalid_positive_id(self.page_end)
            ):
                raise ValueError("page range is invalid")
            assert self.page_start is not None and self.page_end is not None
            if self.page_end < self.page_start:
                raise ValueError("page range is invalid")


@dataclass(frozen=True, slots=True)
class RagEvidenceState:
    """Existing RAG evidence sufficiency without copying retrieved evidence."""

    retrieval_id: str | None = None
    sufficient: bool = False
    result_count: int = 0
    same_authorised_scope: bool = False
    target_covered: bool = False


@dataclass(frozen=True, slots=True)
class ModelContextBudget:
    """Registry-derived model input budget available to evidence."""

    llm_id: int
    registry_row_version: int
    context_policy_code: str
    max_context_tokens: int | None
    occupied_input_tokens: int
    reserved_output_tokens: int
    processing_locality: str

    @property
    def usable_input_tokens(self) -> int | None:
        """Return remaining input tokens, or null when the registry is incomplete."""
        if self.max_context_tokens is None:
            return None
        return max(
            0,
            self.max_context_tokens
            - self.occupied_input_tokens
            - self.reserved_output_tokens,
        )


@dataclass(frozen=True, slots=True)
class MaterialisationCharacteristics:
    """Authorised metadata characteristics used without content materialisation."""

    representation_family: str
    member_count: int
    aggregate_registered_bytes: int
    available_artefact_ids: tuple[int, ...] = ()
    has_registered_structure: bool = False
    has_registered_page_provenance: bool = False
    has_registered_table_provenance: bool = False
    legacy_clob_backed: bool = False
    classification_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MaterialisationPolicyLimits:
    """Approved P1-07 limits layered inside the immutable P1-06 ceilings."""

    max_complete_bytes: int = 256 * 1024
    max_complete_tokens: int = 12000
    max_complete_context_percent: int = 25
    max_selected_artefacts: int = 32
    max_selected_chunks: int = 64
    max_surrounding_chunks_each_side: int = 2
    local_only_broad_materialisation: bool = True
    classification_enforcement_enabled: bool = False
    restricted_classification_codes: tuple[str, ...] = ()
    eligible_classification_codes: tuple[str, ...] = ()
    truncation_permitted: bool = False

    def __post_init__(self) -> None:
        """Reject limits outside the approved P1-06 and percentage ceilings."""
        if not 1 <= self.max_complete_bytes <= 4 * 1024 * 1024:
            raise ValueError("max_complete_bytes exceeds the P1-06 emitted ceiling")
        if self.max_complete_tokens <= 0:
            raise ValueError("max_complete_tokens must be positive")
        if not 1 <= self.max_complete_context_percent <= 100:
            raise ValueError("max_complete_context_percent must be between 1 and 100")
        if not 1 <= self.max_selected_artefacts <= 32:
            raise ValueError("max_selected_artefacts exceeds the P1-06 ceiling")
        if not 1 <= self.max_selected_chunks <= 64:
            raise ValueError("max_selected_chunks exceeds the P1-06 ceiling")
        if not 0 <= self.max_surrounding_chunks_each_side <= 8:
            raise ValueError("surrounding context exceeds the controlled selector ceiling")


@dataclass(frozen=True, slots=True)
class ProgressiveMaterialisationRequest:
    """Complete deterministic policy input assembled by trusted Core code."""

    principal_username: str
    scope: KnowledgeScope
    purpose: MaterialisationPurpose
    target_type: str
    target_id: int
    model_budget: ModelContextBudget
    characteristics: MaterialisationCharacteristics
    authorised: bool
    requested_level: MaterialisationLevel | None = None
    selector: LogicalMaterialisationSelector | None = None
    rag_evidence: RagEvidenceState = field(default_factory=RagEvidenceState)
    estimate: TokenEstimate | None = None
    raw_binary_requested: bool = False
    policy_config_fingerprint: str = "UNSPECIFIED"
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        """Canonicalise public identities and reject malformed policy inputs."""
        principal = str(self.principal_username).strip()
        target_type = str(self.target_type).strip().upper()
        if not principal:
            raise ValueError("principal_username is required")
        if target_type not in {
            "DOCUMENT",
            "DOCUMENT_VERSION",
            "EXTRACTION",
            "ARTEFACT",
            "CHUNK_SET",
        }:
            raise ValueError("target_type is unsupported")
        if _invalid_positive_id(self.target_id):
            raise ValueError("target_id must be a positive integer")
        try:
            canonical_uuid = str(uuid.UUID(str(self.request_id)))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("request_id must be a canonical UUID") from exc
        object.__setattr__(self, "principal_username", principal)
        object.__setattr__(self, "target_type", target_type)
        object.__setattr__(self, "request_id", canonical_uuid)


@dataclass(frozen=True, slots=True)
class MaterialisationApprovalSnapshot:
    """Immutable P1-07 approval facts required by model submission."""

    policy_request_id: str
    principal_username: str
    scope: KnowledgeScope
    target_type: str
    target_id: int
    llm_id: int
    registry_row_version: int
    context_policy_code: str
    policy_version: str
    policy_config_fingerprint: str


@dataclass(frozen=True, slots=True)
class MaterialisationDecision:
    """Safe deterministic decision contract returned to Core callers."""

    request_id: str
    decision_code: MaterialisationDecisionCode
    reason_code: str
    requested_level: MaterialisationLevel
    effective_level: MaterialisationLevel | None
    downgrade_chain: tuple[MaterialisationLevel, ...]
    complete: bool
    selected: bool
    downgraded: bool
    truncated: bool
    needs_more_evidence: bool
    estimated_bytes: int | None
    estimated_safe_tokens: int | None
    usable_context_tokens: int | None
    policy_version: str
    audit_dimensions: Mapping[str, int | str | bool | None]


class ProgressiveMaterialisationPolicy:
    """Choose the narrowest safe normalised materialisation deterministically."""

    VERSION = "P1-07.1"

    def __init__(self, limits: MaterialisationPolicyLimits | None = None) -> None:
        """Initialise the policy with approved limits."""
        self._limits = limits or MaterialisationPolicyLimits()
        if self._limits.truncation_permitted:
            raise ValueError("P1-07 does not permit truncation")

    def decide(
        self,
        request: ProgressiveMaterialisationRequest,
    ) -> MaterialisationDecision:
        """Return approval, downgrade, evidence request, or rejection."""
        requested = request.requested_level or _default_level(request)
        if request.raw_binary_requested:
            return self._decision(
                request,
                requested,
                MaterialisationDecisionCode.REJECTED,
                "MAT_RAW_BINARY_PHASE1_PROHIBITED",
                None,
                (),
            )
        if not request.authorised:
            return self._decision(
                request,
                requested,
                MaterialisationDecisionCode.REJECTED,
                "MAT_NOT_AUTHORISED",
                None,
                (),
            )
        if self._classification_restricted(request):
            return self._decision(
                request,
                requested,
                MaterialisationDecisionCode.REJECTED,
                "MAT_CLASSIFICATION_POLICY_RESTRICTED",
                None,
                (),
            )
        selector_reason = _selector_failure_reason(requested, request)
        if selector_reason is not None:
            decision_code = (
                MaterialisationDecisionCode.NEEDS_EVIDENCE
                if selector_reason == "MAT_MORE_EVIDENCE_REQUIRED"
                else MaterialisationDecisionCode.REJECTED
            )
            return self._decision(
                request,
                requested,
                decision_code,
                selector_reason,
                None,
                (),
            )

        chain = _downgrade_chain(requested)
        first_failure: str | None = None
        for index, level in enumerate(chain):
            reason = self._level_failure_reason(level, request)
            if index == 0:
                first_failure = reason
            if reason is None:
                code = (
                    MaterialisationDecisionCode.APPROVED
                    if index == 0
                    else MaterialisationDecisionCode.DOWNGRADED
                )
                return self._decision(
                    request,
                    requested,
                    code,
                    "MAT_APPROVED" if index == 0 else (
                        first_failure or "MAT_NARROWER_LEVEL_SELECTED"
                    ),
                    level,
                    chain[: index + 1],
                )

        if requested is MaterialisationLevel.RELEVANT_CHUNKS:
            return self._decision(
                request,
                requested,
                MaterialisationDecisionCode.NEEDS_EVIDENCE,
                "MAT_MORE_EVIDENCE_REQUIRED",
                None,
                chain,
            )
        return self._decision(
            request,
            requested,
            MaterialisationDecisionCode.DOWNGRADED,
            first_failure or "MAT_NARROWER_LEVEL_SELECTED",
            MaterialisationLevel.METADATA_STRUCTURE,
            (*chain, MaterialisationLevel.METADATA_STRUCTURE),
        )

    def _level_failure_reason(
        self,
        level: MaterialisationLevel,
        request: ProgressiveMaterialisationRequest,
    ) -> str | None:
        """Return a safe reason when one candidate level is not admissible."""
        if level is MaterialisationLevel.METADATA_STRUCTURE:
            return None
        if level is MaterialisationLevel.RELEVANT_CHUNKS:
            rag = request.rag_evidence
            if not (
                rag.sufficient
                and rag.result_count > 0
                and rag.same_authorised_scope
                and rag.target_covered
            ):
                return "MAT_MORE_EVIDENCE_REQUIRED"
            if rag.result_count > self._limits.max_selected_chunks:
                return "MAT_CHUNK_LIMIT_EXCEEDED"
            return self._context_failure(level, request)
        if level is MaterialisationLevel.SURROUNDING_CONTEXT:
            selector = request.selector
            if selector is None or not selector.anchor_chunk_ids:
                return "MAT_MORE_EVIDENCE_REQUIRED"
            if (
                selector.context_before > self._limits.max_surrounding_chunks_each_side
                or selector.context_after > self._limits.max_surrounding_chunks_each_side
            ):
                return "MAT_SURROUNDING_CONTEXT_LIMIT_EXCEEDED"
        if level is MaterialisationLevel.LOGICAL_SELECTION:
            selector = request.selector
            if selector is None:
                return "MAT_SELECTION_REQUIRED"
            if selector.selector_type is LogicalSelectorType.ARTEFACT_MEMBERS:
                return "MAT_NARROWER_SELECTION_UNAVAILABLE"
            selector_reason = _selector_failure_reason(level, request)
            if selector_reason is not None:
                return selector_reason
        if level is MaterialisationLevel.SELECTED_ARTEFACTS:
            selector = request.selector
            if selector is None or not selector.artefact_ids:
                return "MAT_SELECTION_REQUIRED"
            if len(selector.artefact_ids) > self._limits.max_selected_artefacts:
                return "MAT_MEMBER_LIMIT_EXCEEDED"
        if level is MaterialisationLevel.COMPLETE_NORMALISED_DOCUMENT:
            complete_failure = self._complete_failure(request)
            if complete_failure is not None:
                return complete_failure
        if (
            self._limits.local_only_broad_materialisation
            and request.model_budget.processing_locality.upper() != "LOCAL"
        ):
            return "MAT_LOCALITY_POLICY_RESTRICTED"
        return self._context_failure(level, request)

    def _classification_restricted(
        self,
        request: ProgressiveMaterialisationRequest,
    ) -> bool:
        """Return whether the target classification is ineligible for evidence."""
        if not self._limits.classification_enforcement_enabled:
            return False
        classifications = set(request.characteristics.classification_codes)
        restricted = set(self._limits.restricted_classification_codes)
        eligible = set(self._limits.eligible_classification_codes)
        return bool(
            classifications & restricted
            or (eligible and not classifications.issubset(eligible))
        )

    def _complete_failure(
        self,
        request: ProgressiveMaterialisationRequest,
    ) -> str | None:
        """Apply the approved complete-document byte, token, and fraction limits."""
        estimate = request.estimate
        byte_count = (
            estimate.byte_count
            if estimate is not None
            else request.characteristics.aggregate_registered_bytes
        )
        if byte_count > self._limits.max_complete_bytes:
            return "MAT_COMPLETE_BYTE_LIMIT_EXCEEDED"
        if estimate is None:
            return "MAT_ACCOUNTING_REQUIRED"
        if estimate.safe_token_count > self._limits.max_complete_tokens:
            return "MAT_COMPLETE_TOKEN_LIMIT_EXCEEDED"
        usable = request.model_budget.usable_input_tokens
        if usable is None or usable <= 0:
            return "MAT_MODEL_CONTEXT_UNKNOWN"
        allowed = usable * self._limits.max_complete_context_percent // 100
        if estimate.safe_token_count > allowed:
            return "MAT_COMPLETE_CONTEXT_FRACTION_EXCEEDED"
        return None

    @staticmethod
    def _context_failure(
        level: MaterialisationLevel,
        request: ProgressiveMaterialisationRequest,
    ) -> str | None:
        """Check available model context when an estimate is present."""
        usable = request.model_budget.usable_input_tokens
        if usable is None:
            return "MAT_MODEL_CONTEXT_UNKNOWN"
        requested = request.requested_level or _default_level(request)
        if (
            level is requested
            and request.estimate is not None
            and request.estimate.safe_token_count > usable
        ):
            return "MAT_MODEL_CONTEXT_LIMIT_EXCEEDED"
        return None

    def _decision(
        self,
        request: ProgressiveMaterialisationRequest,
        requested: MaterialisationLevel,
        code: MaterialisationDecisionCode,
        reason: str,
        effective: MaterialisationLevel | None,
        chain: tuple[MaterialisationLevel, ...],
    ) -> MaterialisationDecision:
        """Build a safe decision and its content-free audit dimensions."""
        estimate = request.estimate
        complete = effective is MaterialisationLevel.COMPLETE_NORMALISED_DOCUMENT
        selected = effective in {
            MaterialisationLevel.RELEVANT_CHUNKS,
            MaterialisationLevel.SURROUNDING_CONTEXT,
            MaterialisationLevel.LOGICAL_SELECTION,
            MaterialisationLevel.SELECTED_ARTEFACTS,
        }
        audit = MappingProxyType(
            {
                "purpose_code": request.purpose.value,
                "requested_level_code": requested.value,
                "effective_level_code": effective.value if effective else None,
                "decision_code": code.value,
                "reason_code": reason,
                "member_count": request.characteristics.member_count,
                "rag_result_count": request.rag_evidence.result_count,
                "classification_count": len(
                    request.characteristics.classification_codes
                ),
                "complete": complete,
                "selected": selected,
                "downgraded": code is MaterialisationDecisionCode.DOWNGRADED,
                "truncated": False,
            }
        )
        return MaterialisationDecision(
            request_id=request.request_id,
            decision_code=code,
            reason_code=reason,
            requested_level=requested,
            effective_level=effective,
            downgrade_chain=chain,
            complete=complete,
            selected=selected,
            downgraded=code is MaterialisationDecisionCode.DOWNGRADED,
            truncated=False,
            needs_more_evidence=code is MaterialisationDecisionCode.NEEDS_EVIDENCE,
            estimated_bytes=estimate.byte_count if estimate else None,
            estimated_safe_tokens=estimate.safe_token_count if estimate else None,
            usable_context_tokens=request.model_budget.usable_input_tokens,
            policy_version=self.VERSION,
            audit_dimensions=audit,
        )


class AuditedProgressiveMaterialisationPolicy:
    """Evaluate and durably audit policy decisions through the P1-06 boundary."""

    def __init__(
        self,
        *,
        policy: ProgressiveMaterialisationPolicy | None = None,
        repository: KnowledgeRetrievalRepository | None = None,
    ) -> None:
        """Initialise the deterministic policy and authorised audit repository."""
        self._policy = policy or ProgressiveMaterialisationPolicy()
        self._repository = repository or KnowledgeRetrievalRepository()

    def decide(
        self,
        request: ProgressiveMaterialisationRequest,
    ) -> MaterialisationDecision:
        """Evaluate, audit the content-free decision, and record its outcome."""
        decision = self._policy.decide(request)
        self.record(request, decision)
        return decision

    def record(
        self,
        request: ProgressiveMaterialisationRequest,
        decision: MaterialisationDecision,
    ) -> None:
        """Record an already evaluated final decision and terminal audit outcome."""
        estimate = request.estimate
        self._repository.record_policy_decision(
            policy_request_id=request.request_id,
            principal_username=request.principal_username,
            target_scope_type=request.scope.scope_type,
            target_scope_key=request.scope.scope_key,
            target_type=request.target_type,
            target_id=request.target_id,
            decision_code=decision.decision_code.value,
            reason_code=decision.reason_code,
            purpose_code=request.purpose.value,
            requested_level_code=decision.requested_level.value,
            effective_level_code=(
                decision.effective_level.value if decision.effective_level else None
            ),
            policy_version=decision.policy_version,
            estimator_code=estimate.estimator_code if estimate else None,
            estimated_byte_size=decision.estimated_bytes,
            estimated_token_count=decision.estimated_safe_tokens,
            usable_context_tokens=decision.usable_context_tokens,
            member_count=request.characteristics.member_count,
            chunk_count=request.rag_evidence.result_count or None,
            complete=decision.complete,
            selected=decision.selected,
            downgraded=decision.downgraded,
            truncated=decision.truncated,
        )
        self._repository.record_outcome(
            retrieval_id=request.request_id,
            outcome_code="COMPLETED",
            reason_code="MAT_POLICY_DECISION_RECORDED",
            member_count=request.characteristics.member_count,
            chunk_count=request.rag_evidence.result_count or None,
        )


@dataclass(frozen=True, slots=True)
class ProgressiveMaterialisationResult:
    """Policy-labelled verified result ready for later P1-08 prompt assembly."""

    decision: MaterialisationDecision
    parts: tuple[KnowledgeRetrievedPart, ...] = ()
    metadata: KnowledgeMaterialisationResult | None = None
    accounting: TokenEstimate | None = None
    approval: MaterialisationApprovalSnapshot | None = None
    verified: bool = False


class KnowledgeMaterialisationCoordinator:
    """Coordinate P1-07 policy with existing P1-06 and RAG retrieval results."""

    def __init__(
        self,
        *,
        materialisation_service: KnowledgeMaterialisationService,
        policy: ProgressiveMaterialisationPolicy,
        audited_policy: AuditedProgressiveMaterialisationPolicy,
        estimator: ConservativeUtf8TokenEstimator,
    ) -> None:
        """Initialise one policy layer over the sole authorised retrieval path."""
        self._service = materialisation_service
        self._policy = policy
        self._audited_policy = audited_policy
        self._estimator = estimator

    @staticmethod
    def characteristics_from_metadata(
        result: KnowledgeMaterialisationResult,
    ) -> MaterialisationCharacteristics:
        """Derive content-free policy characteristics from authorised metadata."""
        members = result.members
        artefact_ids = tuple(
            int(member["artefact_id"])
            for member in members
            if member.get("artefact_id") is not None
        )
        byte_count = sum(int(member.get("byte_size") or 0) for member in members)
        roles = {str(member.get("artefact_role") or "") for member in members}
        media = {str(member.get("media_type") or "") for member in members}
        representation = (
            "SPREADSHEET_PACKAGE"
            if "TABLE" in roles or any(value.startswith("text/csv") for value in media)
            else "MARKDOWN"
        )
        classification = result.metadata.get("classification_codes") or ()
        return MaterialisationCharacteristics(
            representation_family=representation,
            member_count=len(members),
            aggregate_registered_bytes=byte_count,
            available_artefact_ids=artefact_ids,
            has_registered_structure=bool(members or result.chunks),
            has_registered_page_provenance=any(
                member.get("page_start") is not None for member in members
            ),
            has_registered_table_provenance=any(
                member.get("source_cell_range") for member in members
            ),
            legacy_clob_backed=bool(result.metadata.get("legacy_provenance")),
            classification_codes=tuple(str(code) for code in classification),
        )

    def prepare(
        self,
        request: ProgressiveMaterialisationRequest,
        *,
        rag_results: Sequence[KnowledgeSearchResult] = (),
    ) -> ProgressiveMaterialisationResult:
        """Materialise the final approved level, then audit its verified accounting."""
        preflight = self._policy.decide(request)
        if preflight.decision_code in {
            MaterialisationDecisionCode.REJECTED,
            MaterialisationDecisionCode.NEEDS_EVIDENCE,
        } or preflight.effective_level is MaterialisationLevel.METADATA_STRUCTURE:
            self._audited_policy.record(request, preflight)
            return ProgressiveMaterialisationResult(
                preflight,
                accounting=request.estimate,
                approval=_approval_snapshot(request, preflight),
            )

        try:
            assert preflight.effective_level is not None
            parts, metadata = self._materialise_level(
                preflight.effective_level,
                request,
                rag_results,
            )
            verified = self._estimator.estimate_parts(
                (
                    part.content,
                    str(part.provenance.get("media_type") or "text/plain; charset=utf-8"),
                )
                for part in parts
            )
            verified_request = replace(request, estimate=verified)
            final_decision = self._policy.decide(verified_request)
            if final_decision.effective_level != preflight.effective_level:
                if final_decision.effective_level in {
                    None,
                    MaterialisationLevel.METADATA_STRUCTURE,
                }:
                    parts = ()
                    metadata = None
                    verified = self._estimator.estimate_parts(())
                else:
                    assert final_decision.effective_level is not None
                    parts, metadata = self._materialise_level(
                        final_decision.effective_level,
                        verified_request,
                        rag_results,
                    )
                    verified = self._estimator.estimate_parts(
                        (
                            part.content,
                            str(
                                part.provenance.get("media_type")
                                or "text/plain; charset=utf-8"
                            ),
                        )
                        for part in parts
                    )
                    verified_request = replace(verified_request, estimate=verified)
                    final_decision = self._policy.decide(verified_request)
            self._audited_policy.record(verified_request, final_decision)
            return ProgressiveMaterialisationResult(
                final_decision,
                parts=parts,
                metadata=metadata,
                accounting=verified,
                approval=_approval_snapshot(verified_request, final_decision),
                verified=verified.verified and bool(parts),
            )
        except (ValueError, UnicodeError) as exc:
            failed = replace(
                preflight,
                decision_code=MaterialisationDecisionCode.REJECTED,
                reason_code=_safe_coordinator_reason(exc),
                effective_level=None,
                complete=False,
                selected=False,
                downgraded=False,
                needs_more_evidence=False,
            )
            self._audited_policy.record(request, failed)
            return ProgressiveMaterialisationResult(
                failed,
                accounting=request.estimate,
                approval=_approval_snapshot(request, failed),
            )

    def prepare_target(
        self,
        *,
        principal_username: str,
        scope: KnowledgeScope,
        purpose: MaterialisationPurpose,
        target_type: str,
        target_id: int,
        model_budget: ModelContextBudget,
        requested_level: MaterialisationLevel | None = None,
        selector: LogicalMaterialisationSelector | None = None,
        rag_evidence: RagEvidenceState | None = None,
        rag_results: Sequence[KnowledgeSearchResult] = (),
        raw_binary_requested: bool = False,
        policy_config_fingerprint: str = "UNSPECIFIED",
    ) -> ProgressiveMaterialisationResult:
        """Authorise metadata, derive characteristics, decide, and materialise."""
        metadata_request = _metadata_request(
            target_type=target_type,
            target_id=target_id,
            selector=selector,
        )
        metadata = self._service.describe(
            metadata_request,
            principal_username=principal_username,
            scope=scope,
        )
        characteristics = self.characteristics_from_metadata(metadata)
        estimate = self._estimator.estimate_registered_bytes(
            characteristics.aggregate_registered_bytes,
            part_count=max(characteristics.member_count, 1),
        )
        policy_request = ProgressiveMaterialisationRequest(
            principal_username=principal_username,
            scope=scope,
            purpose=purpose,
            target_type=target_type,
            target_id=target_id,
            model_budget=model_budget,
            characteristics=characteristics,
            authorised=metadata.status == "COMPLETED",
            requested_level=requested_level,
            selector=selector,
            rag_evidence=rag_evidence or RagEvidenceState(),
            estimate=estimate,
            raw_binary_requested=raw_binary_requested,
            policy_config_fingerprint=policy_config_fingerprint,
        )
        if metadata.status != "COMPLETED":
            decision = self._policy.decide(policy_request)
            return ProgressiveMaterialisationResult(
                decision,
                metadata=metadata,
                accounting=estimate,
                approval=_approval_snapshot(policy_request, decision),
            )
        prepared = self.prepare(policy_request, rag_results=rag_results)
        if prepared.metadata is None:
            return replace(prepared, metadata=metadata)
        return prepared

    def _materialise_level(
        self,
        level: MaterialisationLevel,
        request: ProgressiveMaterialisationRequest,
        rag_results: Sequence[KnowledgeSearchResult],
    ) -> tuple[tuple[KnowledgeRetrievedPart, ...], KnowledgeMaterialisationResult | None]:
        """Materialise one level through existing RAG evidence or P1-06."""
        if level is MaterialisationLevel.RELEVANT_CHUNKS:
            return _rag_parts(request, rag_results), None
        p1_request = _p1_request_for_level(level, request)
        with self._service.open_content(
            p1_request,
            principal_username=request.principal_username,
            scope=request.scope,
        ) as stream:
            if stream.result.status != "APPROVED":
                raise ValueError(stream.result.reason_code)
            for _ in stream.iter_bytes():
                pass
            return stream.parts, stream.result


def _metadata_request(
    *,
    target_type: str,
    target_id: int,
    selector: LogicalMaterialisationSelector | None,
) -> KnowledgeMaterialisationRequest:
    """Build the initial authorised metadata request for one controlled target."""
    canonical_type = str(target_type).strip().upper()
    selection_type = "COMPLETE"
    selection: dict[str, object] = {}
    if canonical_type == "CHUNK_SET":
        if selector is None:
            raise ValueError("MAT_SELECTION_REQUIRED")
        if selector.selector_type is LogicalSelectorType.SURROUNDING_CONTEXT:
            if not selector.anchor_chunk_ids:
                raise ValueError("MAT_MORE_EVIDENCE_REQUIRED")
            selection_type = "CHUNK_CONTEXT"
            selection = {
                "first_anchor_chunk_id": selector.anchor_chunk_ids[0],
                "last_anchor_chunk_id": selector.anchor_chunk_ids[-1],
                "context_before": selector.context_before,
                "context_after": selector.context_after,
            }
        elif selector.first_chunk_id is not None and selector.last_chunk_id is not None:
            selection_type = "CHUNK_RANGE"
            selection = {
                "first_chunk_id": selector.first_chunk_id,
                "last_chunk_id": selector.last_chunk_id,
            }
        else:
            raise ValueError("MAT_SELECTION_REQUIRED")
    return KnowledgeMaterialisationRequest(
        operation="METADATA",
        target_type=canonical_type,
        target_id=target_id,
        selection_type=selection_type,
        selection=selection,
    )


def _p1_request_for_level(
    level: MaterialisationLevel,
    request: ProgressiveMaterialisationRequest,
) -> KnowledgeMaterialisationRequest:
    """Map an approved progressive level to one P1-06 controlled request."""
    selector = request.selector
    target_type = request.target_type
    target_id = request.target_id
    selection_type = "COMPLETE"
    selection: dict[str, object] = {}
    if level is MaterialisationLevel.COMPLETE_NORMALISED_DOCUMENT:
        ids = request.characteristics.available_artefact_ids
        if len(ids) > 1:
            selection_type = "MEMBERS"
            selection = {"artefact_ids": list(ids)}
    elif level is MaterialisationLevel.SELECTED_ARTEFACTS:
        if selector is None or not selector.artefact_ids:
            raise ValueError("MAT_SELECTION_REQUIRED")
        if target_type == "ARTEFACT" and selector.artefact_ids == (target_id,):
            selection_type = "COMPLETE"
        else:
            selection_type = "MEMBERS"
            selection = {"artefact_ids": list(selector.artefact_ids)}
    elif level is MaterialisationLevel.SURROUNDING_CONTEXT:
        if selector is None or not selector.anchor_chunk_ids:
            raise ValueError("MAT_MORE_EVIDENCE_REQUIRED")
        target_type = "CHUNK_SET"
        selection_type = "CHUNK_CONTEXT"
        selection = {
            "first_anchor_chunk_id": selector.anchor_chunk_ids[0],
            "last_anchor_chunk_id": selector.anchor_chunk_ids[-1],
            "context_before": selector.context_before,
            "context_after": selector.context_after,
        }
    elif level is MaterialisationLevel.LOGICAL_SELECTION:
        if selector is None:
            raise ValueError("MAT_SELECTION_REQUIRED")
        if selector.selector_type in {
            LogicalSelectorType.SHEET,
            LogicalSelectorType.TABLE,
            LogicalSelectorType.ARTEFACT_MEMBERS,
        }:
            if not selector.artefact_ids:
                raise ValueError("MAT_SELECTION_REQUIRED")
            selection_type = "MEMBERS"
            selection = {"artefact_ids": list(selector.artefact_ids)}
        elif selector.selector_type is LogicalSelectorType.CELL_RANGE:
            if len(selector.artefact_ids) != 1 or selector.cell_range is None:
                raise ValueError("MAT_SELECTION_REQUIRED")
            target_type = "ARTEFACT"
            target_id = selector.artefact_ids[0]
            selection_type = "TABLE_RANGE"
            selection = {
                "artefact_id": target_id,
                "cell_range": selector.cell_range,
            }
        elif selector.selector_type in {
            LogicalSelectorType.CHUNK_RANGE,
            LogicalSelectorType.SECTION,
        }:
            if selector.first_chunk_id is None or selector.last_chunk_id is None:
                raise ValueError("MAT_SELECTION_REQUIRED")
            target_type = "CHUNK_SET"
            selection_type = (
                "SECTION_RANGE"
                if selector.selector_type is LogicalSelectorType.SECTION
                else "CHUNK_RANGE"
            )
            selection = {
                "first_chunk_id": selector.first_chunk_id,
                "last_chunk_id": selector.last_chunk_id,
            }
        else:
            raise ValueError("MAT_SELECTOR_PROVENANCE_UNAVAILABLE")
    else:
        raise ValueError("MAT_LEVEL_UNSUPPORTED")
    return KnowledgeMaterialisationRequest(
        operation="CONTENT",
        target_type=target_type,
        target_id=target_id,
        selection_type=selection_type,
        selection=selection,
    )


def _rag_parts(
    request: ProgressiveMaterialisationRequest,
    results: Sequence[KnowledgeSearchResult],
) -> tuple[KnowledgeRetrievedPart, ...]:
    """Reuse already authorised RAG chunks after exact hash and scope checks."""
    if not results or len(results) != request.rag_evidence.result_count:
        raise ValueError("MAT_MORE_EVIDENCE_REQUIRED")
    parts: list[KnowledgeRetrievedPart] = []
    for result in results:
        if result.scope != request.scope:
            raise ValueError("MAT_NOT_AUTHORISED")
        payload = result.chunk_text.encode("utf-8")
        observed = hashlib.sha256(payload).hexdigest()
        if result.chunk_content_sha256 is None or observed != result.chunk_content_sha256:
            raise ValueError("MAT_VERIFICATION_FAILED")
        provenance = MappingProxyType(
            {
                "document_id": result.document_id,
                "document_version_id": result.document_version_id,
                "chunk_id": result.chunk_id,
                "chunk_no": result.chunk_no,
                "source_artefact_id": result.source_artefact_id,
                "extraction_id": result.extraction_id,
                "chunk_set_id": result.chunk_set_id,
                "media_type": (
                    result.source_artefact_media_type
                    or "text/plain; charset=utf-8"
                ),
                "span_start": result.span_start,
                "span_end": result.span_end,
            }
        )
        verification = MappingProxyType(
            {
                "storage_kind": "DATABASE_CHUNK",
                "status": "VERIFIED_REUSED_RAG",
                "expected_sha256": result.chunk_content_sha256,
                "observed_sha256": observed,
                "emitted_sha256": observed,
                "emitted_byte_size": len(payload),
            }
        )
        parts.append(KnowledgeRetrievedPart(payload, provenance, verification))
    return tuple(parts)


def _approval_snapshot(
    request: ProgressiveMaterialisationRequest,
    decision: MaterialisationDecision,
) -> MaterialisationApprovalSnapshot:
    """Capture the immutable policy and model facts used for one decision."""
    return MaterialisationApprovalSnapshot(
        policy_request_id=request.request_id,
        principal_username=request.principal_username,
        scope=request.scope,
        target_type=request.target_type,
        target_id=request.target_id,
        llm_id=request.model_budget.llm_id,
        registry_row_version=request.model_budget.registry_row_version,
        context_policy_code=request.model_budget.context_policy_code,
        policy_version=decision.policy_version,
        policy_config_fingerprint=request.policy_config_fingerprint,
    )


def _safe_coordinator_reason(exc: Exception) -> str:
    """Map retrieval and verification failures to bounded policy reason codes."""
    reason = str(exc)
    if reason.startswith("MAT_"):
        return reason
    if reason in {
        "RETRIEVAL_NOT_AUTHORISED",
        "RETRIEVAL_TARGET_NOT_FOUND",
        "RETRIEVAL_OBJECT_MISSING",
        "RETRIEVAL_OBJECT_CORRUPT",
        "RETRIEVAL_OBJECT_UNSAFE",
        "RETRIEVAL_LIMIT_EXCEEDED",
        "RETRIEVAL_REPRESENTATION_UNAVAILABLE",
    }:
        return "MAT_" + reason.removeprefix("RETRIEVAL_")
    return "MAT_RETRIEVAL_FAILED"


def _default_level(request: ProgressiveMaterialisationRequest) -> MaterialisationLevel:
    """Derive the approved evidence-first default from controlled purpose."""
    if request.purpose is MaterialisationPurpose.INSPECT_STRUCTURE:
        return MaterialisationLevel.METADATA_STRUCTURE
    if request.purpose in {
        MaterialisationPurpose.QUESTION_ANSWERING,
        MaterialisationPurpose.FOLLOW_UP,
    }:
        return MaterialisationLevel.RELEVANT_CHUNKS
    if request.purpose in {
        MaterialisationPurpose.SUMMARISE,
        MaterialisationPurpose.REVIEW,
    }:
        return MaterialisationLevel.COMPLETE_NORMALISED_DOCUMENT
    if request.selector is not None:
        return MaterialisationLevel.LOGICAL_SELECTION
    return MaterialisationLevel.RELEVANT_CHUNKS


def _selector_failure_reason(
    requested: MaterialisationLevel,
    request: ProgressiveMaterialisationRequest,
) -> str | None:
    """Validate that logical requests use available registered provenance."""
    selector = request.selector
    if requested not in {
        MaterialisationLevel.SURROUNDING_CONTEXT,
        MaterialisationLevel.LOGICAL_SELECTION,
        MaterialisationLevel.SELECTED_ARTEFACTS,
    }:
        return None
    if selector is None:
        return "MAT_SELECTION_REQUIRED"
    if not selector.registered_provenance:
        return "MAT_SELECTOR_PROVENANCE_UNAVAILABLE"
    if selector.selector_type is LogicalSelectorType.PAGE_RANGE:
        if not request.characteristics.has_registered_page_provenance:
            return "MAT_SELECTOR_PROVENANCE_UNAVAILABLE"
    if selector.selector_type in {LogicalSelectorType.TABLE, LogicalSelectorType.CELL_RANGE}:
        if not request.characteristics.has_registered_table_provenance:
            return "MAT_SELECTOR_PROVENANCE_UNAVAILABLE"
    if requested is MaterialisationLevel.SURROUNDING_CONTEXT:
        if selector.selector_type is not LogicalSelectorType.SURROUNDING_CONTEXT:
            return "MAT_SELECTION_REQUIRED"
        if not selector.anchor_chunk_ids:
            return "MAT_MORE_EVIDENCE_REQUIRED"
    if requested is MaterialisationLevel.SELECTED_ARTEFACTS and not selector.artefact_ids:
        return "MAT_SELECTION_REQUIRED"
    return None


def _downgrade_chain(requested: MaterialisationLevel) -> tuple[MaterialisationLevel, ...]:
    """Return the approved deterministic broad-to-narrow precedence."""
    if requested is MaterialisationLevel.RELEVANT_CHUNKS:
        return (MaterialisationLevel.RELEVANT_CHUNKS,)
    if requested is MaterialisationLevel.METADATA_STRUCTURE:
        return (MaterialisationLevel.METADATA_STRUCTURE,)
    precedence = (
        MaterialisationLevel.COMPLETE_NORMALISED_DOCUMENT,
        MaterialisationLevel.SELECTED_ARTEFACTS,
        MaterialisationLevel.LOGICAL_SELECTION,
        MaterialisationLevel.SURROUNDING_CONTEXT,
        MaterialisationLevel.RELEVANT_CHUNKS,
        MaterialisationLevel.METADATA_STRUCTURE,
    )
    return precedence[precedence.index(requested) :]


def _invalid_positive_id(value: object) -> bool:
    """Return whether a value is not a strict positive integer identity."""
    return isinstance(value, bool) or not isinstance(value, int) or value <= 0
