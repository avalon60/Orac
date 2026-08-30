"""Tests for Phase 2C authorised semantic discovery and federation."""

# Author: Clive Bostock
# Date: 2026-08-29
# Description: Verifies discovery, opaque authority, partial failure, and ranking.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from model.plugin_routing.embeddings import EmbeddingProvider  # noqa: E402
from orac_core.conversation_memory import GovernedRetrievalResult  # noqa: E402
from orac_core.conversation_memory import RetrievalDomain  # noqa: E402
from orac_core.conversation_memory import RetrievalInitiator  # noqa: E402
from orac_core.conversation_memory import TrustedRetrievalContext  # noqa: E402
from orac_core.governed_retrieval import AuthorisedDomainBinding  # noqa: E402
from orac_core.governed_retrieval import AuthorisedKnowledgeDomain  # noqa: E402
from orac_core.governed_retrieval import DomainDiscoveryService  # noqa: E402
from orac_core.governed_retrieval import FederatedRetrievalExecutor  # noqa: E402
from orac_core.governed_retrieval import FederatedRetrievalRequest  # noqa: E402
from orac_core.governed_retrieval import FederatedEvidenceCandidate  # noqa: E402
from orac_core.governed_retrieval import FederatedGovernedRetrievalResult  # noqa: E402
from orac_core.governed_retrieval import GovernedRetrievalConfiguration  # noqa: E402
from orac_core.governed_retrieval import GovernedRetrievalToolCoordinator  # noqa: E402
from orac_core.governed_retrieval import KnowledgeDomainAdvertisement  # noqa: E402
from orac_core.governed_retrieval import KnowledgeDomainOffer  # noqa: E402
from orac_core.governed_retrieval import StructuredToolCall  # noqa: E402
from orac_core.governed_retrieval import ToolDecisionMode  # noqa: E402
from orac_core.governed_retrieval import ToolStreamEvent  # noqa: E402
from orac_core.governed_retrieval import ToolStreamEventKind  # noqa: E402
from orac_core.governed_retrieval import governed_retrieve_tool_schema  # noqa: E402
from orac_core.governed_retrieval import (
    domain_discovery_embedding_provider,
)  # noqa: E402
from orac_core.governed_retrieval import federated_rank_candidates  # noqa: E402
from orac_core.knowledge import KnowledgeScope  # noqa: E402
from orac_core.governed_retrieval.audit import _phase2c_json  # noqa: E402


