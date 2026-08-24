"""Securely materialise approved binary evidence into opaque attachments."""

# Author: Clive Bostock
# Date: 23-Aug-2026
# Description: Implements fail-closed P2-06 contracts and lifecycle orchestration.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import hashlib
import json
from pathlib import Path
import re
import threading
import time
from types import MappingProxyType
from typing import Any, BinaryIO, Iterator, Protocol
import uuid

from lib.fsutils import project_home

from .attachment_store import AttachmentBinding
from .attachment_store import AttachmentRecoveryReport
from .attachment_store import AttachmentRecord
from .attachment_store import AttachmentStoreError
from .attachment_store import OpaqueAttachmentStore
from .managed_store import KnowledgeManagedStore
from .managed_store import ManagedObjectIdentity
from .managed_store import ManagedStoreError
from .materialisation import KnowledgeMaterialisationRequest
from .repository import KnowledgeRetrievalRepository
from .scope import KnowledgeScope

POLICY_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
CONTROLLED_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{0,99}$")
PROCESSOR_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
MEDIA_TYPE_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9!#$&^_.+-]{0,126}/[a-z0-9][a-z0-9!#$&^_.+-]{0,126}$"
)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
GLOBAL_REQUIRED_DIMENSIONS = frozenset(
    {"BYTES", "OUTPUT_BYTES", "RETRIES", "ELAPSED_TIME"}
)
EXPANSION_DIMENSIONS = frozenset(
    {"MEMBERS", "EXPANDED_BYTES", "OBJECTS", "PAGES", "PIXELS", "CELLS", "FRAMES"}
)
DEFAULT_RUNTIME_ROOT = project_home() / "var" / "knowledge" / "attachments"


class P204Disposition(StrEnum):
    """Controlled P2-04 policy dispositions."""

    ACCEPT = "ACCEPT"
    DEFER = "DEFER"
    REJECT = "REJECT"


class P205Disposition(StrEnum):
    """Controlled P2-05 route dispositions."""

    SELECTED = "SELECTED"
    FALLBACK = "FALLBACK"
    DEFER = "DEFER"
    REJECT = "REJECT"


class P205RouteKind(StrEnum):
    """Controlled route kinds accepted from P2-05."""

    DETERMINISTIC_PROCESSOR = "DETERMINISTIC_PROCESSOR"
    SPECIALIST_MODEL = "SPECIALIST_MODEL"
    NORMALISED_EVIDENCE_FALLBACK = "NORMALISED_EVIDENCE_FALLBACK"
    PRIMARY_TEXT_COMPATIBILITY = "PRIMARY_TEXT_COMPATIBILITY"


class BinaryMaterialisationDisposition(StrEnum):
    """Public P2-06 result dispositions."""

    READY = "READY"
    DEFER = "DEFER"
    REJECT = "REJECT"


class MimeDecision(StrEnum):
    """Independent verified MIME reconciliation decisions."""

    EXACT = "EXACT"
    FAMILY = "FAMILY"
    NOT_REQUIRED = "NOT_REQUIRED"


class LimitDimension(StrEnum):
    """P2-04/P2-05 dimension-qualified materialisation bounds."""

    BYTES = "BYTES"
    OUTPUT_BYTES = "OUTPUT_BYTES"
    RETRIES = "RETRIES"
    ELAPSED_TIME = "ELAPSED_TIME"
    MEMBERS = "MEMBERS"
    EXPANDED_BYTES = "EXPANDED_BYTES"
    OBJECTS = "OBJECTS"
    PAGES = "PAGES"
    PIXELS = "PIXELS"
    CELLS = "CELLS"
    DURATION = "DURATION"
    CHANNELS = "CHANNELS"
    FRAMES = "FRAMES"


class SelectionAxis(StrEnum):
    """Controlled numeric coordinate axes; none represents a path or label."""

    BYTE = "BYTE"
    MEMBER = "MEMBER"
    PAGE = "PAGE"
    X_PIXEL = "X_PIXEL"
    Y_PIXEL = "Y_PIXEL"
    SHEET = "SHEET"
    CHART = "CHART"
    CELL_ROW = "CELL_ROW"
    CELL_COLUMN = "CELL_COLUMN"
    SLIDE = "SLIDE"
    OBJECT = "OBJECT"
    TIME_MILLISECOND = "TIME_MILLISECOND"
    CHANNEL = "CHANNEL"
    FRAME = "FRAME"


class AttachmentCleanupState(StrEnum):
    """Safe public attachment cleanup states."""

    NOT_ALLOCATED = "NOT_ALLOCATED"
    READY = "READY"
    CONSUMED = "CONSUMED"
    CLEANED = "CLEANED"
    CLEANUP_FAILED = "CLEANUP_FAILED"


@dataclass(frozen=True, slots=True)
class MaterialisationLimit:
    """One immutable maximum for an exact controlled dimension."""

    dimension: LimitDimension
    maximum: int
    unit_code: str

    def __post_init__(self) -> None:
        """Validate a non-negative dimension-qualified maximum."""
        dimension = LimitDimension(self.dimension)
        maximum = int(self.maximum)
        if maximum < 0 or (dimension != LimitDimension.RETRIES and maximum == 0):
            raise ValueError("materialisation maximum is invalid")
        unit = _controlled_code(self.unit_code, field_name="unit_code")
        object.__setattr__(self, "dimension", dimension)
        object.__setattr__(self, "maximum", maximum)
        object.__setattr__(self, "unit_code", unit)


@dataclass(frozen=True, slots=True)
class SelectionCoordinate:
    """One inclusive-exclusive numeric selection coordinate."""

    axis: SelectionAxis
    start: int
    end: int

    def __post_init__(self) -> None:
        """Reject negative, empty, or unbounded coordinates."""
        axis = SelectionAxis(self.axis)
        start = int(self.start)
        end = int(self.end)
        if start < 0 or end <= start:
            raise ValueError("selection coordinates must be finite and non-empty")
        object.__setattr__(self, "axis", axis)
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)


@dataclass(frozen=True, slots=True)
class LogicalBinarySelection:
    """Exact bounded logical selection without names, paths, URLs, or keys."""

    selection_code: str
    coordinates: tuple[SelectionCoordinate, ...]

    def __post_init__(self) -> None:
        """Canonicalise a controlled selection with unique axes."""
        code = _controlled_code(self.selection_code, field_name="selection_code")
        coordinates = tuple(self.coordinates)
        if not coordinates:
            raise ValueError("binary selection must include bounded coordinates")
        axes = [coordinate.axis for coordinate in coordinates]
        if len(axes) != len(set(axes)):
            raise ValueError("binary selection axes must be unique")
        object.__setattr__(self, "selection_code", code)
        object.__setattr__(
            self,
            "coordinates",
            tuple(sorted(coordinates, key=lambda item: item.axis.value)),
        )

    @property
    def fingerprint(self) -> str:
        """Return a deterministic selection fingerprint."""
        return _fingerprint(
            {
                "selection_code": self.selection_code,
                "coordinates": [
                    {
                        "axis": item.axis.value,
                        "start": item.start,
                        "end": item.end,
                    }
                    for item in self.coordinates
                ],
            }
        )


@dataclass(frozen=True, slots=True)
class MediaSafetyEvidence:
    """Immutable P2-04 safety evidence bound to exact source bytes."""

    evidence_id: str
    evidence_version: str
    source_fingerprint: str
    signature_valid: bool
    structure_valid: bool
    corrupt: bool = False
    encrypted: bool = False
    active_content: bool = False
    external_references: bool = False
    nested_content: bool = False
    expansion_risk: bool = False

    def __post_init__(self) -> None:
        """Validate controlled identity and exact source binding."""
        _canonical_uuid(self.evidence_id, field_name="evidence_id")
        _policy_version(self.evidence_version, field_name="evidence_version")
        _canonical_sha256(self.source_fingerprint, field_name="source_fingerprint")

    @property
    def fingerprint(self) -> str:
        """Return the immutable safety-evidence fingerprint."""
        return _fingerprint(
            {
                "evidence_id": self.evidence_id,
                "evidence_version": self.evidence_version,
                "source_fingerprint": self.source_fingerprint,
                "signature_valid": self.signature_valid,
                "structure_valid": self.structure_valid,
                "corrupt": self.corrupt,
                "encrypted": self.encrypted,
                "active_content": self.active_content,
                "external_references": self.external_references,
                "nested_content": self.nested_content,
                "expansion_risk": self.expansion_risk,
            }
        )


