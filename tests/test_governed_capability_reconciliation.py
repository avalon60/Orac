"""Tests for automatic governed-tool capability reconciliation."""

# Author: Clive Bostock
# Date: 2026-08-31
# Description: Verifies evidence maturity, retries, context gating, and SQL wiring.

from __future__ import annotations

from pathlib import Path
import sys
import types
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from controller.orac import Orac  # noqa: E402
from orac_core.context_budget import ContextBudgetConfiguration  # noqa: E402
from orac_core.context_budget import ContextModelSnapshot  # noqa: E402
from orac_core.governed_retrieval import EffectiveToolModeResolver  # noqa: E402
from orac_core.governed_retrieval import GovernedRetrievalConfiguration  # noqa: E402
from orac_core.governed_retrieval import (  # noqa: E402
    GOVERNED_RETRIEVAL_SYSTEM_INSTRUCTION,
)
from orac_core.governed_retrieval import ModelToolCapabilityEvidence  # noqa: E402
from orac_core.governed_retrieval import KnowledgeDomainAdvertisement  # noqa: E402
from orac_core.governed_retrieval import KnowledgeDomainOffer  # noqa: E402
from orac_core.governed_retrieval import ProbeOutcome  # noqa: E402
from orac_core.conversation_memory.models import RetrievalDomain  # noqa: E402
from orac_core.governed_retrieval import StreamingHealthKey  # noqa: E402
from orac_core.governed_retrieval import StreamingToolHealthTracker  # noqa: E402
from orac_core.governed_retrieval import StructuredToolCapabilityProbe  # noqa: E402
from orac_core.governed_retrieval import ToolDecisionMode  # noqa: E402
from orac_core.governed_retrieval import ToolStreamEvent  # noqa: E402
from orac_core.governed_retrieval import ToolStreamEventKind as Kind  # noqa: E402
from orac_core.governed_retrieval.discovery import (  # noqa: E402
    AuthorisedDomainBinding,
    DomainDiscoveryTelemetry,
)


def _valid_events():
    """Return one provider-completed valid tool call."""
    return [
        ToolStreamEvent(Kind.TOOL_CALL_START, tool_name="retrieve"),
        ToolStreamEvent(
            Kind.TOOL_CALL_ARGUMENT_DELTA,
            tool_name="retrieve",
            arguments_delta=(
                '{"query":"fixture","domain":"CONVERSATION"}'
            ),
        ),
        ToolStreamEvent(Kind.TOOL_CALL_COMPLETED, tool_name="retrieve"),
        ToolStreamEvent(Kind.ASSISTANT_COMPLETION, finish_reason="tool_calls"),
    ]


class _RetryConnector:
    """Fail transiently twice, then complete both probe stages."""

    def __init__(self) -> None:
        self.buffered_calls = 0
        self.streamed_calls = 0

    def buffered_tool_events(self, **_kwargs):
        self.buffered_calls += 1
        if self.buffered_calls < 3:
            raise TimeoutError("temporary")
        yield from _valid_events()

    def stream_tool_events(self, **_kwargs):
        self.streamed_calls += 1
        yield from _valid_events()


