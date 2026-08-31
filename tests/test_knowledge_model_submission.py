"""Tests for final P1-08 model submission guards."""

# Author: Clive Bostock
# Date: 14-Aug-2026
# Description: Verifies stale-state, context-budget, and strict invocation controls.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
import uuid

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from orac_core.knowledge.evidence import EvidenceEnvelope  # noqa: E402
from orac_core.knowledge.materialisation_policy import (  # noqa: E402
    MaterialisationApprovalSnapshot,
)
from orac_core.knowledge.model_submission import (  # noqa: E402
    KnowledgeModelSubmissionGuard,
    KnowledgeEvidenceFollowUpLimits,
    KnowledgeEvidenceFollowUpTracker,
    ModelRegistrySnapshot,
    ModelSubmissionRejection,
    PrepareModelSubmissionRequest,
    PreparedModelSubmission,
    PromptContextSnapshot,
)
from orac_core.knowledge.scope import KnowledgeScope  # noqa: E402
from orac_core.knowledge.token_estimation import (  # noqa: E402
    ConservativeUtf8TokenEstimator,
)


class KnowledgeModelSubmissionGuardTests(unittest.TestCase):
    """Exercise final immutable prompt checks without database or model access."""

    def setUp(self) -> None:
        self.estimator = ConservativeUtf8TokenEstimator()
        self.envelope_text = (
            "ORAC_UNTRUSTED_EVIDENCE_BEGIN version=1\n"
            '{"parts":[],"schema":"orac.untrusted_evidence","version":1}\n'
            "ORAC_UNTRUSTED_EVIDENCE_END version=1"
        )
        envelope_estimate = self.estimator.estimate_envelope(self.envelope_text)
        self.envelope = EvidenceEnvelope(
            version=1,
            text=self.envelope_text,
            byte_size=len(self.envelope_text.encode("utf-8")),
            safe_token_count=envelope_estimate.safe_token_count,
            part_count=1,
            content_digest="0" * 64,
            complete=True,
            selected=False,
            downgraded=False,
            non_truncated=True,
        )
        self.model = ModelRegistrySnapshot(
            llm_id=7,
            row_version=4,
            provider_code="ollama",
            model_name="qwen",
            model_type="TEXT",
            context_policy_code="APP",
            max_context_tokens=32768,
            processing_locality="LOCAL",
            text_evidence_eligible=True,
        )
        self.approval = MaterialisationApprovalSnapshot(
            policy_request_id=str(uuid.uuid4()),
            principal_username="clive",
            scope=KnowledgeScope("PROJECT", "ORAC_CORE"),
            target_type="DOCUMENT_VERSION",
            target_id=87,
            llm_id=7,
            registry_row_version=4,
            context_policy_code="APP",
            policy_version="P1-07.1",
            policy_config_fingerprint="policy-1",
        )

    def request(self, **overrides) -> PrepareModelSubmissionRequest:
        """Return one valid immutable submission fixture."""
        values = {
            "submission_id": str(uuid.uuid4()),
            "request_id": str(uuid.uuid4()),
            "approval": self.approval,
            "envelope": self.envelope,
            "prompt": f"Trusted directive.\n{self.envelope_text}\nCurrent user message.",
            "prompt_context": PromptContextSnapshot(
                conversation_id=3,
                highest_turn_index=8,
                system_prompt_fingerprint="system-1",
                policy_config_fingerprint="policy-1",
            ),
            "model": self.model,
        }
        values.update(overrides)
        return PrepareModelSubmissionRequest(**values)

    def test_eligible_exact_snapshot_is_approved_and_audited(self) -> None:
        audit: list[dict] = []
        guard = KnowledgeModelSubmissionGuard(
            estimator=self.estimator,
            registry_reader=lambda llm_id: self.model,
            decision_recorder=lambda **kwargs: audit.append(kwargs),
        )

        prepared = guard.prepare(self.request())

        self.assertIsInstance(prepared, PreparedModelSubmission)
        assert isinstance(prepared, PreparedModelSubmission)
        self.assertEqual(prepared.invocation_options.max_output_tokens, 2048)
        self.assertFalse(prepared.invocation_options.allow_endpoint_fallback)
        self.assertFalse(prepared.invocation_options.allow_output_budget_growth)
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0]["reason_code"], "MAT_SUB_APPROVED")

    def test_effective_context_uses_smaller_runtime_limit(self) -> None:
        runtime_limited = replace(
            self.model,
            max_context_tokens=49152,
            runtime_context_tokens=32768,
            runtime_observation_source="OLLAMA_SHOW",
            runtime_observation_fingerprint="runtime-1",
        )

        self.assertEqual(runtime_limited.effective_context_tokens, 32768)
        self.assertTrue(runtime_limited.runtime_constrained)
        self.assertIsNone(
            KnowledgeModelSubmissionGuard().model_eligibility_reason(
                runtime_limited
            )
        )

    def test_runtime_limit_below_context_floor_is_ineligible(self) -> None:
        runtime_limited = replace(
            self.model,
            max_context_tokens=49152,
            runtime_context_tokens=32767,
            runtime_observation_source="OLLAMA_SHOW",
            runtime_observation_fingerprint="runtime-1",
        )
        guard = KnowledgeModelSubmissionGuard(
            estimator=self.estimator,
            registry_reader=lambda llm_id: runtime_limited,
        )

        result = guard.prepare(self.request(model=runtime_limited))

        self.assertEqual(
            result.reason_code,
            "MAT_SUB_MODEL_CONTEXT_BELOW_MINIMUM",
        )

    def test_unknown_runtime_uses_governed_context_floor(self) -> None:
        guard = KnowledgeModelSubmissionGuard()

        self.assertEqual(self.model.effective_context_tokens, 32768)
        self.assertIsNone(guard.model_eligibility_reason(self.model))

    def test_runtime_observation_change_is_stale(self) -> None:
        approved = replace(
            self.model,
            max_context_tokens=49152,
            runtime_context_tokens=32768,
            runtime_observation_source="OLLAMA_SHOW",
            runtime_observation_fingerprint="runtime-1",
        )
        current = replace(
            approved,
            runtime_context_tokens=49152,
            runtime_observation_fingerprint="runtime-2",
        )
        guard = KnowledgeModelSubmissionGuard(
            registry_reader=lambda llm_id: current,
        )

        result = guard.prepare(self.request(model=approved))

        self.assertEqual(result.reason_code, "MAT_SUB_MODEL_STALE")

    def test_registry_row_change_requires_fresh_p1_07(self) -> None:
        stale = replace(self.model, row_version=5)
        guard = KnowledgeModelSubmissionGuard(
            estimator=self.estimator,
            registry_reader=lambda llm_id: stale,
        )

        result = guard.prepare(self.request())

        self.assertIsInstance(result, ModelSubmissionRejection)
        self.assertEqual(result.reason_code, "MAT_SUB_MODEL_STALE")

    def test_null_or_zero_context_limit_is_ineligible(self) -> None:
        unknown = ModelRegistrySnapshot(
            llm_id=7,
            row_version=4,
            provider_code="ollama",
            model_name="qwen",
            model_type="TEXT",
            context_policy_code="APP",
            max_context_tokens=0,
            processing_locality="LOCAL",
            text_evidence_eligible=True,
        )
        guard = KnowledgeModelSubmissionGuard(
            estimator=self.estimator,
            registry_reader=lambda llm_id: unknown,
        )

        result = guard.prepare(self.request(model=unknown))

        self.assertEqual(result.reason_code, "MAT_SUB_MODEL_CONTEXT_UNKNOWN")

    def test_evidence_share_over_25_percent_is_rejected(self) -> None:
        small_model = ModelRegistrySnapshot(
            llm_id=7,
            row_version=4,
            provider_code="ollama",
            model_name="qwen",
            model_type="TEXT",
            context_policy_code="APP",
            max_context_tokens=2600,
            processing_locality="LOCAL",
            text_evidence_eligible=True,
        )
        approval = MaterialisationApprovalSnapshot(
            **{
                "policy_request_id": self.approval.policy_request_id,
                "principal_username": "clive",
                "scope": self.approval.scope,
                "target_type": "DOCUMENT_VERSION",
                "target_id": 87,
                "llm_id": 7,
                "registry_row_version": 4,
                "context_policy_code": "APP",
                "policy_version": "P1-07.1",
                "policy_config_fingerprint": "policy-1",
            }
        )
        guard = KnowledgeModelSubmissionGuard(
            estimator=self.estimator,
            registry_reader=lambda llm_id: small_model,
            min_effective_context_tokens=1,
        )

        result = guard.prepare(self.request(model=small_model, approval=approval))

        self.assertEqual(result.reason_code, "MAT_SUB_EVIDENCE_SHARE_EXCEEDED")

    def test_policy_fingerprint_change_is_rejected(self) -> None:
        context = PromptContextSnapshot(
            conversation_id=3,
            highest_turn_index=8,
            system_prompt_fingerprint="system-1",
            policy_config_fingerprint="policy-2",
        )

        result = KnowledgeModelSubmissionGuard().prepare(
            self.request(prompt_context=context)
        )

        self.assertEqual(result.reason_code, "MAT_SUB_POLICY_STALE")

    def test_output_reserve_cannot_be_silently_changed(self) -> None:
        result = KnowledgeModelSubmissionGuard().prepare(
            self.request(reserved_output_tokens=4096)
        )

        self.assertEqual(result.reason_code, "MAT_SUB_OUTPUT_RESERVE_EXCEEDED")

    def test_budget_configuration_cannot_relax_approved_safety_limits(self) -> None:
        with self.assertRaisesRegex(ValueError, "5% minimum"):
            KnowledgeModelSubmissionGuard(context_safety_percent=4)
        with self.assertRaisesRegex(ValueError, "256 minimum"):
            KnowledgeModelSubmissionGuard(context_safety_min_tokens=255)
        with self.assertRaisesRegex(ValueError, "cannot exceed 25"):
            KnowledgeModelSubmissionGuard(max_evidence_context_percent=26)
        with self.assertRaisesRegex(ValueError, "must be positive"):
            KnowledgeModelSubmissionGuard(min_effective_context_tokens=0)

    def test_follow_up_configuration_cannot_exceed_approved_ceilings(self) -> None:
        excessive_limits = (
            {"max_rounds": 3},
            {"max_bytes": 512 * 1024 + 1},
            {"max_safe_tokens": 24_001},
            {"max_members": 17},
            {"max_chunks": 65},
            {"max_rows": 2_001},
            {"max_elapsed_seconds": 121},
        )

        for overrides in excessive_limits:
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(ValueError, "exceed P1-08 ceilings"):
                    KnowledgeEvidenceFollowUpLimits(**overrides)

    def test_follow_up_tracker_allows_only_two_bounded_rounds(self) -> None:
        tracker = KnowledgeEvidenceFollowUpTracker()
        now = datetime.now(timezone.utc)
        state = tracker.register_initial(
            conversation_id=3,
            principal_username="clive",
            scope=self.approval.scope,
            target_type="DOCUMENT_VERSION",
            target_id=87,
            registered_artefact_ids=(410,),
            registered_chunk_ids=(),
            envelope=self.envelope,
            now=now,
        )
        self.assertNotIsInstance(state, ModelSubmissionRejection)
        first = tracker.register_follow_up(
            state,
            principal_username="clive",
            scope=self.approval.scope,
            target_type="DOCUMENT_VERSION",
            target_id=87,
            envelope=self.envelope,
            now=now + timedelta(seconds=1),
        )
        self.assertNotIsInstance(first, ModelSubmissionRejection)
        second = tracker.register_follow_up(
            first,
            principal_username="clive",
            scope=self.approval.scope,
            target_type="DOCUMENT_VERSION",
            target_id=87,
            envelope=self.envelope,
            now=now + timedelta(seconds=2),
        )
        self.assertNotIsInstance(second, ModelSubmissionRejection)

        rejected = tracker.register_follow_up(
            second,
            principal_username="clive",
            scope=self.approval.scope,
            target_type="DOCUMENT_VERSION",
            target_id=87,
            envelope=self.envelope,
            now=now + timedelta(seconds=3),
        )

        self.assertEqual(rejected.reason_code, "MAT_SUB_FOLLOW_UP_LIMIT")

        unregistered = tracker.register_follow_up(
            state,
            principal_username="clive",
            scope=self.approval.scope,
            target_type="DOCUMENT_VERSION",
            target_id=87,
            envelope=self.envelope,
            evidence_chunk_ids=(999,),
            now=now + timedelta(milliseconds=500),
        )
        self.assertEqual(
            unregistered.reason_code,
            "MAT_SUB_REAUTHORISATION_REQUIRED",
        )

    def test_follow_up_tracker_enforces_rows_and_expiry(self) -> None:
        tracker = KnowledgeEvidenceFollowUpTracker(
            KnowledgeEvidenceFollowUpLimits(max_rows=1, max_elapsed_seconds=1)
        )
        now = datetime.now(timezone.utc)
        csv_envelope = replace(self.envelope, row_count=2)

        rejected = tracker.register_initial(
            conversation_id=3,
            principal_username="clive",
            scope=self.approval.scope,
            target_type="DOCUMENT_VERSION",
            target_id=87,
            registered_artefact_ids=(410,),
            registered_chunk_ids=(),
            envelope=csv_envelope,
            now=now,
        )

        self.assertEqual(rejected.reason_code, "MAT_SUB_FOLLOW_UP_LIMIT")

        initial = KnowledgeEvidenceFollowUpTracker(
            KnowledgeEvidenceFollowUpLimits(max_elapsed_seconds=1)
        ).register_initial(
            conversation_id=3,
            principal_username="clive",
            scope=self.approval.scope,
            target_type="DOCUMENT_VERSION",
            target_id=87,
            registered_artefact_ids=(410,),
            registered_chunk_ids=(),
            envelope=self.envelope,
            now=now,
        )
        expired = tracker.register_follow_up(
            initial,
            principal_username="clive",
            scope=self.approval.scope,
            target_type="DOCUMENT_VERSION",
            target_id=87,
            envelope=self.envelope,
            now=now + timedelta(seconds=2),
        )
        self.assertEqual(expired.reason_code, "MAT_SUB_FOLLOW_UP_LIMIT")


if __name__ == "__main__":
    unittest.main()