@dataclass(frozen=True, slots=True)
class P204PolicyApproval:
    """Immutable accepted P2-04 result consumed without widening."""

    result_id: str
    policy_version: str
    disposition: P204Disposition
    reason_code: str
    source_authorisation_fingerprint: str
    verified_representation: str
    declared_mime_type: str
    detected_mime_type: str
    mime_decision: MimeDecision
    selection: LogicalBinarySelection
    limits: tuple[MaterialisationLimit, ...]
    transformation_chain: tuple[str, ...]
    required_output_representation: str
    safety_evidence: MediaSafetyEvidence
    evaluated_at: datetime
    expires_at: datetime
    fingerprint: str = ""

    def __post_init__(self) -> None:
        """Canonicalise and verify the immutable policy fingerprint."""
        _canonical_uuid(self.result_id, field_name="result_id")
        version = _policy_version(self.policy_version, field_name="policy_version")
        disposition = P204Disposition(self.disposition)
        reason = _controlled_code(self.reason_code, field_name="reason_code")
        source_authorisation = _canonical_sha256(
            self.source_authorisation_fingerprint,
            field_name="source_authorisation_fingerprint",
        )
        representation = _processor_code(
            self.verified_representation,
            field_name="verified_representation",
        )
        output_representation = _processor_code(
            self.required_output_representation,
            field_name="required_output_representation",
        )
        declared_mime = _media_type(self.declared_mime_type)
        detected_mime = _media_type(self.detected_mime_type)
        limits = _canonical_limits(self.limits)
        chain = tuple(
            _controlled_code(item, field_name="transformation_chain")
            for item in self.transformation_chain
        )
        if not chain:
            raise ValueError("transformation_chain must not be empty")
        evaluated_at = _utc_datetime(self.evaluated_at, field_name="evaluated_at")
        expires_at = _utc_datetime(self.expires_at, field_name="expires_at")
        if expires_at <= evaluated_at:
            raise ValueError("P2-04 approval must have a positive lifetime")
        object.__setattr__(self, "policy_version", version)
        object.__setattr__(self, "disposition", disposition)
        object.__setattr__(self, "reason_code", reason)
        object.__setattr__(
            self, "source_authorisation_fingerprint", source_authorisation
        )
        object.__setattr__(self, "verified_representation", representation)
        object.__setattr__(
            self, "required_output_representation", output_representation
        )
        object.__setattr__(self, "declared_mime_type", declared_mime)
        object.__setattr__(self, "detected_mime_type", detected_mime)
        object.__setattr__(self, "mime_decision", MimeDecision(self.mime_decision))
        object.__setattr__(self, "limits", limits)
        object.__setattr__(self, "transformation_chain", chain)
        object.__setattr__(self, "evaluated_at", evaluated_at)
        object.__setattr__(self, "expires_at", expires_at)
        expected = self.expected_fingerprint()
        supplied = str(self.fingerprint)
        if supplied and supplied != expected:
            raise ValueError("P2-04 policy fingerprint does not match its fields")
        object.__setattr__(self, "fingerprint", expected)

    def expected_fingerprint(self) -> str:
        """Compute the canonical fingerprint from all authoritative fields."""
        return _fingerprint(
            {
                "result_id": self.result_id,
                "policy_version": self.policy_version,
                "disposition": self.disposition.value,
                "reason_code": self.reason_code,
                "source_authorisation_fingerprint": self.source_authorisation_fingerprint,
                "verified_representation": self.verified_representation,
                "declared_mime_type": self.declared_mime_type,
                "detected_mime_type": self.detected_mime_type,
                "mime_decision": self.mime_decision.value,
                "selection_fingerprint": self.selection.fingerprint,
                "limits_fingerprint": limits_fingerprint(self.limits),
                "transformation_chain": list(self.transformation_chain),
                "required_output_representation": self.required_output_representation,
                "safety_evidence_fingerprint": self.safety_evidence.fingerprint,
                "evaluated_at": self.evaluated_at.isoformat(),
                "expires_at": self.expires_at.isoformat(),
            }
        )


@dataclass(frozen=True, slots=True)
class ProcessorProfileIdentity:
    """Exact reviewed deterministic processor/profile/version identity."""

    processor_code: str
    profile_code: str
    version: str

    def __post_init__(self) -> None:
        """Validate the controlled immutable processor identity."""
        object.__setattr__(
            self,
            "processor_code",
            _processor_code(self.processor_code, field_name="processor_code"),
        )
        object.__setattr__(
            self,
            "profile_code",
            _processor_code(self.profile_code, field_name="profile_code"),
        )
        object.__setattr__(
            self,
            "version",
            _policy_version(self.version, field_name="processor_version"),
        )

    @property
    def key(self) -> tuple[str, str, str]:
        """Return the exact registry key."""
        return self.processor_code, self.profile_code, self.version


@dataclass(frozen=True, slots=True)
class P205RouteApproval:
    """Immutable P2-05 selected or approved fallback route result."""

    result_id: str
    route_policy_version: str
    disposition: P205Disposition
    reason_code: str
    route_kind: P205RouteKind
    route_identity: str
    processor: ProcessorProfileIdentity
    policy_fingerprint: str
    selection_fingerprint: str
    limits_fingerprint: str
    evidence_fingerprint: str
    fallback_chain_id: str
    fallback_step: int
    locality_decision_id: str
    classification_decision_id: str
    consent_decision_id: str
    minimisation_decision_id: str
    evaluated_at: datetime
    expires_at: datetime
    fingerprint: str = ""

    def __post_init__(self) -> None:
        """Canonicalise and verify the immutable route fingerprint."""
        for name in (
            "result_id",
            "fallback_chain_id",
            "locality_decision_id",
            "classification_decision_id",
            "consent_decision_id",
            "minimisation_decision_id",
        ):
            _canonical_uuid(getattr(self, name), field_name=name)
        object.__setattr__(
            self,
            "route_policy_version",
            _policy_version(
                self.route_policy_version,
                field_name="route_policy_version",
            ),
        )
        object.__setattr__(self, "disposition", P205Disposition(self.disposition))
        object.__setattr__(self, "route_kind", P205RouteKind(self.route_kind))
        object.__setattr__(
            self,
            "reason_code",
            _controlled_code(self.reason_code, field_name="reason_code"),
        )
        object.__setattr__(
            self,
            "route_identity",
            _controlled_code(self.route_identity, field_name="route_identity"),
        )
        for name in (
            "policy_fingerprint",
            "selection_fingerprint",
            "limits_fingerprint",
            "evidence_fingerprint",
        ):
            _canonical_sha256(getattr(self, name), field_name=name)
        fallback_step = int(self.fallback_step)
        if fallback_step < 0:
            raise ValueError("fallback_step must be zero or greater")
        object.__setattr__(self, "fallback_step", fallback_step)
        evaluated_at = _utc_datetime(self.evaluated_at, field_name="evaluated_at")
        expires_at = _utc_datetime(self.expires_at, field_name="expires_at")
        if expires_at <= evaluated_at:
            raise ValueError("P2-05 route must have a positive lifetime")
        object.__setattr__(self, "evaluated_at", evaluated_at)
        object.__setattr__(self, "expires_at", expires_at)
        expected = self.expected_fingerprint()
        supplied = str(self.fingerprint)
        if supplied and supplied != expected:
            raise ValueError("P2-05 route fingerprint does not match its fields")
        object.__setattr__(self, "fingerprint", expected)

    def expected_fingerprint(self) -> str:
        """Compute the canonical route fingerprint."""
        return _fingerprint(
            {
                "result_id": self.result_id,
                "route_policy_version": self.route_policy_version,
                "disposition": self.disposition.value,
                "reason_code": self.reason_code,
                "route_kind": self.route_kind.value,
                "route_identity": self.route_identity,
                "processor": list(self.processor.key),
                "policy_fingerprint": self.policy_fingerprint,
                "selection_fingerprint": self.selection_fingerprint,
                "limits_fingerprint": self.limits_fingerprint,
                "evidence_fingerprint": self.evidence_fingerprint,
                "fallback_chain_id": self.fallback_chain_id,
                "fallback_step": self.fallback_step,
                "locality_decision_id": self.locality_decision_id,
                "classification_decision_id": self.classification_decision_id,
                "consent_decision_id": self.consent_decision_id,
                "minimisation_decision_id": self.minimisation_decision_id,
                "evaluated_at": self.evaluated_at.isoformat(),
                "expires_at": self.expires_at.isoformat(),
            }
        )


