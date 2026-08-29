"""Immutable contracts for model-aware dialogue context budgeting."""

# Author: Clive Bostock
# Date: 2026-08-29
# Description: Defines governed context limits, prompt components, and decisions.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from types import MappingProxyType
from typing import Any, Mapping


class ContextComponentKind(str, Enum):
    """Host-owned model-context component classifications."""

    MANDATORY = "MANDATORY"
    RECENT_DIALOGUE_FLOOR = "RECENT_DIALOGUE_FLOOR"
    PRIMARY_EVIDENCE = "PRIMARY_EVIDENCE"
    SUPPLEMENTARY_MEMORY = "SUPPLEMENTARY_MEMORY"
    RECENT_DIALOGUE = "RECENT_DIALOGUE"


class ContextPriority(IntEnum):
    """Deterministic optional allocation order."""

    CONTINUITY_FLOOR = 10
    PRIMARY_EVIDENCE = 20
    SUPPLEMENTARY_MEMORY = 30
    RECENT_DIALOGUE = 40


@dataclass(frozen=True, slots=True)
class RuntimeContextObservation:
    """One bounded provider observation of active runtime context capacity."""

    context_limit_tokens: int | None
    source_code: str
    observation_fingerprint: str | None = None
    source_version: str | None = None
    can_reliably_reread: bool = False

    def __post_init__(self) -> None:
        """Validate safe, content-free runtime metadata."""
        if self.context_limit_tokens is not None and self.context_limit_tokens <= 0:
            raise ValueError("runtime context limit must be positive when supplied")
        if not self.source_code.strip():
            raise ValueError("runtime observation source_code is required")


@dataclass(frozen=True, slots=True)
class ContextModelSnapshot:
    """Exact governed model row and optional active runtime context observation."""

    llm_id: int
    registry_row_version: int
    provider_code: str
    model_name: str
    governed_model_context_limit: int
    runtime_execution_context_limit: int | None = None
    runtime_observation_source: str | None = None
    runtime_observation_fingerprint: str | None = None
    runtime_observation_version: str | None = None
    runtime_limit_rereadable: bool = False
    enabled: bool = True

    def __post_init__(self) -> None:
        """Validate governed identity and limit fields."""
        if self.llm_id <= 0:
            raise ValueError("llm_id must be positive")
        if self.registry_row_version < 0:
            raise ValueError("registry_row_version must be non-negative")
        if not self.provider_code.strip() or not self.model_name.strip():
            raise ValueError("provider_code and model_name are required")
        if self.governed_model_context_limit <= 0:
            raise ValueError("governed model context limit must be positive")
        if (
            self.runtime_execution_context_limit is not None
            and self.runtime_execution_context_limit <= 0
        ):
            raise ValueError("runtime execution context limit must be positive")

    @property
    def effective_context_limit(self) -> int:
        """Return the lower of governed and known active runtime limits."""
        if self.runtime_execution_context_limit is None:
            return self.governed_model_context_limit
        return min(
            self.governed_model_context_limit,
            self.runtime_execution_context_limit,
        )

    @property
    def runtime_constrained(self) -> bool:
        """Return whether runtime capacity reduces the governed ceiling."""
        return (
            self.runtime_execution_context_limit is not None
            and self.runtime_execution_context_limit
            < self.governed_model_context_limit
        )


@dataclass(frozen=True, slots=True)
class ProviderContextEstimate:
    """Conservative estimate over one exact context-bearing serialization."""

    base_estimated_tokens: int
    estimator_uncertainty_percent: int
    estimator_uncertainty_tokens: int
    safe_preflight_tokens: int
    estimator_code: str
    estimator_version: str
    serialization_code: str
    serialization_fingerprint: str
    byte_count: int
    character_count: int

    def __post_init__(self) -> None:
        """Reject inconsistent or negative accounting."""
        values = (
            self.base_estimated_tokens,
            self.estimator_uncertainty_tokens,
            self.safe_preflight_tokens,
            self.byte_count,
            self.character_count,
        )
        if any(value < 0 for value in values):
            raise ValueError("provider context estimates must be non-negative")
        if self.safe_preflight_tokens != (
            self.base_estimated_tokens + self.estimator_uncertainty_tokens
        ):
            raise ValueError("uncertainty margin must be applied exactly once")


@dataclass(frozen=True, slots=True)
class ContextItem:
    """One atomic host-selected context item."""

    item_id: str
    kind: ContextComponentKind
    text: str
    priority: ContextPriority | None = None
    rank: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate item identity and freeze bounded metadata."""
        if not self.item_id.strip():
            raise ValueError("context item_id is required")
        if not isinstance(self.text, str):
            raise TypeError("context item text must be a string")
        if self.kind is ContextComponentKind.MANDATORY and self.priority is not None:
            raise ValueError("mandatory items do not have an optional priority")
        if self.kind is not ContextComponentKind.MANDATORY and self.priority is None:
            raise ValueError("optional items require a priority")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ContextBudgetRequest:
    """Inputs for one immutable context allocation decision."""

    request_id: str
    model: ContextModelSnapshot
    response_allowance: int
    mandatory_items: tuple[ContextItem, ...]
    optional_items: tuple[ContextItem, ...] = ()

    def __post_init__(self) -> None:
        """Validate request identity and response allowance."""
        if not self.request_id.strip():
            raise ValueError("request_id is required")
        if self.response_allowance <= 0:
            raise ValueError("response_allowance must be positive")
        if any(item.kind is not ContextComponentKind.MANDATORY for item in self.mandatory_items):
            raise ValueError("mandatory_items may contain only mandatory components")
        if any(item.kind is ContextComponentKind.MANDATORY for item in self.optional_items):
            raise ValueError("optional_items may not contain mandatory components")


@dataclass(frozen=True, slots=True)
class ContextAllocation:
    """Content-free allocation result for audit and telemetry."""

    selected_item_ids: tuple[str, ...]
    omitted_item_ids: tuple[str, ...]
    omission_reason_codes: tuple[str, ...]
    selected_counts: Mapping[str, int]
    omitted_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        """Freeze aggregate maps."""
        object.__setattr__(self, "selected_counts", MappingProxyType(dict(self.selected_counts)))
        object.__setattr__(self, "omitted_counts", MappingProxyType(dict(self.omitted_counts)))


@dataclass(frozen=True, slots=True)
class PreparedModelContext:
    """Approved immutable provider context and its bounded accounting."""

    request: ContextBudgetRequest
    selected_items: tuple[ContextItem, ...]
    serialized_context: str
    provider_estimate: ProviderContextEstimate
    context_safety_reserve: int
    effective_context_limit: int
    allocation: ContextAllocation
    diagnostic_reason_codes: tuple[str, ...]

    @property
    def remaining_headroom(self) -> int:
        """Return unused context after every required reservation."""
        return max(
            0,
            self.effective_context_limit
            - self.provider_estimate.safe_preflight_tokens
            - self.request.response_allowance
            - self.context_safety_reserve,
        )


@dataclass(frozen=True, slots=True)
class ContextBudgetRejection:
    """Safe rejection that never includes prompt or evidence content."""

    request_id: str
    reason_code: str
    diagnostic_reason_codes: tuple[str, ...] = ()