class _SemanticEmbedding(EmbeddingProvider):
    """Small deterministic semantic fixture with observable batching."""

    def __init__(self) -> None:
        self.batches: list[tuple[str, ...]] = []

    @property
    def model_id(self) -> str:
        """Return a stable synthetic model identity."""
        return "synthetic-semantic-v1"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Map illustrative topics into independent semantic axes."""
        self.batches.append(tuple(texts))
        vectors = []
        for text in texts:
            lowered = text.casefold()
            vectors.append(
                [
                    (
                        1.0
                        if any(
                            word in lowered for word in ("chess", "alapin", "gambit")
                        )
                        else 0.0
                    ),
                    (
                        1.0
                        if any(
                            word in lowered for word in ("orac", "retrieval", "plugin")
                        )
                        else 0.0
                    ),
                    (
                        1.0
                        if any(word in lowered for word in ("sdk", "guardrail"))
                        else 0.0
                    ),
                    1.0 if "email" in lowered else 0.0,
                ]
            )
        return vectors


class _Catalogue:
    """Injectable current-authority catalogue fixture."""

    def __init__(self, rows, *, memory=True) -> None:
        self.rows = list(rows)
        self.memory = memory
        self.memory_calls = []

    def load_authorised_projects(self, principal_username, candidate_limit):
        """Return only fixture rows authorised to this principal."""
        assert principal_username == "alice"
        total = len(self.rows)
        return [
            {**row, "authorised_catalogue_size": total}
            for row in self.rows[:candidate_limit]
        ]

    def has_retrievable_conversation_memory(
        self, principal_username, embedding_model, embedding_dimensions
    ):
        """Capture compatibility parameters without inspecting memory content."""
        self.memory_calls.append(
            (principal_username, embedding_model, embedding_dimensions)
        )
        return self.memory


def _row(code, name, description, version="1"):
    return {
        "project_code": code,
        "display_name": name,
        "description": description,
        "descriptor_version": version,
    }


def _discovery(rows, *, memory=True, hard_limit=4096, maximum=3):
    embedding = _SemanticEmbedding()
    service = DomainDiscoveryService(
        repository=_Catalogue(rows, memory=memory),
        embedding_provider=embedding,
        profile_identity="domain_discovery:synthetic:v1",
        descriptor_schema_version="domain-descriptor-v1",
        minimum_score=0.50,
        semantic_weight=0.85,
        lexical_weight=0.15,
        embedding_batch_size=64,
        catalogue_hard_limit=hard_limit,
        max_advertised_domains=maximum,
        conversation_embedding_model="conversation-model-v1",
        conversation_embedding_dimensions=4,
    )
    return service, embedding


def test_alapin_discovers_only_authorised_relevant_synthetic_project() -> None:
    """Natural topical text discovers a project without an explicit scope name."""
    service, _ = _discovery(
        [
            _row(
                "SYN_CHESS", "Synthetic Chess", "Chess openings, tactics and gambits."
            ),
            _row("SYN_ORAC", "Synthetic Orac", "Orac plugins and governed retrieval."),
            _row("SYN_SDK", "Synthetic SDK", "SDK guardrails and integration."),
        ],
        memory=False,
    )
    offer = service.discover(
        query="What are the main attacking ideas in the Alapin Gambit?",
        principal_username="alice",
        conversation_eligible=False,
    )
    assert [item.display_name for item in offer.advertisements] == ["Synthetic Chess"]
    binding = offer.bindings[offer.advertisements[0].handle]
    assert binding.scope == KnowledgeScope("PROJECT", "SYN_CHESS")
    assert "SYN_CHESS" not in offer.render_instruction()


def test_cross_domain_question_advertises_two_relevant_synthetic_projects() -> None:
    """A generic cross-domain turn can produce a bounded two-domain offer."""
    service, _ = _discovery(
        [
            _row("SYN_ORAC", "Synthetic Orac", "Orac plugin implementation."),
            _row("SYN_SDK", "Synthetic SDK", "SDK integration guardrails."),
            _row("SYN_CHESS", "Synthetic Chess", "Chess openings and tactics."),
        ],
        memory=False,
    )
    offer = service.discover(
        query="How should Orac's plugin comply with our SDK guardrails?",
        principal_username="alice",
        conversation_eligible=False,
    )
    assert {item.display_name for item in offer.advertisements} == {
        "Synthetic Orac",
        "Synthetic SDK",
    }


def test_unrelated_turn_advertises_no_project_domain() -> None:
    """Access alone never causes an irrelevant PROJECT advertisement."""
    service, _ = _discovery(
        [_row("SYN_CHESS", "Synthetic Chess", "Chess openings and tactics.")],
        memory=False,
    )
    offer = service.discover(
        query="Write a friendly birthday greeting.",
        principal_username="alice",
        conversation_eligible=False,
    )
    assert offer.advertisements == ()


def test_discovery_embedding_profile_is_independent_of_conversation_memory() -> None:
    """The provider factory reads only the dedicated Core profile section."""

    class _Config:
        values = {
            "provider": "ollama",
            "service_url": "http://localhost:11434",
            "model_id": "domain-model-v1",
            "dimensions": 8,
            "profile_version": "domain-profile-v3",
        }

        def config_value(self, section, key, default=""):
            assert section == "embedding.domain_discovery"
            return self.values.get(key, default)

        def int_config_value(self, section, key, default=0):
            assert section == "embedding.domain_discovery"
            return self.values.get(key, default)

    provider, identity = domain_discovery_embedding_provider(_Config())
    assert provider.model_id == "domain-model-v1"
    assert identity == "ollama:domain-model-v1:8:domain-profile-v3"


def test_conversation_is_advertised_without_generic_descriptor_matching() -> None:
    """Natural topical recall remains possible without explicit recall language."""
    service, embedding = _discovery([], memory=True)
    offer = service.discover(
        query="I'm reconsidering the email ingestion design.",
        principal_username="alice",
        conversation_eligible=True,
    )
    assert len(offer.advertisements) == 1
    assert offer.advertisements[0].domain_type is RetrievalDomain.CONVERSATION
    assert offer.advertisements[0].display_name == "Previous conversations"
    assert offer.advertisements[0].relevance_score is None
    assert embedding.batches == []

    class _ConversationMediator:
        def available_domains(self, *, context):
            return (RetrievalDomain.CONVERSATION,)

        def retrieve(self, request, *, context):
            assert request.query == "I'm reconsidering the email ingestion design."
            return GovernedRetrievalResult(
                domain=RetrievalDomain.CONVERSATION,
                status="grounded",
                reason_codes=("conversation_memory_grounded",),
                evidence=(_Evidence("Earlier email decision", 1),),
                provenance={"message_ids": (1,)},
            )

    executor = FederatedRetrievalExecutor(
        mediator=_ConversationMediator(),
        project_authorizer=None,
        max_evidence_items=2,
    )
    result = executor.retrieve(
        FederatedRetrievalRequest(
            "I'm reconsidering the email ingestion design.",
            (offer.advertisements[0].handle,),
        ),
        offer=offer,
        context=TrustedRetrievalContext("alice", 100),
    )
    assert result.status == "grounded"
    assert result.evidence[0].evidence.text == "Earlier email decision"


def test_semantic_provider_failure_preserves_conversation_offer_and_fails_soft() -> (
    None
):
    """PROJECT discovery failure does not couple recall to its embedding profile."""

    class _UnavailableEmbedding(_SemanticEmbedding):
        def embed_texts(self, texts):
            raise RuntimeError("synthetic provider outage")

    service = DomainDiscoveryService(
        repository=_Catalogue(
            [_row("P1", "Synthetic Project", "Project documentation.")],
            memory=True,
        ),
        embedding_provider=_UnavailableEmbedding(),
        profile_identity="domain_discovery:unavailable:v1",
        descriptor_schema_version="domain-v1",
        conversation_embedding_model="conversation-v1",
        conversation_embedding_dimensions=4,
    )
    offer = service.discover(
        query="Project question",
        principal_username="alice",
        conversation_eligible=True,
    )
    assert offer.telemetry.fallback_mode == "SEMANTIC_PROVIDER_UNAVAILABLE"
    assert [item.domain_type for item in offer.advertisements] == [
        RetrievalDomain.CONVERSATION
    ]


def test_plugin_is_considered_only_with_a_trusted_runtime_binding() -> None:
    """The project catalogue never causes arbitrary plugin enumeration."""
    service, _ = _discovery([], memory=False)
    without_binding = service.discover(
        query="plugin image analysis",
        principal_username="alice",
        conversation_eligible=False,
    )
    assert without_binding.advertisements == ()
    bridge = object()
    plugin = AuthorisedKnowledgeDomain(
        domain_type=RetrievalDomain.PLUGIN,
        stable_identity="trusted-runtime-plugin",
        display_name="Synthetic image analysis",
        description="Image analysis plugin knowledge.",
        descriptor_version="runtime-v1",
        plugin_bridge=bridge,
    )
    with_binding = service.discover(
        query="plugin image analysis",
        principal_username="alice",
        conversation_eligible=False,
        plugin_domain=plugin,
    )
    assert [item.domain_type for item in with_binding.advertisements] == [
        RetrievalDomain.PLUGIN
    ]
    assert (
        with_binding.bindings[with_binding.advertisements[0].handle].plugin_bridge
        is bridge
    )


def test_large_normal_catalogue_has_no_routine_128_domain_cliff_and_caches() -> None:
    """All 129 authorised descriptors are evaluated in bounded cold batches."""
    rows = [
        _row(f"SYN_{index}", f"Domain {index}", "General unrelated material.")
        for index in range(128)
    ] + [_row("SYN_CHESS", "Synthetic Chess", "Chess gambits and openings.")]
    service, embedding = _discovery(rows, memory=False)
    first = service.discover(
        query="Alapin Gambit attacking ideas",
        principal_username="alice",
        conversation_eligible=False,
    )
    assert first.telemetry.domains_scored == 129
    assert first.telemetry.embedding_batches == 3
    assert first.telemetry.cache_misses == 129
    assert any(item.display_name == "Synthetic Chess" for item in first.advertisements)
    second = service.discover(
        query="Alapin Gambit attacking ideas",
        principal_username="alice",
        conversation_eligible=False,
    )
    assert second.telemetry.cache_hits == 129
    assert second.telemetry.cache_misses == 0
    assert second.telemetry.embedding_batches == 0
    assert len(embedding.batches) == 5  # two query calls plus three cold batches


def test_exceptional_hard_limit_omits_projects_but_preserves_conversation() -> None:
    """The defensive catalogue limit is distinct from ordinary evaluation bounds."""
    service, _ = _discovery(
        [_row(f"SYN_{index}", f"Domain {index}", "Material") for index in range(4)],
        memory=True,
        hard_limit=3,
    )
    offer = service.discover(
        query="anything",
        principal_username="alice",
        conversation_eligible=True,
    )
    assert offer.telemetry.fallback_mode == "CATALOGUE_HARD_LIMIT"
    assert offer.telemetry.domains_scored == 0
    assert [item.domain_type for item in offer.advertisements] == [
        RetrievalDomain.CONVERSATION
    ]


@dataclass(frozen=True)
class _Evidence:
    """Synthetic evidence with native score retained only for provenance/audit."""

    text: str
    chunk_id: int
    score: float = 0.0


def _binding(handle, domain_type, order, weight, scope_key=None):
    advertisement = KnowledgeDomainAdvertisement(
        handle=handle,
        domain_type=domain_type,
        display_name=f"Domain {order}",
        description="Synthetic fixture.",
        relevance_score=weight,
    )
    return AuthorisedDomainBinding(
        advertisement=advertisement,
        stable_identity=f"{domain_type.value}:{order}",
        advertised_order=order,
        domain_weight=weight,
        scope=(KnowledgeScope("PROJECT", scope_key) if scope_key else None),
    )


def test_weighted_diverse_federated_ranking_is_deterministic() -> None:
    """Domain relevance affects priority while each genuine domain gets a seed."""
    strong = _binding("d_strong", RetrievalDomain.PROJECT, 0, 1.0, "P1")
    weak = _binding("d_weak", RetrievalDomain.PROJECT, 1, 0.75, "P2")
    ranked = federated_rank_candidates(
        (
            (strong, (_Evidence("s1", 1), _Evidence("s2", 2), _Evidence("s3", 3))),
            (weak, (_Evidence("w1", 10), _Evidence("w2", 11))),
        ),
        maximum_items=5,
    )
    assert [(item.domain_handle, item.within_domain_rank) for item in ranked] == [
        ("d_strong", 1),
        ("d_weak", 1),
        ("d_strong", 2),
        ("d_strong", 3),
        ("d_weak", 2),
    ]
    assert ranked[0].native_score == 0.0


def test_ranking_handles_similar_domains_sparse_domain_and_tight_budget() -> None:
    """Synthetic merge cases cover similarity, sparse evidence, and truncation."""
    left = _binding("d_left", RetrievalDomain.PROJECT, 0, 0.90, "P1")
    right = _binding("d_right", RetrievalDomain.PROJECT, 1, 0.89, "P2")
    evidence = (
        (left, tuple(_Evidence(f"l{index}", index) for index in range(1, 6))),
        (right, (_Evidence("only", 20),)),
    )
    ranked = federated_rank_candidates(evidence, maximum_items=4)
    assert [item.domain_handle for item in ranked[:2]] == ["d_left", "d_right"]
    tight = federated_rank_candidates(evidence, maximum_items=1)
    assert [(item.domain_handle, item.within_domain_rank) for item in tight] == [
        ("d_left", 1)
    ]


class _Authorizer:
    """Return current authority per exact synthetic project scope."""

    def __init__(self, revoked=()) -> None:
        self.revoked = set(revoked)
        self.calls = []

    def resolve_for_user(self, username, names):
        """Resolve only the exact host binding supplied by federation."""
        self.calls.append((username, names))
        scope = KnowledgeScope.parse(names[0])
        if scope.scope_key in self.revoked:
            return SimpleNamespace(status="denied", scopes=())
        return SimpleNamespace(status="authorised", scopes=(scope,))


class _Mediator:
    """Existing adapter seam fixture."""

    def __init__(self) -> None:
        self.calls = []

    def available_domains(self, *, context):
        """Expose conversation only when its service would be active."""
        return (RetrievalDomain.CONVERSATION,)

    def retrieve(self, request, *, context):
        """Return evidence from the exact bound scope."""
        self.calls.append((request, context))
        scope_key = context.project_scope.scope_key
        return GovernedRetrievalResult(
            domain=request.domain,
            status="grounded",
            reason_codes=("evidence_selected",),
            evidence=(_Evidence(f"evidence-{scope_key}", len(self.calls)),),
            provenance={"scope": scope_key},
        )


def test_mid_turn_revocation_drops_only_that_advertised_domain() -> None:
    """An unrelated authorised domain still contributes evidence after revocation."""
    first = _binding("d_first", RetrievalDomain.PROJECT, 0, 1.0, "P1")
    second = _binding("d_second", RetrievalDomain.PROJECT, 1, 0.9, "P2")
    offer = KnowledgeDomainOffer(
        (first.advertisement, second.advertisement),
        {"d_first": first, "d_second": second},
    )
    mediator = _Mediator()
    executor = FederatedRetrievalExecutor(
        mediator=mediator,
        project_authorizer=_Authorizer(revoked={"P1"}),
        max_evidence_items=6,
    )
    result = executor.retrieve(
        FederatedRetrievalRequest("question", ("d_first", "d_second")),
        offer=offer,
        context=TrustedRetrievalContext(
            principal_username="alice",
            evidence_token_budget=100,
            initiator=RetrievalInitiator.MODEL_TOOL,
        ),
    )
    assert result.status == "grounded"
    assert result.unavailable_count == 1
    assert result.successful_domain_types == ("PROJECT",)
    assert [item.evidence.text for item in result.evidence] == ["evidence-P2"]
    assert [call[1].project_scope.scope_key for call in mediator.calls] == ["P2"]


def test_forged_duplicate_and_excessive_handles_reject_the_whole_call() -> None:
    """Invalid model input never reaches any domain adapter."""
    first = _binding("d_first", RetrievalDomain.PROJECT, 0, 1.0, "P1")
    second = _binding("d_second", RetrievalDomain.PROJECT, 1, 0.9, "P2")
    offer = KnowledgeDomainOffer(
        (first.advertisement, second.advertisement),
        {"d_first": first, "d_second": second},
    )
    coordinator = GovernedRetrievalToolCoordinator(
        mediator=_Mediator(),
        configuration=GovernedRetrievalConfiguration(
            enabled=True, max_selected_domains=2
        ),
        federated_executor=SimpleNamespace(),
    )
    for arguments in (
        '{"query":"x","domains":["d_forged"]}',
        '{"query":"x","domains":["d_first","d_first"]}',
        '{"query":"x","domains":["d_first","d_second","d_forged"]}',
        '{"query":"x","domains":"d_first"}',
        '{"query":"x","domains":["d_first"],"project_id":1}',
    ):
        call = StructuredToolCall("call-1", "retrieve", arguments)
        assert coordinator._validate_federated_call(call, offer) is None


def test_forged_handle_executes_no_adapter_and_uses_normal_fallback() -> None:
    """The coordinator enforces the authority boundary before federation."""
    binding = _binding("d_first", RetrievalDomain.PROJECT, 0, 1.0, "P1")
    offer = KnowledgeDomainOffer(
        (binding.advertisement,),
        {binding.advertisement.handle: binding},
    )

    class _Executor:
        calls = 0

        def retrieve(self, request, *, offer, context):
            self.calls += 1
            raise AssertionError("forged input reached federation")

    class _Connector:
        def stream_tool_events(self, *, messages, tools, generation_options):
            if tools:
                arguments = '{"query":"x","domains":["d_forged"]}'
                yield ToolStreamEvent(
                    ToolStreamEventKind.TOOL_CALL_START,
                    call_id="call-1",
                    tool_name="retrieve",
                )
                yield ToolStreamEvent(
                    ToolStreamEventKind.TOOL_CALL_ARGUMENT_DELTA,
                    call_id="call-1",
                    tool_name="retrieve",
                    arguments_delta=arguments,
                )
                yield ToolStreamEvent(
                    ToolStreamEventKind.TOOL_CALL_COMPLETED,
                    call_id="call-1",
                    tool_name="retrieve",
                )
                yield ToolStreamEvent(
                    ToolStreamEventKind.ASSISTANT_COMPLETION,
                    finish_reason="tool_calls",
                )
            else:
                yield ToolStreamEvent(
                    ToolStreamEventKind.ASSISTANT_TEXT_DELTA,
                    text="Ordinary fallback.",
                )

    executor = _Executor()
    coordinator = GovernedRetrievalToolCoordinator(
        mediator=_Mediator(),
        configuration=GovernedRetrievalConfiguration(enabled=True),
        federated_executor=executor,
    )
    execution = coordinator.begin(
        connector=_Connector(),
        messages=[{"role": "user", "content": "question"}],
        mode=ToolDecisionMode.STREAMING,
        allowed_domains=(),
        context=TrustedRetrievalContext("alice", 100),
        domain_offer=offer,
    )
    assert "".join(execution.stream()) == "Ordinary fallback."
    assert executor.calls == 0
    assert execution.result.retrieval_executed is False


def test_phase2c_schema_contains_only_query_and_invocation_handles() -> None:
    """Provider-native schema accepts no project, principal, or selector fields."""
    schema = governed_retrieve_tool_schema(
        domain_handles=("d_first", "d_second"), max_selected_domains=2
    )
    parameters = schema["function"]["parameters"]
    assert parameters["required"] == ["query", "domains"]
    assert parameters["additionalProperties"] is False
    assert parameters["properties"]["domains"]["uniqueItems"] is True
    assert parameters["properties"]["domains"]["items"]["enum"] == [
        "d_first",
        "d_second",
    ]
    assert set(parameters["properties"]) == {"query", "domains"}


def test_audit_contract_rejects_query_or_evidence_content_fields() -> None:
    """Only the fixed content-free telemetry shape can reach durable audit."""
    valid = {
        "schema_version": 1,
        "discovery": {
            "authorised_catalogue_size": 2,
            "domains_scored": 2,
            "advertised": [],
            "candidate_counts": {},
        },
        "selected_handles": [],
    }
    assert _phase2c_json(valid) is not None
    for forbidden in ("query", "prompt", "evidence_text"):
        invalid = dict(valid)
        invalid[forbidden] = "content"
        try:
            _phase2c_json(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"audit accepted forbidden field {forbidden}")


def test_final_context_guard_omits_lowest_ranked_federated_evidence() -> None:
    """Tight Phase 2B headroom keeps the strongest fitting evidence and provenance."""
    binding = _binding("d_first", RetrievalDomain.PROJECT, 0, 1.0, "P1")
    offer = KnowledgeDomainOffer(
        (binding.advertisement,),
        {binding.advertisement.handle: binding},
    )
    candidates = (
        FederatedEvidenceCandidate(
            "d_first",
            RetrievalDomain.PROJECT,
            0,
            1.0,
            1,
            0.9,
            "chunk:1",
            _Evidence("first-item", 1),
        ),
        FederatedEvidenceCandidate(
            "d_first",
            RetrievalDomain.PROJECT,
            0,
            1.0,
            2,
            0.8,
            "chunk:2",
            _Evidence("second-item", 2),
        ),
    )

    class _Executor:
        def retrieve(self, request, *, offer, context):
            return FederatedGovernedRetrievalResult(
                status="grounded",
                reason_codes=("federated_evidence_selected",),
                evidence=candidates,
                provenance={"domains": {}},
                selected_handles=request.domain_handles,
                successful_domain_types=("PROJECT",),
            )

    class _Connector:
        def __init__(self):
            self.calls = []

        def stream_tool_events(self, *, messages, tools, generation_options):
            self.calls.append((messages, tools))
            if tools:
                arguments = '{"query":"x","domains":["d_first"]}'
                yield ToolStreamEvent(
                    ToolStreamEventKind.TOOL_CALL_START,
                    call_id="call-1",
                    tool_name="retrieve",
                )
                yield ToolStreamEvent(
                    ToolStreamEventKind.TOOL_CALL_ARGUMENT_DELTA,
                    call_id="call-1",
                    tool_name="retrieve",
                    arguments_delta=arguments,
                )
                yield ToolStreamEvent(
                    ToolStreamEventKind.TOOL_CALL_COMPLETED,
                    call_id="call-1",
                    tool_name="retrieve",
                )
                yield ToolStreamEvent(
                    ToolStreamEventKind.ASSISTANT_COMPLETION,
                    finish_reason="tool_calls",
                )
            else:
                yield ToolStreamEvent(
                    ToolStreamEventKind.ASSISTANT_TEXT_DELTA,
                    text="Grounded answer.",
                )

    connector = _Connector()
    coordinator = GovernedRetrievalToolCoordinator(
        mediator=_Mediator(),
        configuration=GovernedRetrievalConfiguration(enabled=True),
        federated_executor=_Executor(),
    )
    execution = coordinator.begin(
        connector=connector,
        messages=[{"role": "user", "content": "question"}],
        mode=ToolDecisionMode.STREAMING,
        allowed_domains=(),
        context=TrustedRetrievalContext("alice", 100),
        domain_offer=offer,
        final_context_guard=lambda payload: "second-item" not in payload,
    )
    assert "".join(execution.stream()) == "Grounded answer."
    assert execution.result.selected_evidence_count == 1
    assert execution.result.omitted_evidence_count == 1
    assert execution.result.provenance["selected_evidence"] == [
        {
            "domain_type": "PROJECT",
            "domain_handle": "d_first",
            "within_domain_rank": 1,
            "native_score": 0.9,
            "domain_weight": 1.0,
            "chunk_id": 1,
        }
    ]
    assert connector.calls[-1][1] == []


def test_new_offer_uses_new_invocation_scoped_handles_and_current_grants() -> None:
    """Per-turn enumeration observes grants and never reuses opaque authority."""
    catalogue = _Catalogue([], memory=False)
    embedding = _SemanticEmbedding()
    service = DomainDiscoveryService(
        repository=catalogue,
        embedding_provider=embedding,
        profile_identity="domain_discovery:synthetic:v1",
        descriptor_schema_version="domain-v1",
        minimum_score=0.1,
        conversation_embedding_model="unused",
        conversation_embedding_dimensions=4,
    )
    empty = service.discover(
        query="Alapin", principal_username="alice", conversation_eligible=False
    )
    assert empty.advertisements == ()
    catalogue.rows.append(_row("P1", "Chess", "Chess gambits and openings."))
    granted = service.discover(
        query="Alapin", principal_username="alice", conversation_eligible=False
    )
    refreshed = service.discover(
        query="Alapin", principal_username="alice", conversation_eligible=False
    )
    assert len(granted.advertisements) == 1
    assert granted.advertisements[0].handle != refreshed.advertisements[0].handle
    assert refreshed.binding(granted.advertisements[0].handle) is None


def test_descriptor_version_and_profile_identity_invalidate_vector_cache() -> None:
    """Row and logical profile changes cannot silently reuse descriptor vectors."""
    rows = [_row("P1", "Domain", "Chess openings.", version="1")]
    catalogue = _Catalogue(rows, memory=False)
    embedding = _SemanticEmbedding()
    service = DomainDiscoveryService(
        repository=catalogue,
        embedding_provider=embedding,
        profile_identity="domain_discovery:model:v1",
        descriptor_schema_version="descriptor-v1",
        minimum_score=0.1,
        conversation_embedding_model="unused",
        conversation_embedding_dimensions=4,
    )
    service.discover(
        query="chess", principal_username="alice", conversation_eligible=False
    )
    catalogue.rows[0] = _row("P1", "Domain", "Chess openings.", version="2")
    outcome = service.discover(
        query="chess", principal_username="alice", conversation_eligible=False
    )
    assert outcome.telemetry.cache_misses == 1
    assert outcome.telemetry.cache_hits == 0
    replacement, _ = _discovery(rows, memory=False)
    assert replacement._profile_identity != service._profile_identity
