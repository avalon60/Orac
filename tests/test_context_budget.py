"""Tests for Phase 2B unified model-aware context budgeting."""

# Author: Clive Bostock
# Date: 2026-08-29
# Description: Verifies effective limits, allocation, estimation, and safety.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from orac_core.context_budget import ContextBudgetConfiguration  # noqa: E402
from orac_core.context_budget import ContextBudgetPlanner  # noqa: E402
from orac_core.context_budget import ContextBudgetRejection  # noqa: E402
from orac_core.context_budget import ContextBudgetRequest  # noqa: E402
from orac_core.context_budget import ContextComponentKind  # noqa: E402
from orac_core.context_budget import ContextItem  # noqa: E402
from orac_core.context_budget import ContextModelSnapshot  # noqa: E402
from orac_core.context_budget import ContextPriority  # noqa: E402
from orac_core.context_budget import PreparedModelContext  # noqa: E402
from orac_core.context_budget import ProviderContextAccountant  # noqa: E402


class _Config:
    """ConfigManager-compatible context-budget fixture."""

    def __init__(self, values=None):
        self.values = values or {}

    def bool_config_value(self, section, key, default=False):
        return self.values.get(key, default)

    def int_config_value(self, section, key, default=0):
        return self.values.get(key, default)


def _model(*, governed=49152, runtime=32768):
    return ContextModelSnapshot(
        llm_id=2,
        registry_row_version=13,
        provider_code="ollama",
        model_name="fixture",
        governed_model_context_limit=governed,
        runtime_execution_context_limit=runtime,
        runtime_observation_source="OLLAMA_SHOW",
        runtime_observation_fingerprint="runtime-1",
        runtime_limit_rereadable=True,
    )


def _mandatory(text="system and current request"):
    return ContextItem("mandatory", ContextComponentKind.MANDATORY, text)


def _optional(item_id, kind, priority, text, rank=0):
    return ContextItem(item_id, kind, text, priority, rank)


def _serialize(items):
    return json.dumps(
        [{"id": item.item_id, "text": item.text} for item in items],
        ensure_ascii=False,
        separators=(",", ":"),
    )


class ContextBudgetConfigurationTests(unittest.TestCase):
    """Verify conservative defaults and explicit reviewed bounds."""

    def test_defaults_and_lower_calibrated_margin(self):
        config = ContextBudgetConfiguration.from_config(_Config())
        self.assertTrue(config.enabled)
        self.assertTrue(config.shadow_mode)
        self.assertEqual(config.estimator_uncertainty_margin_percent, 20)
        self.assertEqual(
            ContextBudgetConfiguration(
                estimator_uncertainty_margin_percent=10
            ).estimator_uncertainty_margin_percent,
            10,
        )

    def test_invalid_safety_bounds_fail(self):
        with self.assertRaises(ValueError):
            ContextBudgetConfiguration(estimator_uncertainty_margin_percent=9)
        with self.assertRaises(ValueError):
            ContextBudgetConfiguration(context_safety_percent=4)
        with self.assertRaises(ValueError):
            ContextBudgetConfiguration(context_safety_min_tokens=255)
        with self.assertRaises(ValueError):
            ContextBudgetConfiguration(recent_dialogue_min_exchanges=0)


class ContextModelSnapshotTests(unittest.TestCase):
    """Verify governed and runtime context limits remain distinct."""

    def test_smaller_runtime_limit_is_valid_effective_limit(self):
        model = _model(governed=49152, runtime=32768)
        self.assertEqual(model.effective_context_limit, 32768)
        self.assertTrue(model.runtime_constrained)

    def test_runtime_cannot_increase_governed_limit(self):
        model = _model(governed=32768, runtime=49152)
        self.assertEqual(model.effective_context_limit, 32768)
        self.assertFalse(model.runtime_constrained)

    def test_unknown_runtime_uses_governed_limit(self):
        model = replace(
            _model(),
            runtime_execution_context_limit=None,
            runtime_observation_source=None,
        )
        self.assertEqual(model.effective_context_limit, 49152)


