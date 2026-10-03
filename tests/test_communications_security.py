"""Verify authority boundaries around communications and plugin arbitration."""

# Author: Clive Bostock
# Date: 2026-09-20
# Description: Tests eligibility filtering, arbiter bounds, and confirmation use.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from model.plugin_execution_policy import inspect_plugin_policy_eligibility
from model.plugin_execution_service import PluginExecutionService
from model.plugin_routing.handoff import PluginRoutingHandoff
from model.plugin_routing.models import ArbitrationDecision
from model.plugin_routing.models import PluginExecutionPolicy
from model.plugin_routing.models import PluginManifest
from model.plugin_routing.models import PluginRouteCandidate
from model.plugin_runtime import PluginExecutionResult
from orac_core.communications import CapabilityRestrictions
from orac_core.communications import ConversationContext
from orac_core.communications import Message
from orac_core.communications import MessageRole
from orac_core.communications import OracRequest
from orac_core.communications import PrincipalContext
from orac_core.communications import ToolDefinition
from orac_core.knowledge import KnowledgeScope
from orac_core.communications.runtime import _knowledge_scope_allowed
from orac_core.communications.runtime import _restrict_plugin_handoff
from orac_core.communications.runtime import OracCommunicationsRuntime
from orac_core.communications.runtime import _governed_retrieval_allowed


def _candidate(plugin_id: str, capability_id: str) -> PluginRouteCandidate:
    """Build a high-confidence route candidate."""
    return PluginRouteCandidate(
        plugin_id=plugin_id,
        capability_id=capability_id,
        intent_name="run",
        confidence=0.99,
        match_reasons=("test",),
    )


def _manifest(*, requires_confirmation: bool = False) -> PluginManifest:
    """Build a minimal enabled manifest."""
    return PluginManifest(
        schema_version=2,
        plugin_id="allowed",
        name="Allowed",
        description="Allowed plugin",
        version="1.0.0",
        enabled=True,
        capabilities=("allowed.run",),
        entitlements=(),
        entities=(),
        examples=(),
        entry_point="plugin:Plugin",
        manifest_path=Path("plugins/allowed.json"),
        plugin_dir=Path("plugins/allowed"),
        manifest_hash="unit",
        execution_policy=PluginExecutionPolicy(
            action_type=(
                "device_control" if requires_confirmation else "informational_read_only"
            ),
            requires_confirmation=requires_confirmation,
            allowed_by_default=not requires_confirmation,
            capabilities=("allowed.run",),
        ),
    )


class _EligibilityRouter:
    """Expose deterministic eligibility and record final invocations."""

    def __init__(self) -> None:
        self.calls = []

    def candidate_eligibility(self, candidate, *, meta=None):
        """Allow only the declared test capability."""
        return SimpleNamespace(
            executable=candidate.plugin_id == "allowed"
            and candidate.capability_id == "allowed.run"
        )

    def route(self, prompt, meta, handoff, auth_user, **kwargs):
        """Record and return a handled result."""
        self.calls.append(handoff.candidates[0])
        return PluginExecutionResult(plugin_id="allowed", content="handled")


class _SpyArbiter:
    """Record the exact candidates visible to arbitration."""

    def __init__(self, *, malicious: bool = False) -> None:
        self.seen = ()
        self.malicious = malicious

    def arbitrate(self, *, utterance, candidates, pending_context=None):
        """Select the eligible candidate or forge an ineligible result."""
        self.seen = candidates
        selected = (
            _candidate("denied", "denied.run") if self.malicious else candidates[0]
        )
        return ArbitrationDecision(
            decision_type="execute_plugin",
            selected_plugin_id=selected.plugin_id,
            selected_capability_id=selected.capability_id,
            selected_intent_name=selected.intent_name,
            candidates=(selected,),
            reason="test",
            utterance=utterance,
        )


def test_arbiter_sees_only_host_eligible_candidates() -> None:
    """Disabled or undeclared candidates must be absent from arbitration."""
    router = _EligibilityRouter()
    arbiter = _SpyArbiter()
    service = PluginExecutionService(
        plugin_router=router,
        plugin_arbiter=arbiter,
        logger=SimpleNamespace(log_warning=lambda *_: None, log_debug=lambda *_: None),
    )

    service.execute(
        prompt="run",
        meta={},
        handoff=PluginRoutingHandoff(
            candidates=(
                _candidate("allowed", "allowed.run"),
                _candidate("denied", "denied.run"),
            )
        ),
        auth_user="unit_user",
    )

    assert [candidate.plugin_id for candidate in arbiter.seen] == ["allowed"]
    assert [candidate.plugin_id for candidate in router.calls] == ["allowed"]