class CapabilityReconciliationTests(unittest.TestCase):
    """Verify provisional metadata and deterministic probe behaviour."""

    def test_metadata_is_provisional_and_does_not_enable_buffered_mode(self):
        resolver = EffectiveToolModeResolver(
            health_tracker=StreamingToolHealthTracker()
        )
        mode, reason = resolver.resolve(
            enabled=True,
            evidence=ModelToolCapabilityEvidence(
                model_revision="digest",
                structured_evidence_state="MODEL_METADATA_VERIFIED",
            ),
            provider_structured_supported=True,
            provider_streamed_supported=True,
            health_key=StreamingHealthKey(
                "ollama", "runtime", "adapter", 1, "digest"
            ),
            authority_available=True,
            context_safe=True,
        )
        self.assertEqual(mode, ToolDecisionMode.NONE)
        self.assertEqual(reason, "STRUCTURED_TOOL_PROBE_PENDING")

    def test_transient_retry_schedule_is_exact_and_bounded(self):
        connector = _RetryConnector()
        delays: list[float] = []
        report = StructuredToolCapabilityProbe().run_with_retries(
            connector,
            sleep=delays.append,
        )
        self.assertEqual(delays, [10.0, 30.0])
        self.assertEqual(connector.buffered_calls, 3)
        self.assertEqual(connector.streamed_calls, 1)
        self.assertEqual(report.structured.outcome, ProbeOutcome.PASS)
        self.assertEqual(report.structured.attempts, 3)
        self.assertEqual(report.streamed.outcome, ProbeOutcome.PASS)

    def test_provider_completed_invalid_output_is_not_retried(self):
        class _Rejected:
            def __init__(self) -> None:
                self.calls = 0

            def buffered_tool_events(self, **_kwargs):
                self.calls += 1
                yield ToolStreamEvent(
                    Kind.ASSISTANT_TEXT_DELTA,
                    text="I cannot use tools.",
                )
                yield ToolStreamEvent(Kind.ASSISTANT_COMPLETION)

        connector = _Rejected()
        delays: list[float] = []
        report = StructuredToolCapabilityProbe().run_with_retries(
            connector,
            sleep=delays.append,
        )
        self.assertEqual(connector.calls, 1)
        self.assertEqual(delays, [])
        self.assertEqual(report.structured.outcome, ProbeOutcome.MODEL_REJECTED)
        self.assertEqual(report.streamed.outcome, ProbeOutcome.NOT_RUN)


class AdvancedContextFloorTests(unittest.TestCase):
    """Keep the advanced floor isolated from explicit bounded retrieval."""

    def test_sub_floor_model_suppresses_only_advanced_tool_preparation(self):
        orchestrator = Orac.__new__(Orac)
        orchestrator.governed_retrieval_coordinator = object()
        orchestrator.governed_retrieval_configuration = (
            GovernedRetrievalConfiguration(
                enabled=True,
                domain_discovery_enabled=True,
                domain_discovery_shadow_mode=False,
                min_effective_context_tokens=32768,
            )
        )
        orchestrator.governed_tool_mode_resolver = object()
        orchestrator.host_retrieval_mediator = object()
        orchestrator.ctx = types.SimpleNamespace(
            get_llm_registry_entry=lambda _llm_id: {
                "LLM_ID": 7,
                "MODEL": "small-model",
                "MAX_CONTEXT_TOKENS": 16384,
                "PROPERTIES": {"digest": "small-digest"},
            }
        )
        orchestrator._context_model_snapshot = lambda **_kwargs: ContextModelSnapshot(
            llm_id=7,
            registry_row_version=1,
            provider_code="ollama",
            model_name="small-model",
            governed_model_context_limit=16384,
            runtime_execution_context_limit=16384,
        )
        result = orchestrator._prepare_governed_tool_execution(
            llm_connector=object(),
            final_prompt="ordinary question",
            discovery_query="ordinary question",
            auth_user="clive",
            session_id="session",
            request_id="request",
            effective_llm_id=7,
            effective_provider="ollama",
            effective_service_url="http://localhost",
            generation_options={"num_predict": 256},
        )
        self.assertIsNone(result)

        source = (PROJECT_ROOT / "src/controller/orac.py").read_text(
            encoding="utf-8"
        )
        explicit_retrieval = source.index("self.knowledge_retrieval_service.retrieve")
        advanced_preparation = source.index("self._prepare_governed_tool_execution(")
        self.assertLess(explicit_retrieval, advanced_preparation)
        self.assertIn(
            "and knowledge_route_decision is None",
            source[advanced_preparation - 1200 : advanced_preparation],
        )