class ProviderContextAccountantTests(unittest.TestCase):
    """Verify uncertainty is distinct and applied exactly once."""

    def test_margin_is_applied_once(self):
        accountant = ProviderContextAccountant(
            estimator_uncertainty_percent=20
        )
        estimate = accountant.estimate(
            '{"messages":[{"role":"user","content":"hello"}]}',
            serialization_code="TEST_CHAT_V1",
        )
        self.assertEqual(
            estimate.safe_preflight_tokens,
            estimate.base_estimated_tokens + estimate.estimator_uncertainty_tokens,
        )
        self.assertGreater(estimate.estimator_uncertainty_tokens, 0)

    def test_provider_actual_usage_remains_separate(self):
        accountant = ProviderContextAccountant(
            estimator_uncertainty_percent=20
        )
        estimate = accountant.estimate("hello", serialization_code="TEST")
        provider_actual = estimate.base_estimated_tokens + 3
        base_delta = provider_actual - estimate.base_estimated_tokens
        safe_margin_delta = estimate.safe_preflight_tokens - provider_actual
        self.assertEqual(base_delta, 3)
        self.assertIsInstance(safe_margin_delta, int)


class ContextBudgetPlannerTests(unittest.TestCase):
    """Exercise continuity-first allocation and the universal guard."""

    def setUp(self):
        self.config = ContextBudgetConfiguration(
            estimator_uncertainty_margin_percent=20,
            context_safety_percent=5,
            context_safety_min_tokens=256,
        )
        self.planner = ContextBudgetPlanner(self.config)
        self.accountant = ProviderContextAccountant(
            estimator_uncertainty_percent=20
        )

    def _prepare(self, request):
        return self.planner.prepare(
            request,
            serializer=_serialize,
            estimator=lambda value: self.accountant.estimate(
                value,
                serialization_code="TEST_CHAT_V1",
            ),
        )

    def test_runtime_reduced_is_diagnostic_not_rejection(self):
        result = self._prepare(
            ContextBudgetRequest(
                "request-1",
                _model(governed=49152, runtime=32768),
                2048,
                (_mandatory(),),
            )
        )
        self.assertIsInstance(result, PreparedModelContext)
        assert isinstance(result, PreparedModelContext)
        self.assertIn("CTX_RUNTIME_LIMIT_REDUCED", result.diagnostic_reason_codes)
        self.assertEqual(result.effective_context_limit, 32768)

    def test_unknown_runtime_is_diagnostic(self):
        result = self._prepare(
            ContextBudgetRequest(
                "request-2",
                replace(_model(), runtime_execution_context_limit=None),
                2048,
                (_mandatory(),),
            )
        )
        self.assertIsInstance(result, PreparedModelContext)
        assert isinstance(result, PreparedModelContext)
        self.assertIn("CTX_RUNTIME_LIMIT_UNKNOWN", result.diagnostic_reason_codes)

    def test_mandatory_overflow_rejects(self):
        result = self._prepare(
            ContextBudgetRequest(
                "request-3",
                _model(governed=1024, runtime=1024),
                512,
                (_mandatory("x" * 5000),),
            )
        )
        self.assertIsInstance(result, ContextBudgetRejection)
        self.assertEqual(result.reason_code, "CTX_MANDATORY_OVERFLOW")

    def test_continuity_first_and_atomic_omission(self):
        result = self._prepare(
            ContextBudgetRequest(
                "request-4",
                _model(governed=2400, runtime=2400),
                512,
                (_mandatory("m" * 500),),
                (
                    _optional(
                        "floor",
                        ContextComponentKind.RECENT_DIALOGUE_FLOOR,
                        ContextPriority.CONTINUITY_FLOOR,
                        "f" * 900,
                    ),
                    _optional(
                        "primary",
                        ContextComponentKind.PRIMARY_EVIDENCE,
                        ContextPriority.PRIMARY_EVIDENCE,
                        "p" * 5000,
                    ),
                    _optional(
                        "older",
                        ContextComponentKind.RECENT_DIALOGUE,
                        ContextPriority.RECENT_DIALOGUE,
                        "o" * 100,
                    ),
                ),
            )
        )
        self.assertIsInstance(result, PreparedModelContext)
        assert isinstance(result, PreparedModelContext)
        self.assertIn("floor", result.allocation.selected_item_ids)
        self.assertIn("primary", result.allocation.omitted_item_ids)
        self.assertIn("older", result.allocation.selected_item_ids)
        self.assertNotIn("p" * 100, result.serialized_context)

    def test_final_safety_equation_uses_effective_limit(self):
        result = self._prepare(
            ContextBudgetRequest(
                "request-5",
                _model(governed=49152, runtime=8192),
                2048,
                (_mandatory("m" * 1000),),
            )
        )
        self.assertIsInstance(result, PreparedModelContext)
        assert isinstance(result, PreparedModelContext)
        total = (
            result.provider_estimate.safe_preflight_tokens
            + result.request.response_allowance
            + result.context_safety_reserve
        )
        self.assertLessEqual(total, 8192)


if __name__ == "__main__":
    unittest.main()