@dataclass(frozen=True, slots=True)
class BinaryMaterialisationRequest:
    """Complete immutable P2-06 input without caller locators or payloads."""

    request_id: str
    correlation_id: str
    audit_id: str
    cancellation_id: str
    principal_username: str = field(repr=False)
    scope: KnowledgeScope
    document_version_id: int
    extraction_id: int
    artefact_id: int
    expected_byte_size: int
    expected_sha256: str
    source_fingerprint: str
    policy: P204PolicyApproval
    route: P205RouteApproval
    expires_at: datetime
    cleanup_deadline: datetime
    fingerprint: str = ""

    def __post_init__(self) -> None:
        """Validate identities and verify the complete request fingerprint."""
        for name in ("request_id", "correlation_id", "audit_id", "cancellation_id"):
            _canonical_uuid(getattr(self, name), field_name=name)
        principal = str(self.principal_username).strip()
        if (
            not principal
            or len(principal) > 128
            or any(ord(char) < 32 for char in principal)
        ):
            raise ValueError("principal_username is invalid")
        for name in ("document_version_id", "extraction_id", "artefact_id"):
            value = int(getattr(self, name))
            if value < 1:
                raise ValueError(f"{name} must be positive")
            object.__setattr__(self, name, value)
        expected_byte_size = int(self.expected_byte_size)
        if expected_byte_size < 0:
            raise ValueError("expected_byte_size must be zero or greater")
        object.__setattr__(self, "expected_byte_size", expected_byte_size)
        _canonical_sha256(self.expected_sha256, field_name="expected_sha256")
        _canonical_sha256(self.source_fingerprint, field_name="source_fingerprint")
        expires_at = _utc_datetime(self.expires_at, field_name="expires_at")
        cleanup_deadline = _utc_datetime(
            self.cleanup_deadline,
            field_name="cleanup_deadline",
        )
        if cleanup_deadline < expires_at:
            raise ValueError("cleanup_deadline cannot precede expires_at")
        object.__setattr__(self, "principal_username", principal)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(self, "cleanup_deadline", cleanup_deadline)
        expected = self.expected_fingerprint()
        supplied = str(self.fingerprint)
        if supplied and supplied != expected:
            raise ValueError("materialisation request fingerprint is invalid")
        object.__setattr__(self, "fingerprint", expected)

    @property
    def principal_fingerprint(self) -> str:
        """Return a content-free principal binding."""
        return hashlib.sha256(
            self.principal_username.casefold().encode("utf-8")
        ).hexdigest()

    def expected_fingerprint(self) -> str:
        """Compute the complete request fingerprint."""
        return _fingerprint(
            {
                "request_id": self.request_id,
                "correlation_id": self.correlation_id,
                "audit_id": self.audit_id,
                "cancellation_id": self.cancellation_id,
                "principal_fingerprint": self.principal_fingerprint,
                "scope_type": self.scope.scope_type,
                "scope_key": self.scope.scope_key,
                "document_version_id": self.document_version_id,
                "extraction_id": self.extraction_id,
                "artefact_id": self.artefact_id,
                "expected_byte_size": self.expected_byte_size,
                "expected_sha256": self.expected_sha256,
                "source_fingerprint": self.source_fingerprint,
                "policy_fingerprint": self.policy.fingerprint,
                "route_fingerprint": self.route.fingerprint,
                "expires_at": self.expires_at.isoformat(),
                "cleanup_deadline": self.cleanup_deadline.isoformat(),
            }
        )


@dataclass(frozen=True, slots=True)
class ProcessorInspection:
    """Deterministic inspection of the same opened source descriptor."""

    verified_representation: str
    detected_mime_type: str
    mime_decision: MimeDecision
    measurements: tuple[MaterialisationLimit, ...]
    signature_valid: bool
    structure_valid: bool
    corrupt: bool = False
    encrypted: bool = False
    active_content: bool = False
    external_references: bool = False
    nested_content: bool = False
    expansion_risk: bool = False

    def __post_init__(self) -> None:
        """Canonicalise bounded processor inspection evidence."""
        object.__setattr__(
            self,
            "verified_representation",
            _processor_code(
                self.verified_representation,
                field_name="verified_representation",
            ),
        )
        object.__setattr__(
            self, "detected_mime_type", _media_type(self.detected_mime_type)
        )
        object.__setattr__(self, "mime_decision", MimeDecision(self.mime_decision))
        object.__setattr__(self, "measurements", _canonical_limits(self.measurements))


@dataclass(frozen=True, slots=True)
class DeterministicDerivativeEvidence:
    """Content-free deterministic derivative identity and provenance."""

    derivative_id: str
    output_representation: str
    processor: ProcessorProfileIdentity
    authoritative: bool
    provenance_fingerprint: str

    def __post_init__(self) -> None:
        """Validate derivative identity and provenance fingerprint."""
        _canonical_uuid(self.derivative_id, field_name="derivative_id")
        object.__setattr__(
            self,
            "output_representation",
            _processor_code(
                self.output_representation,
                field_name="output_representation",
            ),
        )
        _canonical_sha256(
            self.provenance_fingerprint,
            field_name="provenance_fingerprint",
        )


class DeterministicBinaryProcessor(Protocol):
    """Future approved deterministic processor seam; no implementation is built in."""

    def inspect(
        self,
        source: BinaryIO,
        *,
        selection: LogicalBinarySelection,
        limits: Mapping[LimitDimension, int],
        check_terminal: Callable[[], None],
    ) -> ProcessorInspection:
        """Inspect the exact verified descriptor without executing content."""
        ...

    def materialise(
        self,
        source: BinaryIO,
        sink: BinaryIO,
        *,
        selection: LogicalBinarySelection,
        limits: Mapping[LimitDimension, int],
        check_terminal: Callable[[], None],
    ) -> DeterministicDerivativeEvidence:
        """Write only the approved selection to the bounded sink."""
        ...


@dataclass(frozen=True, slots=True)
class ApprovedProcessorProfile:
    """Host-owned exact processor registration supplied after separate review."""

    identity: ProcessorProfileIdentity
    media_family_code: str
    input_representation: str
    output_representation: str
    accepted_mime_types: frozenset[str]
    required_dimensions: frozenset[LimitDimension]
    allowed_selection_codes: frozenset[str]
    processor: DeterministicBinaryProcessor = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        """Validate a complete, bounded host-owned profile."""
        object.__setattr__(
            self,
            "media_family_code",
            _controlled_code(self.media_family_code, field_name="media_family_code"),
        )
        object.__setattr__(
            self,
            "input_representation",
            _processor_code(
                self.input_representation, field_name="input_representation"
            ),
        )
        object.__setattr__(
            self,
            "output_representation",
            _processor_code(
                self.output_representation, field_name="output_representation"
            ),
        )
        mime_types = frozenset(_media_type(value) for value in self.accepted_mime_types)
        if not mime_types:
            raise ValueError("approved processor profile requires MIME constraints")
        required = frozenset(
            LimitDimension(value) for value in self.required_dimensions
        )
        required = required | frozenset(
            LimitDimension(value) for value in GLOBAL_REQUIRED_DIMENSIONS
        )
        selection_codes = frozenset(
            _controlled_code(value, field_name="allowed_selection_codes")
            for value in self.allowed_selection_codes
        )
        if not selection_codes:
            raise ValueError("approved processor profile requires selection codes")
        object.__setattr__(self, "accepted_mime_types", mime_types)
        object.__setattr__(self, "required_dimensions", required)
        object.__setattr__(self, "allowed_selection_codes", selection_codes)


@dataclass(frozen=True, slots=True)
class RouteRevalidation:
    """Fresh P2-05 route-authority result immediately before byte access."""

    approved: bool
    reason_code: str
    route_fingerprint: str
    policy_fingerprint: str
    evaluated_at: datetime

    def __post_init__(self) -> None:
        """Validate safe current route-revalidation evidence."""
        object.__setattr__(
            self,
            "reason_code",
            _controlled_code(self.reason_code, field_name="reason_code"),
        )
        _canonical_sha256(self.route_fingerprint, field_name="route_fingerprint")
        _canonical_sha256(self.policy_fingerprint, field_name="policy_fingerprint")
        object.__setattr__(
            self,
            "evaluated_at",
            _utc_datetime(self.evaluated_at, field_name="evaluated_at"),
        )


class RouteRevalidator(Protocol):
    """Revalidate route, policy, locality, classification, and expiry."""

    def revalidate(
        self,
        request: BinaryMaterialisationRequest,
        *,
        evaluated_at: datetime,
    ) -> RouteRevalidation:
        """Return a fresh fail-closed decision without provider side effects."""
        ...


class FailClosedRouteRevalidator:
    """Default authority while no P2-05 production routing runtime exists."""

    def revalidate(
        self,
        request: BinaryMaterialisationRequest,
        *,
        evaluated_at: datetime,
    ) -> RouteRevalidation:
        """Defer every route without inspecting any provider or model."""
        return RouteRevalidation(
            approved=False,
            reason_code="MAT_ROUTE_REVALIDATOR_UNAVAILABLE",
            route_fingerprint=request.route.fingerprint,
            policy_fingerprint=request.policy.fingerprint,
            evaluated_at=evaluated_at,
        )