class GovernedProductionFramingTests(unittest.TestCase):
    """Verify host-required semantics and compact production decision framing."""

    @staticmethod
    def _orchestrator(offer: KnowledgeDomainOffer):
        orchestrator = Orac.__new__(Orac)
        captured = {}

        class _Coordinator:
            def begin(self, **kwargs):
                captured.update(kwargs)
                return object()

        orchestrator.governed_retrieval_coordinator = _Coordinator()
        orchestrator.governed_retrieval_configuration = (
            GovernedRetrievalConfiguration(
                enabled=True,
                domain_discovery_enabled=True,
                domain_discovery_shadow_mode=False,
                min_effective_context_tokens=32768,
            )
        )
        orchestrator.governed_tool_mode_resolver = types.SimpleNamespace(
            resolve=lambda **_kwargs: (ToolDecisionMode.STREAMING, "VERIFIED")
        )
        orchestrator.host_retrieval_mediator = types.SimpleNamespace(
            available_domains=lambda **_kwargs: (RetrievalDomain.CONVERSATION,)
        )
        orchestrator.domain_discovery_service = types.SimpleNamespace(
            discover=lambda **_kwargs: offer
        )
        orchestrator.conversation_memory_retrieval_service = None
        orchestrator._use_history = True
        orchestrator.ctx = types.SimpleNamespace(
            _conversation_id=lambda _session_id: 12,
            get_llm_registry_entry=lambda _llm_id: {
                "LLM_ID": 2,
                "MODEL": "qwen3.6-48K:latest",
                "MAX_CONTEXT_TOKENS": 49152,
                "PROPERTIES": {"digest": "qwen-revision"},
            },
        )
        orchestrator._context_model_snapshot = lambda **_kwargs: ContextModelSnapshot(
            llm_id=2,
            registry_row_version=1,
            provider_code="ollama",
            model_name="qwen3.6-48K:latest",
            governed_model_context_limit=49152,
            runtime_execution_context_limit=49152,
        )
        orchestrator.context_budget_configuration = ContextBudgetConfiguration(
            enabled=False
        )
        orchestrator.governed_token_estimator = None
        orchestrator._governed_capability_evidence = lambda _llm_id: (
            ModelToolCapabilityEvidence(
                structured_tool_calling=True,
                streamed_structured_tool_calling=True,
                model_revision="qwen-revision",
                structured_evidence_state="BOUNDED_PROBE_VERIFIED",
                streamed_evidence_state="BOUNDED_PROBE_VERIFIED",
            )
        )
        orchestrator.provider_registry = types.SimpleNamespace(
            capabilities=lambda _provider: types.SimpleNamespace(
                supports_structured_tool_calling=True,
                supports_streamed_structured_tool_calling=True,
            )
        )
        return orchestrator, captured

    @staticmethod
    def _offer(*, semantic_matches: int) -> KnowledgeDomainOffer:
        domain_type = (
            RetrievalDomain.PROJECT
            if semantic_matches
            else RetrievalDomain.CONVERSATION
        )
        advertisement = KnowledgeDomainAdvertisement(
            handle="opaque-handle",
            domain_type=domain_type,
            display_name=("Orac Core" if semantic_matches else "Previous conversations"),
            description="Safe routing metadata.",
            relevance_score=(0.63 if semantic_matches else None),
        )
        binding = AuthorisedDomainBinding(
            advertisement=advertisement,
            stable_identity=(
                "PROJECT:ORAC_CORE"
                if semantic_matches
                else "principal-conversation-memory"
            ),
            advertised_order=0,
            domain_weight=1.0,
        )
        return KnowledgeDomainOffer(
            advertisements=(advertisement,),
            bindings={advertisement.handle: binding},
            telemetry=DomainDiscoveryTelemetry(
                semantic_matches=semantic_matches,
                semantic_advertised_count=semantic_matches,
                conversation_advertised_count=int(not semantic_matches),
                advertised_count=1,
            ),
        )

    def test_ai_os_semantic_match_requires_compact_tool_decision(self):
        orchestrator, captured = self._orchestrator(
            self._offer(semantic_matches=1)
        )
        preparation = orchestrator._prepare_governed_tool_execution(
            llm_connector=object(),
            final_prompt="COMPLETE FLATTENED PRODUCTION PROMPT",
            discovery_query="What is the AI OS?",
            auth_user="clive",
            session_id="session",
            request_id="request",
            effective_llm_id=2,
            effective_provider="ollama",
            effective_service_url="http://localhost",
            generation_options={"num_predict": 256},
        )

        self.assertTrue(preparation.retrieval_required)
        self.assertEqual(
            preparation.requirement_reason_codes,
            ("SEMANTIC_DOMAIN_MATCH",),
        )
        self.assertTrue(captured["retrieval_required"])
        self.assertEqual(captured["messages"][-1]["content"], "What is the AI OS?")
        self.assertNotIn("COMPLETE FLATTENED", str(captured["messages"]))
        self.assertIn("COMPLETE FLATTENED", str(captured["answer_messages"]))

    def test_conversation_only_offer_keeps_optional_full_context_path(self):
        orchestrator, captured = self._orchestrator(
            self._offer(semantic_matches=0)
        )
        preparation = orchestrator._prepare_governed_tool_execution(
            llm_connector=object(),
            final_prompt="COMPLETE FLATTENED PRODUCTION PROMPT",
            discovery_query="Tell me more.",
            auth_user="clive",
            session_id="session",
            request_id="request",
            effective_llm_id=2,
            effective_provider="ollama",
            effective_service_url="http://localhost",
            generation_options={"num_predict": 256},
        )

        self.assertFalse(preparation.retrieval_required)
        self.assertFalse(captured["retrieval_required"])
        self.assertEqual(captured["messages"], captured["answer_messages"])

    def test_explicit_local_intent_retains_required_state_when_tools_unavailable(self):
        orchestrator = Orac.__new__(Orac)
        preparation = orchestrator._prepare_governed_tool_execution(
            llm_connector=object(),
            final_prompt="complete prompt",
            discovery_query="Check your knowledge base for the answer.",
            auth_user="clive",
            session_id="session",
            request_id="request",
            effective_llm_id=2,
            effective_provider="ollama",
            effective_service_url="http://localhost",
            generation_options={"num_predict": 256},
            explicit_local_retrieval_intent=True,
        )

        self.assertTrue(preparation.retrieval_required)
        self.assertIsNone(preparation.execution)
        self.assertEqual(
            preparation.requirement_reason_codes,
            ("EXPLICIT_LOCAL_RETRIEVAL_INTENT",),
        )
        self.assertEqual(
            preparation.unavailable_reason,
            "GOVERNED_RETRIEVAL_NOT_INITIALISED",
        )

    def test_context_budget_shadow_and_enforced_modes_preserve_required_framing(
        self,
    ) -> None:
        class _Connector:
            @staticmethod
            def provider_context_serialization(*, messages, tools):
                return f"messages={len(messages)} tools={len(tools)}", "fixture"

        for shadow_mode in (True, False):
            with self.subTest(shadow_mode=shadow_mode):
                orchestrator, captured = self._orchestrator(
                    self._offer(semantic_matches=1)
                )
                orchestrator.context_budget_configuration = (
                    ContextBudgetConfiguration(
                        enabled=True,
                        shadow_mode=shadow_mode,
                    )
                )
                orchestrator.context_budget_accountant = types.SimpleNamespace(
                    estimate=lambda *_args, **_kwargs: types.SimpleNamespace(
                        safe_preflight_tokens=1000
                    )
                )
                orchestrator.context_budget_planner = types.SimpleNamespace(
                    context_safety_reserve=lambda _limit: 512
                )

                preparation = orchestrator._prepare_governed_tool_execution(
                    llm_connector=_Connector(),
                    final_prompt="COMPLETE FLATTENED PRODUCTION PROMPT",
                    discovery_query="What is the AI OS?",
                    auth_user="clive",
                    session_id="session",
                    request_id="request",
                    effective_llm_id=2,
                    effective_provider="ollama",
                    effective_service_url="http://localhost",
                    generation_options={"num_predict": 256},
                )

                self.assertTrue(preparation.retrieval_required)
                self.assertTrue(captured["retrieval_required"])
                self.assertNotIn("COMPLETE FLATTENED", str(captured["messages"]))


