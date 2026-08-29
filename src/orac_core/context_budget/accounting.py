"""Conservative token estimation for exact provider context serialization."""

# Author: Clive Bostock
# Date: 2026-08-29
# Description: Applies estimator uncertainty exactly once to provider context.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

import hashlib
import math

from orac_core.knowledge.token_estimation import ConservativeUtf8TokenEstimator

from .models import ProviderContextEstimate


class ProviderContextAccountant:
    """Estimate exact context-bearing serialization conservatively."""

    def __init__(self, *, estimator_uncertainty_percent: int) -> None:
        """Initialise with the reviewed uncertainty policy."""
        if not 10 <= estimator_uncertainty_percent <= 50:
            raise ValueError("estimator uncertainty must be between 10 and 50")
        # The uncertainty policy is applied here, not inside the base estimator.
        self._base_estimator = ConservativeUtf8TokenEstimator(
            safety_margin_percent=0,
        )
        self._uncertainty_percent = estimator_uncertainty_percent

    def estimate(
        self,
        serialized_context: str,
        *,
        serialization_code: str,
    ) -> ProviderContextEstimate:
        """Return one safe preflight estimate for a serialized context."""
        estimate = self._base_estimator.estimate_prompt(serialized_context)
        uncertainty = math.ceil(
            estimate.base_token_count * self._uncertainty_percent / 100
        )
        return ProviderContextEstimate(
            base_estimated_tokens=estimate.base_token_count,
            estimator_uncertainty_percent=self._uncertainty_percent,
            estimator_uncertainty_tokens=uncertainty,
            safe_preflight_tokens=estimate.base_token_count + uncertainty,
            estimator_code=estimate.estimator_code,
            estimator_version=estimate.estimator_version,
            serialization_code=serialization_code,
            serialization_fingerprint=hashlib.sha256(
                serialized_context.encode("utf-8")
            ).hexdigest(),
            byte_count=estimate.byte_count,
            character_count=estimate.character_count or 0,
        )