@dataclass(frozen=True, slots=True)
class AuthorisedBinarySource:
    """Private registered descriptor returned by the Core retrieval boundary."""

    document_version_id: int
    extraction_id: int
    artefact_id: int
    media_type: str
    identity: ManagedObjectIdentity
    source_fingerprint: str
    output_set_complete: bool
    storage_key: str = field(repr=False)


class CoreBinarySourceResolver:
    """Re-authorise one exact artefact through the existing Core package API."""

    def __init__(
        self,
        repository: KnowledgeRetrievalRepository | None = None,
    ) -> None:
        """Initialise the resolver with the authorised retrieval repository."""
        self._repository = repository or KnowledgeRetrievalRepository()

    def resolve(self, request: BinaryMaterialisationRequest) -> AuthorisedBinarySource:
        """Resolve one exact registered artefact without exposing its locator."""
        retrieval_request = KnowledgeMaterialisationRequest(
            operation="CONTENT",
            target_type="ARTEFACT",
            target_id=request.artefact_id,
            selection_type="COMPLETE",
            retrieval_id=request.audit_id,
        )
        resolution, rows = self._repository.resolve_request(
            retrieval_id=request.audit_id,
            principal_username=request.principal_username,
            target_scope_type=request.scope.scope_type,
            target_scope_key=request.scope.scope_key,
            request_json=retrieval_request.to_json(),
        )
        if str(resolution.get("status")) != "APPROVED":
            reason = str(
                resolution.get("reason_code") or "MAT_SOURCE_AUTHORISATION_CHANGED"
            )
            raise BinaryMaterialisationError(
                _safe_source_reason(reason),
                "Registered source authorisation failed.",
                disposition=BinaryMaterialisationDisposition.REJECT,
                audited=False,
            )
        if len(rows) != 1:
            raise BinaryMaterialisationError(
                "MAT_SOURCE_IDENTITY_CHANGED",
                "Registered source identity is incomplete or ambiguous.",
                disposition=BinaryMaterialisationDisposition.REJECT,
            )
        row = rows[0]
        try:
            document_version_id = int(row["document_version_id"])
            extraction_id = int(row["extraction_id"])
            artefact_id = int(row["artefact_id"])
            media_type = _media_type(str(row["artefact_media_type"]))
            identity = ManagedObjectIdentity(
                str(row["artefact_content_sha256"]),
                int(row["artefact_byte_size"]),
            )
            storage_key = str(row["artefact_storage_key"])
            complete = str(row.get("output_set_complete_yn") or "N") == "Y"
        except (KeyError, TypeError, ValueError) as exc:
            raise BinaryMaterialisationError(
                "MAT_SOURCE_IDENTITY_CHANGED",
                "Registered source descriptor is invalid.",
                disposition=BinaryMaterialisationDisposition.REJECT,
            ) from exc
        fingerprint = source_identity_fingerprint(
            document_version_id=document_version_id,
            extraction_id=extraction_id,
            artefact_id=artefact_id,
            byte_size=identity.byte_size,
            sha256=identity.sha256,
            media_type=media_type,
        )
        return AuthorisedBinarySource(
            document_version_id=document_version_id,
            extraction_id=extraction_id,
            artefact_id=artefact_id,
            media_type=media_type,
            identity=identity,
            source_fingerprint=fingerprint,
            output_set_complete=complete,
            storage_key=storage_key,
        )

    def record_outcome(
        self,
        *,
        request: BinaryMaterialisationRequest,
        outcome_code: str,
        reason_code: str,
        byte_size: int | None = None,
        sha256: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Record one bounded terminal outcome through the existing audit API."""
        self._repository.record_outcome(
            retrieval_id=request.audit_id,
            outcome_code=outcome_code,
            reason_code=reason_code,
            returned_byte_size=byte_size,
            returned_sha256=sha256,
            member_count=1 if byte_size is not None else None,
            duration_ms=duration_ms,
        )


@dataclass(frozen=True, slots=True)
class BinaryMaterialisationConfiguration:
    """Private host-owned P2-06 runtime and recovery configuration."""

    enabled: bool
    runtime_root: Path
    max_source_bytes: int = 16 * 1024 * 1024
    max_output_bytes: int = 16 * 1024 * 1024
    max_elapsed_seconds: int = 30
    max_ttl_seconds: int = 300
    max_cleanup_grace_seconds: int = 60
    max_recovery_entries: int = 4096
    max_recovery_elapsed_seconds: int = 10
    stale_allocation_seconds: int = 300

    def __post_init__(self) -> None:
        """Reject missing or non-positive host ceilings."""
        object.__setattr__(self, "runtime_root", Path(self.runtime_root).expanduser())
        for name in (
            "max_source_bytes",
            "max_output_bytes",
            "max_elapsed_seconds",
            "max_ttl_seconds",
            "max_cleanup_grace_seconds",
            "max_recovery_entries",
            "max_recovery_elapsed_seconds",
            "stale_allocation_seconds",
        ):
            value = int(getattr(self, name))
            if value < 1:
                raise ValueError(f"{name} must be positive")
            object.__setattr__(self, name, value)

    @classmethod
    def from_config(cls, config_mgr: object) -> "BinaryMaterialisationConfiguration":
        """Load the narrow P2-06 configuration without secret access."""
        section = "knowledge.binary_materialisation"
        bool_loader = getattr(config_mgr, "bool_config_value")
        int_loader = getattr(config_mgr, "int_config_value")
        path_loader = getattr(config_mgr, "path_config_value")
        return cls(
            enabled=bool_loader(section, "enabled", default=False),
            runtime_root=Path(
                path_loader(
                    section,
                    "runtime_root",
                    default=str(DEFAULT_RUNTIME_ROOT),
                    suppress_warnings=True,
                )
            ),
            max_source_bytes=int_loader(
                section,
                "max_source_bytes",
                default=16 * 1024 * 1024,
            ),
            max_output_bytes=int_loader(
                section,
                "max_output_bytes",
                default=16 * 1024 * 1024,
            ),
            max_elapsed_seconds=int_loader(
                section,
                "max_elapsed_seconds",
                default=30,
            ),
            max_ttl_seconds=int_loader(section, "max_ttl_seconds", default=300),
            max_cleanup_grace_seconds=int_loader(
                section,
                "max_cleanup_grace_seconds",
                default=60,
            ),
            max_recovery_entries=int_loader(
                section,
                "max_recovery_entries",
                default=4096,
            ),
            max_recovery_elapsed_seconds=int_loader(
                section,
                "max_recovery_elapsed_seconds",
                default=10,
            ),
            stale_allocation_seconds=int_loader(
                section,
                "stale_allocation_seconds",
                default=300,
            ),
        )


@dataclass(frozen=True, slots=True)
class BinaryMaterialisationResult:
    """Content-free P2-06 result and opaque handle metadata."""

    disposition: BinaryMaterialisationDisposition
    reason_code: str
    attachment_id: str | None
    request_fingerprint: str
    route_fingerprint: str
    policy_fingerprint: str
    source_fingerprint: str
    selection_fingerprint: str
    verified_representation: str
    mime_decision: MimeDecision
    byte_size: int | None
    sha256: str | None
    applied_limits: tuple[MaterialisationLimit, ...]
    derivative: DeterministicDerivativeEvidence | None
    created_at: datetime | None
    expires_at: datetime | None
    consumed_at: datetime | None
    cleanup_state: AttachmentCleanupState
    audit_fields: Mapping[str, Any]


class BinaryMaterialisationError(RuntimeError):
    """Stable internal failure with public disposition and audit state."""

    def __init__(
        self,
        reason_code: str,
        message: str,
        *,
        disposition: BinaryMaterialisationDisposition,
        audited: bool = True,
    ) -> None:
        """Initialise a reason-coded fail-closed materialisation error."""
        super().__init__(message)
        self.reason_code = _controlled_code(reason_code, field_name="reason_code")
        self.disposition = BinaryMaterialisationDisposition(disposition)
        self.audited = audited


class SecureBinaryMaterialisationService:
    """Revalidate, inspect, materialise, bind, consume, and clean P2-06 bytes."""

    def __init__(
        self,
        *,
        managed_store: KnowledgeManagedStore,
        configuration: BinaryMaterialisationConfiguration,
        source_resolver: CoreBinarySourceResolver | None = None,
        route_revalidator: RouteRevalidator | None = None,
        processor_profiles: Sequence[ApprovedProcessorProfile] = (),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Initialise immutable dependencies with no built-in eligible profile."""
        self._managed_store = managed_store
        self._configuration = configuration
        self._source_resolver = source_resolver or CoreBinarySourceResolver()
        self._route_revalidator = route_revalidator or FailClosedRouteRevalidator()
        self._clock = clock or _now_utc
        profiles: dict[tuple[str, str, str], ApprovedProcessorProfile] = {}
        for profile in processor_profiles:
            if profile.identity.key in profiles:
                raise ValueError("processor profile identities must be unique")
            profiles[profile.identity.key] = profile
        self._profiles = MappingProxyType(profiles)
        self._attachment_store = OpaqueAttachmentStore(
            configuration.runtime_root,
            max_recovery_entries=configuration.max_recovery_entries,
            max_recovery_elapsed_seconds=configuration.max_recovery_elapsed_seconds,
            stale_allocation_seconds=configuration.stale_allocation_seconds,
        )
        self._lock = threading.RLock()
        self._results: dict[str, BinaryMaterialisationResult] = {}
        self._bindings: dict[str, AttachmentBinding] = {}

    def reconcile_startup(self) -> AttachmentRecoveryReport:
        """Run bounded startup recovery without following or deleting ambiguity."""
        return self._attachment_store.reconcile(now=self._clock())

    def shutdown(self) -> AttachmentRecoveryReport:
        """Clean current live handles during bounded service shutdown."""
        return self._attachment_store.shutdown()

    def materialise(
        self,
        request: BinaryMaterialisationRequest,
        *,
        cancelled: Callable[[], bool] | None = None,
    ) -> BinaryMaterialisationResult:
        """Create one opaque attachment from an exact approved P2-05 route."""
        cancellation_check = cancelled or (lambda: False)
        with self._lock:
            prior = self._results.get(request.request_id)
            if prior is not None:
                if prior.request_fingerprint == request.fingerprint:
                    if (
                        prior.disposition == BinaryMaterialisationDisposition.READY
                        and prior.attachment_id is not None
                        and self._attachment_store.status(prior.attachment_id) is None
                    ):
                        return replace(
                            prior,
                            disposition=BinaryMaterialisationDisposition.REJECT,
                            reason_code="MAT_ATTACHMENT_ALREADY_CONSUMED",
                            cleanup_state=AttachmentCleanupState.CLEANED,
                        )
                    return prior
                return self._failure_result(
                    request,
                    reason_code="MAT_ATTACHMENT_BINDING_CONFLICT",
                    disposition=BinaryMaterialisationDisposition.REJECT,
                )
            started_monotonic = time.monotonic()
            audited = False
            allocated_attachment_id: str | None = None
            try:
                now = self._clock()
                self._validate_request(request, now=now)
                profile = self._profile_for(request)
                limits = self._effective_limits(request, profile)
                elapsed_limit = limits[LimitDimension.ELAPSED_TIME]
                deadline = min(
                    started_monotonic + elapsed_limit,
                    started_monotonic + self._configuration.max_elapsed_seconds,
                )

                def check_terminal() -> None:
                    if cancellation_check():
                        raise BinaryMaterialisationError(
                            "MAT_CANCELLED",
                            "Materialisation was cancelled.",
                            disposition=BinaryMaterialisationDisposition.REJECT,
                        )
                    if self._clock() >= min(
                        request.policy.expires_at,
                        request.route.expires_at,
                        request.expires_at,
                    ):
                        raise BinaryMaterialisationError(
                            "MAT_APPROVAL_STALE",
                            "Materialisation approval expired during processing.",
                            disposition=BinaryMaterialisationDisposition.DEFER,
                        )
                    if time.monotonic() >= deadline:
                        raise BinaryMaterialisationError(
                            "MAT_ELAPSED_TIME_EXPIRED",
                            "Materialisation elapsed-time limit expired.",
                            disposition=BinaryMaterialisationDisposition.REJECT,
                        )

                check_terminal()
                revalidation = self._route_revalidator.revalidate(
                    request,
                    evaluated_at=now,
                )
                self._validate_route_revalidation(
                    request,
                    revalidation,
                    evaluated_at=now,
                )
                check_terminal()
                source = self._source_resolver.resolve(request)
                audited = True
                self._validate_source(request, source)
                if source.identity.byte_size > limits[LimitDimension.BYTES]:
                    raise BinaryMaterialisationError(
                        "MAT_BOUND_EXCEEDED",
                        "Registered source exceeds its approved byte bound.",
                        disposition=BinaryMaterialisationDisposition.REJECT,
                    )
                check_terminal()
                with self._managed_store.open_verified(
                    source.storage_key,
                    source.identity,
                ) as stream:
                    inspection = profile.processor.inspect(
                        stream,
                        selection=request.policy.selection,
                        limits=limits,
                        check_terminal=check_terminal,
                    )
                    self._validate_inspection(
                        request,
                        profile,
                        inspection,
                        limits=limits,
                    )
                    check_terminal()
                    stream.seek(0)
                    binding = self._attachment_binding(request, created_at=now)

                    def writer(sink: BinaryIO) -> DeterministicDerivativeEvidence:
                        derivative = profile.processor.materialise(
                            stream,
                            sink,
                            selection=request.policy.selection,
                            limits=limits,
                            check_terminal=check_terminal,
                        )
                        if derivative.processor != profile.identity:
                            raise AttachmentStoreError(
                                "MAT_PROCESSOR_PROVENANCE_INVALID",
                                "Processor derivative identity did not match its profile.",
                            )
                        if (
                            derivative.output_representation
                            != profile.output_representation
                        ):
                            raise AttachmentStoreError(
                                "MAT_PROCESSOR_PROVENANCE_INVALID",
                                "Processor output representation did not match its profile.",
                            )
                        return derivative

                    write_result = self._attachment_store.bind(
                        binding=binding,
                        max_output_bytes=limits[LimitDimension.OUTPUT_BYTES],
                        deadline_monotonic=deadline,
                        cancelled=cancellation_check,
                        writer=writer,
                    )
                derivative = write_result.writer_result
                if not isinstance(derivative, DeterministicDerivativeEvidence):
                    raise BinaryMaterialisationError(
                        "MAT_PROCESSOR_PROVENANCE_INVALID",
                        "Processor did not return deterministic derivative evidence.",
                        disposition=BinaryMaterialisationDisposition.REJECT,
                    )
                record = write_result.record
                allocated_attachment_id = record.attachment_id
                result = self._ready_result(
                    request,
                    record=record,
                    derivative=derivative,
                    limits=limits,
                )
                self._bindings[record.attachment_id] = record.binding
                self._source_resolver.record_outcome(
                    request=request,
                    outcome_code="COMPLETED",
                    reason_code="MAT_ATTACHMENT_READY",
                    byte_size=record.byte_size,
                    sha256=record.sha256,
                    duration_ms=max(
                        0,
                        int((time.monotonic() - started_monotonic) * 1000),
                    ),
                )
            except BinaryMaterialisationError as exc:
                self._cleanup_failed_attachment(allocated_attachment_id)
                result = self._failure_result(
                    request,
                    reason_code=exc.reason_code,
                    disposition=exc.disposition,
                )
                if audited and exc.audited:
                    self._record_failure_outcome(
                        request,
                        reason_code=exc.reason_code,
                        started_monotonic=started_monotonic,
                    )
            except (ManagedStoreError, AttachmentStoreError) as exc:
                self._cleanup_failed_attachment(allocated_attachment_id)
                reason = _safe_runtime_reason(exc)
                result = self._failure_result(
                    request,
                    reason_code=reason,
                    disposition=BinaryMaterialisationDisposition.REJECT,
                )
                if audited:
                    self._record_failure_outcome(
                        request,
                        reason_code=reason,
                        started_monotonic=started_monotonic,
                    )
            except Exception:
                self._cleanup_failed_attachment(allocated_attachment_id)
                result = self._failure_result(
                    request,
                    reason_code="MAT_INTERNAL_ERROR",
                    disposition=BinaryMaterialisationDisposition.REJECT,
                )
                if audited:
                    self._record_failure_outcome(
                        request,
                        reason_code="MAT_INTERNAL_ERROR",
                        started_monotonic=started_monotonic,
                    )
            self._results[request.request_id] = result
            return result

    @contextmanager
    def open_attachment_once(
        self,
        attachment_id: str,
        *,
        request: BinaryMaterialisationRequest,
        cancelled: Callable[[], bool] | None = None,
    ) -> Iterator[BinaryIO]:
        """Open an exact principal/request/route-bound handle once."""
        cancellation_check = cancelled or (lambda: False)
        binding = self._bindings.get(attachment_id)
        expected = self._attachment_binding(
            request,
            created_at=(binding.created_at if binding is not None else self._clock()),
        )
        if binding != expected:
            raise BinaryMaterialisationError(
                "MAT_ATTACHMENT_BINDING_INVALID",
                "Attachment binding does not match this consumer.",
                disposition=BinaryMaterialisationDisposition.REJECT,
            )
        try:
            with self._attachment_store.open_once(
                attachment_id,
                binding=expected,
                cancelled=cancellation_check,
                now=self._clock(),
            ) as stream:
                yield stream
        except AttachmentStoreError as exc:
            raise BinaryMaterialisationError(
                _safe_runtime_reason(exc),
                "Attachment consumption failed safely.",
                disposition=BinaryMaterialisationDisposition.REJECT,
            ) from exc
        finally:
            self._bindings.pop(attachment_id, None)
            with self._lock:
                prior = self._results.get(request.request_id)
                if prior is not None and prior.attachment_id == attachment_id:
                    remaining = self._attachment_store.status(attachment_id)
                    self._results[request.request_id] = replace(
                        prior,
                        consumed_at=self._clock(),
                        cleanup_state=(
                            AttachmentCleanupState.CLEANUP_FAILED
                            if remaining is not None
                            else AttachmentCleanupState.CLEANED
                        ),
                    )

    def attachment_status(
        self, attachment_id: str
    ) -> BinaryMaterialisationResult | None:
        """Return a content-free status for a live handle."""
        record = self._attachment_store.status(attachment_id)
        if record is None:
            return None
        request_result = self._results.get(record.binding.request_id)
        if request_result is None:
            return None
        state = {
            "READY": AttachmentCleanupState.READY,
            "CONSUMED": AttachmentCleanupState.CONSUMED,
            "CLEANUP_FAILED": AttachmentCleanupState.CLEANUP_FAILED,
        }.get(record.state, AttachmentCleanupState.CLEANED)
        return replace(
            request_result,
            consumed_at=record.consumed_at,
            cleanup_state=state,
        )

    def _validate_request(
        self,
        request: BinaryMaterialisationRequest,
        *,
        now: datetime,
    ) -> None:
        if not self._configuration.enabled:
            raise BinaryMaterialisationError(
                "MAT_FEATURE_DISABLED",
                "Secure binary materialisation is disabled.",
                disposition=BinaryMaterialisationDisposition.DEFER,
                audited=False,
            )
        if request.fingerprint != request.expected_fingerprint():
            raise BinaryMaterialisationError(
                "MAT_REQUEST_IDENTITY_INVALID",
                "Materialisation request identity changed.",
                disposition=BinaryMaterialisationDisposition.REJECT,
                audited=False,
            )
        if request.policy.fingerprint != request.policy.expected_fingerprint():
            raise BinaryMaterialisationError(
                "MAT_POLICY_IDENTITY_INVALID",
                "P2-04 policy identity changed.",
                disposition=BinaryMaterialisationDisposition.REJECT,
                audited=False,
            )
        if request.route.fingerprint != request.route.expected_fingerprint():
            raise BinaryMaterialisationError(
                "MAT_ROUTE_IDENTITY_INVALID",
                "P2-05 route identity changed.",
                disposition=BinaryMaterialisationDisposition.REJECT,
                audited=False,
            )
        if request.policy.disposition != P204Disposition.ACCEPT:
            disposition = (
                BinaryMaterialisationDisposition.REJECT
                if request.policy.disposition == P204Disposition.REJECT
                else BinaryMaterialisationDisposition.DEFER
            )
            raise BinaryMaterialisationError(
                "MAT_POLICY_NOT_ACCEPTED",
                "P2-04 policy did not accept this source and selection.",
                disposition=disposition,
                audited=False,
            )
        if request.route.disposition not in {
            P205Disposition.SELECTED,
            P205Disposition.FALLBACK,
        }:
            disposition = (
                BinaryMaterialisationDisposition.REJECT
                if request.route.disposition == P205Disposition.REJECT
                else BinaryMaterialisationDisposition.DEFER
            )
            raise BinaryMaterialisationError(
                "MAT_ROUTE_NOT_SELECTED",
                "P2-05 did not select an approved materialisation route.",
                disposition=disposition,
                audited=False,
            )
        if request.route.route_kind == P205RouteKind.PRIMARY_TEXT_COMPATIBILITY:
            raise BinaryMaterialisationError(
                "MAT_ROUTE_KIND_UNSUPPORTED",
                "Phase 1 compatibility is not a binary materialisation route.",
                disposition=BinaryMaterialisationDisposition.DEFER,
                audited=False,
            )
        if request.route.policy_fingerprint != request.policy.fingerprint:
            raise BinaryMaterialisationError(
                "MAT_POLICY_ROUTE_MISMATCH",
                "P2-05 route does not bind the supplied P2-04 policy.",
                disposition=BinaryMaterialisationDisposition.REJECT,
                audited=False,
            )
        if request.route.selection_fingerprint != request.policy.selection.fingerprint:
            raise BinaryMaterialisationError(
                "MAT_SELECTION_WIDENED",
                "Materialisation selection differs from the approved route.",
                disposition=BinaryMaterialisationDisposition.REJECT,
                audited=False,
            )
        if request.route.limits_fingerprint != limits_fingerprint(
            request.policy.limits
        ):
            raise BinaryMaterialisationError(
                "MAT_LIMITS_WIDENED",
                "Materialisation limits differ from the approved route.",
                disposition=BinaryMaterialisationDisposition.REJECT,
                audited=False,
            )
        if (
            request.policy.safety_evidence.source_fingerprint
            != request.source_fingerprint
        ):
            raise BinaryMaterialisationError(
                "MAT_SOURCE_IDENTITY_CHANGED",
                "P2-04 safety evidence belongs to different bytes.",
                disposition=BinaryMaterialisationDisposition.REJECT,
                audited=False,
            )
        for expiry in (
            request.policy.expires_at,
            request.route.expires_at,
            request.expires_at,
        ):
            if now >= expiry:
                raise BinaryMaterialisationError(
                    "MAT_APPROVAL_STALE",
                    "Materialisation approval expired.",
                    disposition=BinaryMaterialisationDisposition.DEFER,
                    audited=False,
                )
        if request.expires_at - now > timedelta(
            seconds=self._configuration.max_ttl_seconds
        ):
            raise BinaryMaterialisationError(
                "MAT_EXPIRY_LIMIT_EXCEEDED",
                "Attachment lifetime exceeds the host ceiling.",
                disposition=BinaryMaterialisationDisposition.REJECT,
                audited=False,
            )
        if request.cleanup_deadline - request.expires_at > timedelta(
            seconds=self._configuration.max_cleanup_grace_seconds
        ):
            raise BinaryMaterialisationError(
                "MAT_CLEANUP_DEADLINE_INVALID",
                "Attachment cleanup deadline exceeds the host ceiling.",
                disposition=BinaryMaterialisationDisposition.REJECT,
                audited=False,
            )
        safety_reason = _safety_failure_reason(request.policy.safety_evidence)
        if safety_reason is not None:
            raise BinaryMaterialisationError(
                safety_reason,
                "P2-04 safety evidence forbids materialisation.",
                disposition=(
                    BinaryMaterialisationDisposition.DEFER
                    if safety_reason
                    in {"MAT_ENCRYPTED_CONTENT", "MAT_EXTERNAL_REFERENCE"}
                    else BinaryMaterialisationDisposition.REJECT
                ),
                audited=False,
            )

    def _profile_for(
        self,
        request: BinaryMaterialisationRequest,
    ) -> ApprovedProcessorProfile:
        profile = self._profiles.get(request.route.processor.key)
        if profile is None:
            raise BinaryMaterialisationError(
                "MAT_PROCESSOR_PROFILE_UNSUPPORTED",
                "No reviewed processor profile matches the route.",
                disposition=BinaryMaterialisationDisposition.DEFER,
                audited=False,
            )
        if request.policy.verified_representation != profile.input_representation:
            raise BinaryMaterialisationError(
                "MAT_REPRESENTATION_MISMATCH",
                "Processor input representation differs from P2-04.",
                disposition=BinaryMaterialisationDisposition.REJECT,
                audited=False,
            )
        if (
            request.policy.required_output_representation
            != profile.output_representation
        ):
            raise BinaryMaterialisationError(
                "MAT_OUTPUT_REPRESENTATION_MISMATCH",
                "Processor output representation differs from P2-04.",
                disposition=BinaryMaterialisationDisposition.REJECT,
                audited=False,
            )
        if (
            request.policy.selection.selection_code
            not in profile.allowed_selection_codes
        ):
            raise BinaryMaterialisationError(
                "MAT_SELECTION_UNSUPPORTED",
                "Processor profile does not support the exact selection type.",
                disposition=BinaryMaterialisationDisposition.DEFER,
                audited=False,
            )
        return profile

    def _effective_limits(
        self,
        request: BinaryMaterialisationRequest,
        profile: ApprovedProcessorProfile,
    ) -> Mapping[LimitDimension, int]:
        approved = {item.dimension: item.maximum for item in request.policy.limits}
        missing = profile.required_dimensions - approved.keys()
        if missing:
            raise BinaryMaterialisationError(
                "MAT_REQUIRED_BOUND_UNKNOWN",
                "One or more required dimensions lack an approved bound.",
                disposition=BinaryMaterialisationDisposition.DEFER,
                audited=False,
            )
        host = {
            LimitDimension.BYTES: self._configuration.max_source_bytes,
            LimitDimension.OUTPUT_BYTES: self._configuration.max_output_bytes,
            LimitDimension.RETRIES: 0,
            LimitDimension.ELAPSED_TIME: self._configuration.max_elapsed_seconds,
        }
        effective = {
            dimension: min(value, host.get(dimension, value))
            for dimension, value in approved.items()
        }
        if effective[LimitDimension.RETRIES] != 0:
            effective[LimitDimension.RETRIES] = 0
        return MappingProxyType(effective)

    @staticmethod
    def _validate_route_revalidation(
        request: BinaryMaterialisationRequest,
        revalidation: RouteRevalidation,
        *,
        evaluated_at: datetime,
    ) -> None:
        if not revalidation.approved:
            raise BinaryMaterialisationError(
                revalidation.reason_code,
                "P2-05 route revalidation did not approve byte access.",
                disposition=BinaryMaterialisationDisposition.DEFER,
                audited=False,
            )
        if (
            revalidation.route_fingerprint != request.route.fingerprint
            or revalidation.policy_fingerprint != request.policy.fingerprint
            or revalidation.evaluated_at != evaluated_at
        ):
            raise BinaryMaterialisationError(
                "MAT_ROUTE_REVALIDATION_MISMATCH",
                "Fresh route evidence does not match the request.",
                disposition=BinaryMaterialisationDisposition.REJECT,
                audited=False,
            )

    @staticmethod
    def _validate_source(
        request: BinaryMaterialisationRequest,
        source: AuthorisedBinarySource,
    ) -> None:
        if not source.output_set_complete:
            raise BinaryMaterialisationError(
                "MAT_OUTPUT_SET_INCOMPLETE",
                "Registered deterministic output set is incomplete.",
                disposition=BinaryMaterialisationDisposition.REJECT,
            )
        if (
            source.document_version_id != request.document_version_id
            or source.extraction_id != request.extraction_id
            or source.artefact_id != request.artefact_id
            or source.identity.byte_size != request.expected_byte_size
            or source.identity.sha256 != request.expected_sha256
            or source.source_fingerprint != request.source_fingerprint
        ):
            raise BinaryMaterialisationError(
                "MAT_SOURCE_IDENTITY_CHANGED",
                "Registered source identity changed since route evaluation.",
                disposition=BinaryMaterialisationDisposition.REJECT,
            )
        if source.media_type != request.policy.declared_mime_type:
            raise BinaryMaterialisationError(
                "MAT_MIME_REGISTERED_MISMATCH",
                "Registered source MIME differs from the P2-04 declaration.",
                disposition=BinaryMaterialisationDisposition.REJECT,
            )

    @staticmethod
    def _validate_inspection(
        request: BinaryMaterialisationRequest,
        profile: ApprovedProcessorProfile,
        inspection: ProcessorInspection,
        *,
        limits: Mapping[LimitDimension, int],
    ) -> None:
        safety_reason = _safety_failure_reason(inspection)
        if safety_reason is not None:
            raise BinaryMaterialisationError(
                safety_reason,
                "Opened source failed deterministic safety inspection.",
                disposition=(
                    BinaryMaterialisationDisposition.DEFER
                    if safety_reason
                    in {"MAT_ENCRYPTED_CONTENT", "MAT_EXTERNAL_REFERENCE"}
                    else BinaryMaterialisationDisposition.REJECT
                ),
            )
        if (
            inspection.verified_representation != request.policy.verified_representation
            or inspection.detected_mime_type != request.policy.detected_mime_type
            or inspection.mime_decision != request.policy.mime_decision
        ):
            raise BinaryMaterialisationError(
                "MAT_REPRESENTATION_MIME_MISMATCH",
                "Opened source representation or MIME decision changed.",
                disposition=BinaryMaterialisationDisposition.REJECT,
            )
        if inspection.detected_mime_type not in profile.accepted_mime_types:
            raise BinaryMaterialisationError(
                "MAT_MIME_UNSUPPORTED",
                "Processor profile does not accept the detected MIME.",
                disposition=BinaryMaterialisationDisposition.DEFER,
            )
        measurements = {
            item.dimension: item.maximum for item in inspection.measurements
        }
        for dimension in profile.required_dimensions:
            if dimension in {LimitDimension.OUTPUT_BYTES, LimitDimension.ELAPSED_TIME}:
                continue
            if dimension not in measurements:
                raise BinaryMaterialisationError(
                    "MAT_REQUIRED_BOUND_UNKNOWN",
                    "Processor inspection did not measure a required dimension.",
                    disposition=BinaryMaterialisationDisposition.DEFER,
                )
            if measurements[dimension] > limits[dimension]:
                reason = (
                    "MAT_EXPANSION_LIMIT_EXCEEDED"
                    if dimension.value in EXPANSION_DIMENSIONS
                    else "MAT_BOUND_EXCEEDED"
                )
                raise BinaryMaterialisationError(
                    reason,
                    "Opened source exceeded an approved dimension.",
                    disposition=BinaryMaterialisationDisposition.REJECT,
                )

    def _attachment_binding(
        self,
        request: BinaryMaterialisationRequest,
        *,
        created_at: datetime,
    ) -> AttachmentBinding:
        return AttachmentBinding(
            request_id=request.request_id,
            request_fingerprint=request.fingerprint,
            principal_fingerprint=request.principal_fingerprint,
            route_fingerprint=request.route.fingerprint,
            policy_fingerprint=request.policy.fingerprint,
            source_fingerprint=request.source_fingerprint,
            selection_fingerprint=request.policy.selection.fingerprint,
            correlation_id=request.correlation_id,
            audit_id=request.audit_id,
            policy_result_id=request.policy.result_id,
            route_result_id=request.route.result_id,
            route_kind=request.route.route_kind.value,
            route_identity=request.route.route_identity,
            processor_code=request.route.processor.processor_code,
            processor_profile=request.route.processor.profile_code,
            processor_version=request.route.processor.version,
            verified_representation=request.policy.verified_representation,
            mime_decision=request.policy.mime_decision.value,
            limits_fingerprint=limits_fingerprint(request.policy.limits),
            locality_decision_id=request.route.locality_decision_id,
            classification_decision_id=request.route.classification_decision_id,
            consent_decision_id=request.route.consent_decision_id,
            minimisation_decision_id=request.route.minimisation_decision_id,
            created_at=created_at,
            expires_at=request.expires_at,
            cleanup_deadline=request.cleanup_deadline,
        )

    def _ready_result(
        self,
        request: BinaryMaterialisationRequest,
        *,
        record: AttachmentRecord,
        derivative: DeterministicDerivativeEvidence,
        limits: Mapping[LimitDimension, int],
    ) -> BinaryMaterialisationResult:
        applied = tuple(
            MaterialisationLimit(
                dimension=dimension,
                maximum=maximum,
                unit_code=_unit_for_dimension(dimension),
            )
            for dimension, maximum in sorted(
                limits.items(),
                key=lambda item: item[0].value,
            )
        )
        return BinaryMaterialisationResult(
            disposition=BinaryMaterialisationDisposition.READY,
            reason_code="MAT_ATTACHMENT_READY",
            attachment_id=record.attachment_id,
            request_fingerprint=request.fingerprint,
            route_fingerprint=request.route.fingerprint,
            policy_fingerprint=request.policy.fingerprint,
            source_fingerprint=request.source_fingerprint,
            selection_fingerprint=request.policy.selection.fingerprint,
            verified_representation=request.policy.verified_representation,
            mime_decision=request.policy.mime_decision,
            byte_size=record.byte_size,
            sha256=record.sha256,
            applied_limits=applied,
            derivative=derivative,
            created_at=record.binding.created_at,
            expires_at=record.binding.expires_at,
            consumed_at=record.consumed_at,
            cleanup_state=AttachmentCleanupState.READY,
            audit_fields=_audit_fields(request, record=record),
        )

    @staticmethod
    def _failure_result(
        request: BinaryMaterialisationRequest,
        *,
        reason_code: str,
        disposition: BinaryMaterialisationDisposition,
    ) -> BinaryMaterialisationResult:
        return BinaryMaterialisationResult(
            disposition=disposition,
            reason_code=reason_code,
            attachment_id=None,
            request_fingerprint=request.fingerprint,
            route_fingerprint=request.route.fingerprint,
            policy_fingerprint=request.policy.fingerprint,
            source_fingerprint=request.source_fingerprint,
            selection_fingerprint=request.policy.selection.fingerprint,
            verified_representation=request.policy.verified_representation,
            mime_decision=request.policy.mime_decision,
            byte_size=None,
            sha256=None,
            applied_limits=(),
            derivative=None,
            created_at=None,
            expires_at=None,
            consumed_at=None,
            cleanup_state=AttachmentCleanupState.NOT_ALLOCATED,
            audit_fields=_audit_fields(request, record=None),
        )

    def _record_failure_outcome(
        self,
        request: BinaryMaterialisationRequest,
        *,
        reason_code: str,
        started_monotonic: float,
    ) -> None:
        outcome = "CANCELLED" if reason_code == "MAT_CANCELLED" else "FAILED"
        try:
            self._source_resolver.record_outcome(
                request=request,
                outcome_code=outcome,
                reason_code=reason_code,
                duration_ms=max(
                    0,
                    int((time.monotonic() - started_monotonic) * 1000),
                ),
            )
        except Exception:
            pass

    def _cleanup_failed_attachment(self, attachment_id: str | None) -> None:
        """Best-effort cleanup after a post-allocation failure."""
        if attachment_id is None:
            return
        self._bindings.pop(attachment_id, None)
        try:
            self._attachment_store.cleanup(
                attachment_id,
                reason_code="MAT_MATERIALISATION_FAILED",
            )
        except AttachmentStoreError:
            return


def source_identity_fingerprint(
    *,
    document_version_id: int,
    extraction_id: int,
    artefact_id: int,
    byte_size: int,
    sha256: str,
    media_type: str,
) -> str:
    """Return the exact registered source identity fingerprint."""
    return _fingerprint(
        {
            "document_version_id": int(document_version_id),
            "extraction_id": int(extraction_id),
            "artefact_id": int(artefact_id),
            "byte_size": int(byte_size),
            "sha256": _canonical_sha256(sha256, field_name="sha256"),
            "media_type": _media_type(media_type),
        }
    )


def limits_fingerprint(limits: Sequence[MaterialisationLimit]) -> str:
    """Return a deterministic dimension-qualified limit fingerprint."""
    canonical = _canonical_limits(limits)
    return _fingerprint(
        [
            {
                "dimension": item.dimension.value,
                "maximum": item.maximum,
                "unit_code": item.unit_code,
            }
            for item in canonical
        ]
    )


def _canonical_limits(
    limits: Sequence[MaterialisationLimit],
) -> tuple[MaterialisationLimit, ...]:
    canonical = tuple(limits)
    dimensions = [item.dimension for item in canonical]
    if len(dimensions) != len(set(dimensions)):
        raise ValueError("materialisation limit dimensions must be unique")
    return tuple(sorted(canonical, key=lambda item: item.dimension.value))


def _safety_failure_reason(evidence: object) -> str | None:
    if not bool(getattr(evidence, "signature_valid")):
        return "MAT_SIGNATURE_MISMATCH"
    if bool(getattr(evidence, "corrupt")) or not bool(
        getattr(evidence, "structure_valid")
    ):
        return "MAT_CORRUPT_CONTENT"
    if bool(getattr(evidence, "encrypted")):
        return "MAT_ENCRYPTED_CONTENT"
    if bool(getattr(evidence, "active_content")):
        return "MAT_ACTIVE_CONTENT"
    if bool(getattr(evidence, "external_references")):
        return "MAT_EXTERNAL_REFERENCE"
    if bool(getattr(evidence, "nested_content")):
        return "MAT_NESTED_CONTENT_UNSUPPORTED"
    if bool(getattr(evidence, "expansion_risk")):
        return "MAT_EXPANSION_RISK"
    return None


def _safe_source_reason(reason_code: str) -> str:
    if reason_code == "RETRIEVAL_NOT_AUTHORISED":
        return "MAT_SOURCE_AUTHORISATION_CHANGED"
    if reason_code == "RETRIEVAL_TARGET_NOT_FOUND":
        return "MAT_SOURCE_MISSING"
    return "MAT_SOURCE_IDENTITY_CHANGED"


def _safe_runtime_reason(exc: Exception) -> str:
    reason = str(getattr(exc, "reason_code", ""))
    if reason.startswith("MAT_") and CONTROLLED_CODE_PATTERN.fullmatch(reason):
        return reason
    if isinstance(exc, ManagedStoreError):
        if reason == "MANAGED_OBJECT_MISSING":
            return "MAT_SOURCE_MISSING"
        if reason in {
            "MANAGED_OBJECT_HASH_MISMATCH",
            "MANAGED_OBJECT_SIZE_MISMATCH",
            "STORAGE_KEY_IDENTITY_MISMATCH",
        }:
            return "MAT_SOURCE_CHANGED"
        if reason in {
            "MANAGED_OBJECT_SYMLINK",
            "MANAGED_OBJECT_NOT_REGULAR",
            "MANAGED_OBJECT_PERMISSION_INVALID",
            "UNSAFE_STORE_LAYOUT",
            "STORE_ROOT_IDENTITY_CHANGED",
        }:
            return "MAT_SOURCE_UNSAFE"
        return "MAT_MANAGED_STORE_UNAVAILABLE"
    return "MAT_INTERNAL_ERROR"


def _audit_fields(
    request: BinaryMaterialisationRequest,
    *,
    record: AttachmentRecord | None,
) -> Mapping[str, Any]:
    return MappingProxyType(
        {
            "request_id": request.request_id,
            "correlation_id": request.correlation_id,
            "audit_id": request.audit_id,
            "principal_fingerprint": request.principal_fingerprint,
            "document_version_id": request.document_version_id,
            "extraction_id": request.extraction_id,
            "artefact_id": request.artefact_id,
            "policy_result_id": request.policy.result_id,
            "route_result_id": request.route.result_id,
            "route_kind": request.route.route_kind.value,
            "route_identity": request.route.route_identity,
            "request_fingerprint": request.fingerprint,
            "source_fingerprint": request.source_fingerprint,
            "policy_fingerprint": request.policy.fingerprint,
            "route_fingerprint": request.route.fingerprint,
            "selection_fingerprint": request.policy.selection.fingerprint,
            "limits_fingerprint": limits_fingerprint(request.policy.limits),
            "fallback_chain_id": request.route.fallback_chain_id,
            "fallback_step": request.route.fallback_step,
            "locality_decision_id": request.route.locality_decision_id,
            "classification_decision_id": request.route.classification_decision_id,
            "consent_decision_id": request.route.consent_decision_id,
            "minimisation_decision_id": request.route.minimisation_decision_id,
            "processor_code": request.route.processor.processor_code,
            "processor_profile": request.route.processor.profile_code,
            "processor_version": request.route.processor.version,
            "verified_representation": request.policy.verified_representation,
            "declared_mime_type": request.policy.declared_mime_type,
            "detected_mime_type": request.policy.detected_mime_type,
            "mime_decision": request.policy.mime_decision.value,
            "safety_evidence_id": request.policy.safety_evidence.evidence_id,
            "safety_evidence_fingerprint": request.policy.safety_evidence.fingerprint,
            "attachment_id": record.attachment_id if record else None,
        }
    )


def _unit_for_dimension(dimension: LimitDimension) -> str:
    return {
        LimitDimension.BYTES: "BYTES",
        LimitDimension.OUTPUT_BYTES: "BYTES",
        LimitDimension.EXPANDED_BYTES: "BYTES",
        LimitDimension.ELAPSED_TIME: "SECONDS",
        LimitDimension.DURATION: "MILLISECONDS",
    }.get(dimension, "COUNT")


def _fingerprint(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _controlled_code(value: str, *, field_name: str) -> str:
    text = str(value).strip().upper()
    if CONTROLLED_CODE_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field_name} must be a controlled upper-case code")
    return text


def _processor_code(value: str, *, field_name: str) -> str:
    text = str(value).strip()
    if PROCESSOR_CODE_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field_name} must be a controlled lower-case code")
    return text


def _policy_version(value: str, *, field_name: str) -> str:
    text = str(value).strip()
    if POLICY_VERSION_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field_name} is invalid")
    return text


def _media_type(value: str) -> str:
    text = str(value).strip()
    if text != text.lower() or MEDIA_TYPE_PATTERN.fullmatch(text) is None:
        raise ValueError("media type must be canonical lower-case type/subtype")
    return text


def _canonical_sha256(value: str, *, field_name: str) -> str:
    text = str(value)
    if SHA256_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field_name} must be a canonical SHA-256 digest")
    return text


def _canonical_uuid(value: str, *, field_name: str) -> str:
    try:
        canonical = str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(f"{field_name} must be a canonical UUID") from exc
    if canonical != str(value):
        raise ValueError(f"{field_name} must be a canonical UUID")
    return canonical


def _utc_datetime(value: datetime, *, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)