class DatabaseLifecycleAssetTests(unittest.TestCase):
    """Verify the connected least-privilege evidence lifecycle assets."""

    def test_promotion_closes_current_row_before_inserting_stronger_evidence(self):
        package = (
            PROJECT_ROOT
            / "resources/db/schema/orac_code/package_body/llm_capability_evidence_api.sql"
        ).read_text(encoding="utf-8").lower()
        close_position = package.index("close_current(p_llm_id, p_capability_code);")
        insert_position = package.index("insert_evidence(", close_position)
        self.assertLess(close_position, insert_position)
        self.assertIn("model_metadata_verified", package)
        self.assertIn("bounded_probe_verified", package)
        self.assertIn("probe_model_rejected", package)

    def test_unique_index_and_grant_chain_are_present(self):
        index_sql = (
            PROJECT_ROOT
            / "resources/db/schema/orac_core/index/llm_modcap_uk1_idx.sql"
        ).read_text(encoding="utf-8").lower()
        api_grant = (
            PROJECT_ROOT
            / "resources/db/schema/orac_api/grant/llm_model_capabilities_code_write.sql"
        ).read_text(encoding="utf-8").lower()
        runtime_grant = (
            PROJECT_ROOT
            / "resources/db/schema/orac_code/grant/llm_capability_evidence_runtime.sql"
        ).read_text(encoding="utf-8").lower()
        self.assertIn("case when effective_to is null then llm_id end", index_sql)
        self.assertIn("llm_model_capabilities_tapi to orac_code", api_grant)
        self.assertIn("llm_capability_evidence_api to orac", runtime_grant)


