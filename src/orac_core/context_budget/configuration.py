"""Validated configuration for unified dialogue context budgeting."""

# Author: Clive Bostock
# Date: 2026-08-29
# Description: Loads and validates Phase 2B context-budget policy.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ContextBudgetConfiguration:
    """Host-owned context-budget policy with conservative defaults."""

    enabled: bool = True
    shadow_mode: bool = True
    estimator_uncertainty_margin_percent: int = 20
    context_safety_percent: int = 5
    context_safety_min_tokens: int = 256
    recent_dialogue_min_exchanges: int = 1

    def __post_init__(self) -> None:
        """Validate safety controls against reviewed bounds."""
        _bounded(
            "estimator_uncertainty_margin_percent",
            self.estimator_uncertainty_margin_percent,
            10,
            50,
        )
        _bounded("context_safety_percent", self.context_safety_percent, 5, 25)
        _bounded(
            "context_safety_min_tokens",
            self.context_safety_min_tokens,
            256,
            8192,
        )
        _bounded(
            "recent_dialogue_min_exchanges",
            self.recent_dialogue_min_exchanges,
            1,
            4,
        )

    @classmethod
    def from_config(
        cls,
        config_mgr: Any,
        *,
        section: str = "context_budget",
    ) -> "ContextBudgetConfiguration":
        """Load configuration using Orac's existing manager contract."""
        return cls(
            enabled=config_mgr.bool_config_value(section, "enabled", default=True),
            shadow_mode=config_mgr.bool_config_value(
                section,
                "shadow_mode",
                default=True,
            ),
            estimator_uncertainty_margin_percent=config_mgr.int_config_value(
                section,
                "estimator_uncertainty_margin_percent",
                default=20,
            ),
            context_safety_percent=config_mgr.int_config_value(
                section,
                "context_safety_percent",
                default=5,
            ),
            context_safety_min_tokens=config_mgr.int_config_value(
                section,
                "context_safety_min_tokens",
                default=256,
            ),
            recent_dialogue_min_exchanges=config_mgr.int_config_value(
                section,
                "recent_dialogue_min_exchanges",
                default=1,
            ),
        )


def _bounded(name: str, value: int, minimum: int, maximum: int) -> None:
    """Reject booleans and integers outside reviewed policy bounds."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
