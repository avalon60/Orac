"""Continuity-first planner and universal pre-invocation context guard."""

# Author: Clive Bostock
# Date: 2026-08-29
# Description: Allocates atomic prompt components under the effective context limit.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
import math

from .configuration import ContextBudgetConfiguration
from .models import ContextAllocation
from .models import ContextBudgetRejection
from .models import ContextBudgetRequest
from .models import ContextComponentKind
from .models import ContextItem
from .models import PreparedModelContext
from .models import ProviderContextEstimate


ContextSerializer = Callable[[tuple[ContextItem, ...]], str]
ContextEstimator = Callable[[str], ProviderContextEstimate]


@dataclass(frozen=True, slots=True)
class ContextBudgetSession:
    """One immutable planning session for a selected model invocation."""

    planner: "ContextBudgetPlanner"
    request: ContextBudgetRequest
    serializer: ContextSerializer
    estimator: ContextEstimator

    def prepare(self) -> PreparedModelContext | ContextBudgetRejection:
        """Prepare this session through its owning planner."""
        return self.planner.prepare(
            self.request,
            serializer=self.serializer,
            estimator=self.estimator,
        )


class ContextBudgetPlanner:
    """Allocate atomic context while preserving mandatory model input."""

    def __init__(self, configuration: ContextBudgetConfiguration) -> None:
        """Initialise the planner with validated host policy."""
        self._configuration = configuration

    def open_session(
        self,
        request: ContextBudgetRequest,
        *,
        serializer: ContextSerializer,
        estimator: ContextEstimator,
    ) -> ContextBudgetSession:
        """Return one immutable context-planning session."""
        return ContextBudgetSession(self, request, serializer, estimator)

    def context_safety_reserve(self, effective_context_limit: int) -> int:
        """Calculate deliberate unused context headroom."""
        return max(
            math.ceil(
                effective_context_limit
                * self._configuration.context_safety_percent
                / 100
            ),
            self._configuration.context_safety_min_tokens,
        )

    def prepare(
        self,
        request: ContextBudgetRequest,
        *,
        serializer: ContextSerializer,
        estimator: ContextEstimator,
    ) -> PreparedModelContext | ContextBudgetRejection:
        """Select optional items and guard the final provider serialization."""
        diagnostics = _limit_diagnostics(request)
        if not request.model.enabled:
            return ContextBudgetRejection(
                request.request_id,
                "CTX_MODEL_DISABLED",
                diagnostics,
            )
        effective_limit = request.model.effective_context_limit
        safety_reserve = self.context_safety_reserve(effective_limit)
        mandatory = tuple(request.mandatory_items)
        mandatory_serialized = serializer(mandatory)
        mandatory_estimate = estimator(mandatory_serialized)
        if not _fits(
            mandatory_estimate,
            response_allowance=request.response_allowance,
            safety_reserve=safety_reserve,
            effective_limit=effective_limit,
        ):
            return ContextBudgetRejection(
                request.request_id,
                "CTX_MANDATORY_OVERFLOW",
                diagnostics,
            )

        selected = list(mandatory)
        omitted: list[ContextItem] = []
        ordered_optional = sorted(
            request.optional_items,
            key=lambda item: (int(item.priority or 999), item.rank, item.item_id),
        )
        final_serialized = mandatory_serialized
        final_estimate = mandatory_estimate
        for item in ordered_optional:
            candidate_items = tuple((*selected, item))
            candidate_serialized = serializer(candidate_items)
            candidate_estimate = estimator(candidate_serialized)
            if _fits(
                candidate_estimate,
                response_allowance=request.response_allowance,
                safety_reserve=safety_reserve,
                effective_limit=effective_limit,
            ):
                selected.append(item)
                final_serialized = candidate_serialized
                final_estimate = candidate_estimate
            else:
                omitted.append(item)

        allocation = _allocation(tuple(selected), tuple(omitted))
        return PreparedModelContext(
            request=request,
            selected_items=tuple(selected),
            serialized_context=final_serialized,
            provider_estimate=final_estimate,
            context_safety_reserve=safety_reserve,
            effective_context_limit=effective_limit,
            allocation=allocation,
            diagnostic_reason_codes=diagnostics,
        )


def _fits(
    estimate: ProviderContextEstimate,
    *,
    response_allowance: int,
    safety_reserve: int,
    effective_limit: int,
) -> bool:
    """Apply the universal final preflight safety equation."""
    return (
        estimate.safe_preflight_tokens
        + response_allowance
        + safety_reserve
        <= effective_limit
    )

def _limit_diagnostics(request: ContextBudgetRequest) -> tuple[str, ...]:
    """Return safe non-rejection diagnostics for runtime capacity state."""
    if request.model.runtime_execution_context_limit is None:
        return ("CTX_RUNTIME_LIMIT_UNKNOWN",)
    if request.model.runtime_constrained:
        return ("CTX_RUNTIME_LIMIT_REDUCED",)
    return ()


def _allocation(
    selected: tuple[ContextItem, ...],
    omitted: tuple[ContextItem, ...],
) -> ContextAllocation:
    """Build content-free aggregate allocation metadata."""
    selected_optional = tuple(
        item for item in selected if item.kind is not ContextComponentKind.MANDATORY
    )
    selected_counts = Counter(item.kind.value for item in selected_optional)
    omitted_counts = Counter(item.kind.value for item in omitted)
    return ContextAllocation(
        selected_item_ids=tuple(item.item_id for item in selected_optional),
        omitted_item_ids=tuple(item.item_id for item in omitted),
        omission_reason_codes=tuple(
            "CTX_COMPONENT_OMITTED_BUDGET" for _item in omitted
        ),
        selected_counts=selected_counts,
        omitted_counts=omitted_counts,
    )