def test_malicious_arbiter_result_cannot_execute() -> None:
    """An arbiter cannot grant a capability outside its eligible input set."""
    router = _EligibilityRouter()
    service = PluginExecutionService(
        plugin_router=router,
        plugin_arbiter=_SpyArbiter(malicious=True),
        logger=SimpleNamespace(log_warning=lambda *_: None, log_debug=lambda *_: None),
    )

    result = service.execute(
        prompt="run",
        meta={},
        handoff=PluginRoutingHandoff(
            candidates=(_candidate("allowed", "allowed.run"),)
        ),
        auth_user="unit_user",
    )

    assert result is not None
    assert result.provenance["status"] == "rejected"
    assert router.calls == []


def test_policy_eligibility_has_no_confirmation_side_effects() -> None:
    """Pre-arbitration inspection must not create or consume tokens."""
    broker = SimpleNamespace(
        inspect_confirmation=lambda **_kwargs: SimpleNamespace(
            confirmed=False,
            reason="Confirmation required.",
        ),
        create_request=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("eligibility created a confirmation")
        ),
        consume_confirmation=lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("eligibility consumed a confirmation")
        ),
    )

    result = inspect_plugin_policy_eligibility(
        _manifest(requires_confirmation=True),
        meta={},
        confirmation_broker=broker,
    )

    assert not result.executable
    assert result.status == "requires_confirmation"


def test_empty_capability_restriction_removes_explicit_candidates() -> None:
    """An empty caller allowlist means permit none, including explicit routes."""
    handoff = PluginRoutingHandoff(candidates=(_candidate("allowed", "allowed.run"),))

    result = _restrict_plugin_handoff(
        handoff,
        restrictions=CapabilityRestrictions(capability_ids=frozenset()),
        selected_capability_id="allowed.run",
    )

    assert result is None


def test_caller_knowledge_restrictions_narrow_both_scope_types() -> None:
    """Project and plugin knowledge require an explicitly retained scope."""
    project = KnowledgeScope("PROJECT", "alpha")
    plugin = KnowledgeScope("PLUGIN", "weather")
    restrictions = CapabilityRestrictions(knowledge_scopes=(project,))

    assert _knowledge_scope_allowed(project, restrictions)
    assert not _knowledge_scope_allowed(plugin, restrictions)
    assert not _knowledge_scope_allowed(
        project,
        CapabilityRestrictions(knowledge_scopes=()),
    )
    assert _knowledge_scope_allowed(project, CapabilityRestrictions())


def test_external_session_references_are_principal_bound() -> None:
    """The same caller session label must not join two principals."""
    runtime = OracCommunicationsRuntime.__new__(OracCommunicationsRuntime)
    runtime._session_scope = "user"
    runtime._normalize_client = True

    alice_session = runtime._derive_session_id({"session_id": "shared"}, "alice")
    bob_session = runtime._derive_session_id({"session_id": "shared"}, "bob")

    assert alice_session == "alice::shared"
    assert bob_session == "bob::shared"
    assert alice_session != bob_session


def test_governed_tool_discovery_obeys_caller_capability_bounds() -> None:
    """Governed retrieval must not bypass an empty or unrelated allowlist."""
    retrieve = ToolDefinition(
        capability_id="knowledge.retrieve",
        name="retrieve",
        description="Retrieve authorised knowledge",
        parameters={"type": "object"},
    )

    def request(restrictions: CapabilityRestrictions) -> OracRequest:
        return OracRequest(
            request_id="req-tool",
            correlation_id="corr-tool",
            principal=PrincipalContext("alice"),
            conversation=ConversationContext(),
            message=Message(MessageRole.USER, "Recall this"),
            source="unit",
            restrictions=restrictions,
            tools=(retrieve,),
        )

    assert _governed_retrieval_allowed(request(CapabilityRestrictions()))
    assert not _governed_retrieval_allowed(
        request(CapabilityRestrictions(capability_ids=frozenset()))
    )
    assert not _governed_retrieval_allowed(
        request(CapabilityRestrictions(capability_ids=frozenset({"weather.read"})))
    )
    assert _governed_retrieval_allowed(
        request(
            CapabilityRestrictions(capability_ids=frozenset({"knowledge.retrieve"}))
        )
    )