class DescriptorDiscriminationTests(unittest.TestCase):
    """Preserve the reviewed general-purpose ORAC_CORE descriptor evidence."""

    def test_descriptor_is_truthful_and_reviewed_fixture_scores_discriminate(self):
        migration = (
            PROJECT_ROOT
            / "resources/db/schema/orac_core/seed_data/zz_orac_core_project_descriptor.sql"
        ).read_text(encoding="utf-8").lower()
        self.assertIn("artificial intelligence knowledge", migration)
        self.assertIn("ai operating systems", migration)
        self.assertIn("model governance", migration)
        self.assertNotIn("what is the ai os?", migration)

        positive_scores = (0.628741, 0.679061, 0.678002, 0.695801)
        negative_scores = (0.283360, 0.338930, 0.322406, 0.326615)
        self.assertTrue(all(score >= 0.50 for score in positive_scores))
        self.assertTrue(all(score < 0.50 for score in negative_scores))
        self.assertGreater(min(positive_scores), max(negative_scores))

    def test_domain_descriptor_is_routing_metadata_not_answer_evidence(self):
        instruction = GOVERNED_RETRIEVAL_SYSTEM_INSTRUCTION.lower()
        self.assertIn("routing metadata, not evidence", instruction)
        self.assertIn("factual answer depends on an advertised domain", instruction)
        self.assertIn("must issue exactly one structured tool call", instruction)

    def test_semantic_match_requires_retrieval_but_conversation_only_does_not(self):
        advertisement = KnowledgeDomainAdvertisement(
            handle="opaque",
            domain_type=RetrievalDomain.PROJECT,
            display_name="Orac Core",
            description="Authorised AI knowledge.",
            relevance_score=0.63,
        )
        binding = AuthorisedDomainBinding(
            advertisement=advertisement,
            stable_identity="PROJECT:ORAC_CORE",
            advertised_order=0,
            domain_weight=1.0,
        )
        matched = KnowledgeDomainOffer(
            advertisements=(advertisement,),
            bindings={"opaque": binding},
            telemetry=DomainDiscoveryTelemetry(semantic_matches=1),
        )
        conversation_only = KnowledgeDomainOffer(
            advertisements=(advertisement,),
            bindings={"opaque": binding},
            telemetry=DomainDiscoveryTelemetry(semantic_matches=0),
        )
        self.assertIn("MUST call retrieve exactly once", matched.render_instruction())
        self.assertNotIn(
            "MUST call retrieve exactly once",
            conversation_only.render_instruction(),
        )


class RegistryMetadataTests(unittest.TestCase):
    """Keep exact revision identity when startup normalises provider metadata."""

    def test_backend_model_normalisation_preserves_digest(self):
        details = Orac._normalise_backend_model_details(
            {
                "name": "model:latest",
                "digest": "sha256:exact-model-revision",
                "details": {"parameter_size": "7B"},
            }
        )
        self.assertEqual(details["digest"], "sha256:exact-model-revision")
        self.assertEqual(details["parameter_size"], "7B")


if __name__ == "__main__":
    unittest.main()
