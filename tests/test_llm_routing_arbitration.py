"""Tests for bounded LLM-assisted plugin routing arbitration."""

# Author: Clive Bostock
# Date: 20-Sep-2026
# Description: Verifies abstention, false-positive controls, and revalidation.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from model.arbitration_provider import ArbitrationProviderError
from model.llm_routing_adviser import LLMRoutingAdviser
from model.plugin_confirmation_broker import PluginConfirmationBroker
from model.plugin_arbitration import PluginArbiter
from model.plugin_execution_service import PluginExecutionService
from model.plugin_router import PluginRouter
from model.plugin_routing.handoff import PluginRoutingHandoff
from model.plugin_routing.models import PluginExecutionPolicy
from model.plugin_routing.models import PluginManifest
from model.plugin_routing.models import PluginRouteCapability
from model.plugin_routing.models import PluginRouteCandidate
from model.plugin_routing.models import PluginRouteIntent
from model.plugin_runtime import PluginExecutionResult


class _Provider:
    """Return a configured response and record the bounded request."""

    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls = []

    def complete(self, *, messages, response_schema):
        """Record and return one fake completion."""
        self.calls.append((messages, response_schema))
        if self.error is not None:
            raise self.error
        return self.response


class _Logger:
    """Capture safe diagnostic messages."""

    def __init__(self) -> None:
        self.debug = []
        self.info = []
        self.warning = []
        self.error = []

    def log_debug(self, message) -> None:
        self.debug.append(message)

    def log_warning(self, message) -> None:
        self.warning.append(message)

    def log_info(self, message) -> None:
        self.info.append(message)

    def log_error(self, message) -> None:
        self.error.append(message)

    def log_exception(self, message, exception) -> None:
        self.error.append(message)


def _candidate(
    plugin_id="home_assistant",
    capability_id="home_assistant.light_control",
    intent_name="control_light",
    confidence=0.80,
    match_reasons=("route_intent_embedding",),
    extracted_params=None,
):
    """Build one immutable candidate for adviser tests."""
    return PluginRouteCandidate(
        plugin_id=plugin_id,
        capability_id=capability_id,
        intent_name=intent_name,
        confidence=confidence,
        match_reasons=match_reasons,
        extracted_params=extracted_params or {},
        safety_level="device_control",
        route_key=f"{plugin_id}::{capability_id}::{intent_name}",
    )


def _response(candidate, *, confidence=0.96, route="plugin"):
    return {
        "selected_route": route,
        "selected_candidate_id": (candidate.route_key if route == "plugin" else None),
        "confidence": confidence,
        "reason": "Clear operational request.",
    }


def _adviser(provider, *, threshold=0.90, logger=None):
    return LLMRoutingAdviser(
        provider=provider,
        provider_name="fake",
        model="router-test",
        min_confidence=threshold,
        logger=logger,
    )


def test_disabled_arbiter_preserves_deterministic_result() -> None:
    """An arbiter without an adviser must retain existing behaviour."""
    candidate = _candidate(confidence=0.95)
    decision = PluginArbiter().arbitrate(
        utterance="Turn on the lounge lights", candidates=(candidate,)
    )
    assert decision.decision_type == "execute_plugin"
    assert decision.reason == "clear_high_confidence_candidate"


def test_deterministic_interceptor_bypasses_adviser() -> None:
    """A confident real interception must take precedence over the model."""
    candidate = _candidate(
        confidence=1.0,
        match_reasons=("route_intent_embedding", "dialog_intercept"),
    )
    provider = _Provider(_response(candidate))
    decision = PluginArbiter(routing_adviser=_adviser(provider)).arbitrate(
        utterance="Turn on the lounge lights", candidates=(candidate,)
    )
    assert decision.decision_type == "execute_plugin"
    assert provider.calls == []


def test_high_embedding_only_candidate_invokes_adviser() -> None:
    """A high embedding score alone is not a deterministic interception."""
    candidate = _candidate(confidence=0.99)
    provider = _Provider(_response(candidate))
    decision = PluginArbiter(routing_adviser=_adviser(provider)).arbitrate(
        utterance="Turn on the lounge lights", candidates=(candidate,)
    )
    assert decision.reason == "llm_adviser_selected_plugin"
    assert len(provider.calls) == 1


def test_ambiguous_candidates_can_be_resolved_by_adviser() -> None:
    """The adviser may resolve two plausible already-permitted routes."""
    first = _candidate(confidence=0.82)
    second = _candidate("media", "media.light_scene", "light_scene", 0.81)
    provider = _Provider(_response(first))
    decision = PluginArbiter(routing_adviser=_adviser(provider)).arbitrate(
        utterance="Turn on the lounge lights", candidates=(first, second)
    )
    assert decision.selected_plugin_id == "home_assistant"


@pytest.mark.parametrize(
    "route",
    ["direct_llm", "no_plugin_match"],
)
def test_adviser_can_abstain_to_normal_fallback(route) -> None:
    """Both supported non-plugin decisions map to existing LLM fallback."""
    candidate = _candidate()
    provider = _Provider(_response(candidate, route=route))
    decision = PluginArbiter(routing_adviser=_adviser(provider)).arbitrate(
        utterance="Turn on the lounge lights", candidates=(candidate,)
    )
    assert decision.decision_type == "llm_fallback"
    assert route in decision.reason


@pytest.mark.parametrize(
    "request_text",
    [
        "Tell me about lights",
        "Tell me about how to check lights",
        "Find information about heating efficiency",
        "Explain thermostat controls",
        "Show me information about lights",
        "Check this information about heating efficiency",
    ],
)
def test_overconfident_informational_selection_is_vetoed(request_text) -> None:
    """Generic topical vocabulary cannot produce plugin interception."""
    candidate = _candidate()
    provider = _Provider(_response(candidate, confidence=1.0))
    advice = _adviser(provider).advise(
        request_text=request_text,
        permitted_candidates=(candidate,),
        invocation_reason="ambiguous",
    )
    assert advice.selected_route == "direct_llm"
    assert advice.fallback_code == "informational_request_veto"


def test_low_confidence_plugin_selection_falls_back() -> None:
    candidate = _candidate()
    advice = _adviser(_Provider(_response(candidate, confidence=0.89))).advise(
        request_text="Turn on the lights",
        permitted_candidates=(candidate,),
        invocation_reason="ambiguous",
    )
    assert advice.fallback_code == "plugin_confidence_below_threshold"


@pytest.mark.parametrize(
    ("response", "expected_code"),
    [
        ("not-json", "invalid_json"),
        ("```json\n{}\n```", "invalid_json"),
        (
            {
                "selected_route": "plugin",
                "selected_candidate_id": "fabricated",
                "confidence": 1.0,
                "reason": "x",
            },
            "invalid_candidate",
        ),
        (
            {
                "selected_route": "web_search",
                "selected_candidate_id": None,
                "confidence": 1.0,
                "reason": "x",
            },
            "unknown_route",
        ),
        (
            {
                "selected_route": "direct_llm",
                "selected_candidate_id": "x",
                "confidence": 1.0,
                "reason": "x",
            },
            "non_plugin_candidate",
        ),
        (
            {
                "selected_route": "direct_llm",
                "selected_candidate_id": None,
                "confidence": float("nan"),
                "reason": "x",
            },
            "invalid_confidence",
        ),
        (
            {
                "selected_route": "direct_llm",
                "selected_candidate_id": None,
                "confidence": True,
                "reason": "x",
            },
            "invalid_confidence",
        ),
        (
            {
                "selected_route": "direct_llm",
                "selected_candidate_id": None,
                "confidence": 1.0,
                "reason": "x",
                "extra": 1,
            },
            "invalid_fields",
        ),
    ],
)
def test_invalid_or_out_of_set_outputs_fail_safe(response, expected_code) -> None:
    candidate = _candidate()
    advice = _adviser(_Provider(response)).advise(
        request_text="Turn on the lights",
        permitted_candidates=(candidate,),
        invocation_reason="ambiguous",
    )
    assert advice.selected_route == "direct_llm"
    assert advice.fallback_code == expected_code


def test_duplicate_json_keys_and_oversized_output_have_safe_categories() -> None:
    candidate = _candidate()
    base = (
        '{"selected_route":"direct_llm","selected_route":"plugin",'
        '"selected_candidate_id":null,"confidence":1,"reason":"x"}'
    )
    duplicate = _adviser(_Provider(base)).advise(
        request_text="Turn on the lights",
        permitted_candidates=(candidate,),
        invocation_reason="ambiguous",
    )
    oversized = _adviser(_Provider("x" * 4001)).advise(
        request_text="Turn on the lights",
        permitted_candidates=(candidate,),
        invocation_reason="ambiguous",
    )
    assert duplicate.fallback_code == "duplicate_key"
    assert oversized.fallback_code == "oversized_output"


def test_duplicate_candidate_ids_and_excess_semantics_abstain_before_provider() -> None:
    first = _candidate()
    duplicate = _candidate()
    provider = _Provider(_response(first))
    duplicate_result = _adviser(provider).advise(
        request_text="Turn on the lights",
        permitted_candidates=(first, duplicate),
        invocation_reason="ambiguous",
    )
    assert duplicate_result.fallback_code == "duplicate_candidate_id"
    assert provider.calls == []

    long_candidate = _candidate(intent_name="x" * 501)
    long_result = _adviser(provider).advise(
        request_text="Turn on the lights",
        permitted_candidates=(long_candidate,),
        invocation_reason="ambiguous",
    )
    assert long_result.fallback_code == "description_out_of_bounds"
    assert provider.calls == []


def test_prompt_contains_only_bounded_semantics_not_candidate_metadata() -> None:
    """Extracted scopes, knowledge, and secrets must not reach the provider."""
    candidate = _candidate(
        extracted_params={
            "project_scope": "PROJECT:SECRET",
            "plugin_scope": "PLUGIN:PRIVATE",
            "credential": "do-not-send",
        }
    )
    provider = _Provider(_response(candidate, route="no_plugin_match"))
    _adviser(provider).advise(
        request_text="Turn on the lights",
        permitted_candidates=(candidate,),
        invocation_reason="ambiguous",
    )
    serialised = repr(provider.calls[0][0])
    assert "PROJECT:SECRET" not in serialised
    assert "PLUGIN:PRIVATE" not in serialised
    assert "do-not-send" not in serialised
    assert "web_search" not in serialised
    assert (
        "retrieval" not in provider.calls[0][1]["properties"]["selected_route"]["enum"]
    )


def test_prompt_names_the_exact_strict_response_contract() -> None:
    """Providers receive field guidance as well as a machine schema."""
    candidate = _candidate()
    provider = _Provider(_response(candidate, route="no_plugin_match"))
    _adviser(provider).advise(
        request_text="Turn on the lights",
        permitted_candidates=(candidate,),
        invocation_reason="ambiguous",
    )
    messages, schema = provider.calls[0]
    prompt_text = " ".join(message["content"] for message in messages)
    assert "selected_route" in prompt_text
    assert "selected_candidate_id" in prompt_text
    assert "confidence" in prompt_text
    assert "reason" in prompt_text
    assert schema["additionalProperties"] is False


class _RevalidatingRouter:
    """Change eligibility between the initial and fresh checks."""

    def __init__(self, *, revoke=False) -> None:
        self.revoke = revoke
        self.checks = 0
        self.calls = []

    def candidate_eligibility(self, candidate, *, meta=None):
        self.checks += 1
        return SimpleNamespace(executable=not (self.revoke and self.checks > 1))

    def route(self, prompt, meta, handoff, auth_user, **kwargs):
        self.calls.append(handoff.candidates[0])
        return PluginExecutionResult(plugin_id="home_assistant", content="ok")


def test_service_revalidates_llm_selection_and_uses_original_object() -> None:
    original = _candidate()
    provider = _Provider(_response(original))
    router = _RevalidatingRouter()
    service = PluginExecutionService(
        plugin_router=router,
        plugin_arbiter=PluginArbiter(routing_adviser=_adviser(provider)),
        logger=_Logger(),
    )
    result = service.execute(
        prompt="Turn on the lights",
        meta={},
        handoff=PluginRoutingHandoff(candidates=(original,)),
        auth_user="user",
    )
    assert result is not None
    assert router.checks == 2
    assert router.calls == [original]
    assert router.calls[0] is original


def test_revoked_candidate_falls_back_without_invocation() -> None:
    original = _candidate()
    router = _RevalidatingRouter(revoke=True)
    service = PluginExecutionService(
        plugin_router=router,
        plugin_arbiter=PluginArbiter(
            routing_adviser=_adviser(_Provider(_response(original)))
        ),
        logger=_Logger(),
    )
    result = service.execute(
        prompt="Turn on the lights",
        meta={},
        handoff=PluginRoutingHandoff(candidates=(original,)),
        auth_user="user",
    )
    assert result is None
    assert router.calls == []


@pytest.mark.parametrize(
    "code",
    ["timeout", "connection_failure", "provider_error", "model_unavailable"],
)
def test_provider_failure_returns_none_to_runtime_continuation(code) -> None:
    """A provider error leaves the existing retrieval and LLM path reachable."""
    candidate = _candidate(confidence=0.99)
    provider = _Provider(error=ArbitrationProviderError(code))
    router = _RevalidatingRouter()
    service = PluginExecutionService(
        plugin_router=router,
        plugin_arbiter=PluginArbiter(routing_adviser=_adviser(provider)),
        logger=_Logger(),
    )
    result = service.execute(
        prompt="Turn on the lights",
        meta={},
        handoff=PluginRoutingHandoff(candidates=(candidate,)),
        auth_user="user",
    )
    assert result is None
    assert router.calls == []
    assert len(provider.calls) == 1


def test_provider_failure_crosses_communications_runtime_seam() -> None:
    """The runtime receives None and can continue its ordinary request flow."""
    from orac_core.communications.runtime import OracCommunicationsRuntime

    candidate = _candidate(confidence=0.99)
    provider = _Provider(error=ArbitrationProviderError("timeout"))
    router = _RevalidatingRouter()
    runtime = OracCommunicationsRuntime.__new__(OracCommunicationsRuntime)
    runtime.plugin_execution_service = PluginExecutionService(
        plugin_router=router,
        plugin_arbiter=PluginArbiter(routing_adviser=_adviser(provider)),
        logger=_Logger(),
    )
    result = runtime._execute_plugin_request(
        prompt="Turn on the lights",
        meta={},
        plugin_routing_handoff=PluginRoutingHandoff(candidates=(candidate,)),
        auth_user="user",
    )
    assert result is None
    assert router.calls == []
    assert len(provider.calls) == 1


def test_missing_eligibility_checker_never_exposes_candidates_to_adviser() -> None:
    """The adviser cannot receive candidates that lack deterministic gating."""
    candidate = _candidate()
    provider = _Provider(_response(candidate))
    router = SimpleNamespace(route=lambda *_args, **_kwargs: None)
    service = PluginExecutionService(
        plugin_router=router,
        plugin_arbiter=PluginArbiter(routing_adviser=_adviser(provider)),
        logger=_Logger(),
    )
    service.execute(
        prompt="Turn on the lights",
        meta={},
        handoff=PluginRoutingHandoff(candidates=(candidate,)),
        auth_user="user",
    )
    assert provider.calls == []


def test_real_adviser_sees_only_candidates_allowed_by_router() -> None:
    """Denied identities must be absent from the model task and schema."""
    allowed = _candidate()
    denied = _candidate("denied", "denied.run", "run", 0.81)

    class _Router(_RevalidatingRouter):
        def candidate_eligibility(self, candidate, *, meta=None):
            return SimpleNamespace(executable=candidate.plugin_id != "denied")

    provider = _Provider(_response(allowed, route="no_plugin_match"))
    service = PluginExecutionService(
        plugin_router=_Router(),
        plugin_arbiter=PluginArbiter(routing_adviser=_adviser(provider)),
        logger=_Logger(),
    )
    service.execute(
        prompt="Turn on the lights",
        meta={},
        handoff=PluginRoutingHandoff(candidates=(allowed, denied)),
        auth_user="user",
    )
    provider_text = repr(provider.calls)
    assert allowed.route_key in provider_text
    assert denied.route_key not in provider_text


def test_high_embedding_informational_request_falls_back_through_arbiter() -> None:
    """Even an overconfident model cannot intercept a topical question."""
    candidate = _candidate(confidence=0.99)
    decision = PluginArbiter(
        routing_adviser=_adviser(_Provider(_response(candidate, confidence=1.0)))
    ).arbitrate(
        utterance="Tell me about lights",
        candidates=(candidate,),
    )
    assert decision.decision_type == "llm_fallback"
    assert decision.reason == "llm_adviser_informational_request_veto"


def test_unavailable_enabled_provider_does_not_restore_embedding_interception() -> None:
    """Enabled-mode provider failure remains a safe normal-flow fallback."""
    from model.arbitration_provider import UnavailableArbitrationProvider

    candidate = _candidate(confidence=0.99)
    adviser = _adviser(UnavailableArbitrationProvider("runtime_unavailable"))
    decision = PluginArbiter(routing_adviser=adviser).arbitrate(
        utterance="Turn on the lights",
        candidates=(candidate,),
    )
    assert decision.decision_type == "llm_fallback"
    assert decision.reason == "llm_adviser_runtime_unavailable"


def _manifest(
    plugin_id: str,
    *,
    enabled: bool = True,
    allowed_by_default: bool = True,
    requires_confirmation: bool = False,
) -> PluginManifest:
    """Build a manifest with one fully declared route capability."""
    capability_id = f"{plugin_id}.run"
    intent = PluginRouteIntent(
        name="run",
        description=f"Run the exact {plugin_id} operation.",
        examples=(f"Run {plugin_id} now.",),
        requires_confirmation=requires_confirmation,
        safety_level=(
            "device_control" if requires_confirmation else "informational_read_only"
        ),
    )
    return PluginManifest(
        schema_version=2,
        plugin_id=plugin_id,
        name=plugin_id.replace("_", " ").title(),
        description=f"{plugin_id} test plugin",
        version="1.0.0",
        enabled=enabled,
        capabilities=(capability_id,),
        entitlements=(),
        entities=(),
        examples=(),
        entry_point="plugin:Plugin",
        manifest_path=Path(f"plugins/{plugin_id}.json"),
        plugin_dir=Path(f"plugins/{plugin_id}"),
        manifest_hash="test",
        execution_policy=PluginExecutionPolicy(
            action_type=(
                "device_control" if requires_confirmation else "informational_read_only"
            ),
            requires_confirmation=requires_confirmation,
            allowed_by_default=allowed_by_default,
            capabilities=(capability_id,),
        ),
        route_capabilities=(
            PluginRouteCapability(
                capability_id=capability_id,
                description=f"Run {plugin_id}.",
                intents=(intent,),
            ),
        ),
    )


class _ManifestManager:
    """Expose exact manifests to the real PluginRouter."""

    def __init__(self, *manifests: PluginManifest) -> None:
        self.manifests = {manifest.plugin_id: manifest for manifest in manifests}

    def get_manifest(self, plugin_id):
        return self.manifests.get(plugin_id)

    def route_records(self):
        return tuple(
            (manifest, capability, intent)
            for manifest in self.manifests.values()
            for capability in manifest.route_capabilities
            for intent in capability.intents
        )


def _manifest_candidate(manifest: PluginManifest) -> PluginRouteCandidate:
    capability = manifest.route_capabilities[0]
    intent = capability.intents[0]
    return PluginRouteCandidate(
        plugin_id=manifest.plugin_id,
        capability_id=capability.capability_id,
        intent_name=intent.name,
        confidence=0.80,
        match_reasons=("route_intent_embedding",),
        requires_confirmation=bool(intent.requires_confirmation),
        safety_level=str(intent.safety_level),
        route_key=(f"{manifest.plugin_id}::{capability.capability_id}::{intent.name}"),
    )


def test_real_router_excludes_disabled_undeclared_and_policy_blocked_candidates() -> (
    None
):
    """The real eligibility boundary supplies only executable capabilities."""
    allowed = _manifest("allowed")
    disabled = _manifest("disabled", enabled=False)
    blocked = _manifest("blocked", allowed_by_default=False)
    manager = _ManifestManager(allowed, disabled, blocked)
    router = PluginRouter(
        plugin_manager=manager,
        logger=_Logger(),
        config_mgr=object(),
        context_manager=object(),
        execution_timeout_seconds=1,
        plugin_db_session_factory=lambda *_args, **_kwargs: None,
    )
    allowed_candidate = _manifest_candidate(allowed)
    undeclared_candidate = PluginRouteCandidate(
        plugin_id="allowed",
        capability_id="allowed.fabricated",
        intent_name="run",
        confidence=0.80,
        match_reasons=("route_intent_embedding",),
        route_key="allowed::allowed.fabricated::run",
    )
    provider = _Provider(_response(allowed_candidate, route="no_plugin_match"))
    service = PluginExecutionService(
        plugin_router=router,
        plugin_arbiter=PluginArbiter(
            plugin_manager=manager,
            routing_adviser=_adviser(provider),
        ),
        logger=_Logger(),
    )
    service.execute(
        prompt="Run the allowed operation",
        meta={},
        handoff=PluginRoutingHandoff(
            candidates=(
                allowed_candidate,
                _manifest_candidate(disabled),
                _manifest_candidate(blocked),
                undeclared_candidate,
            )
        ),
        auth_user="user",
    )
    provider_text = repr(provider.calls)
    assert allowed_candidate.route_key in provider_text
    assert "disabled::" not in provider_text
    assert "blocked::" not in provider_text
    assert "allowed.fabricated" not in provider_text


class _CountingConfirmationBroker(PluginConfirmationBroker):
    """Count confirmation operations across eligibility and final policy."""

    def __init__(self) -> None:
        super().__init__(token_factory=lambda: "confirmation-1")
        self.created = 0
        self.inspected = 0
        self.consumed = 0

    def create_request(self, *args, **kwargs):
        self.created += 1
        return super().create_request(*args, **kwargs)

    def inspect_confirmation(self, *args, **kwargs):
        self.inspected += 1
        return super().inspect_confirmation(*args, **kwargs)

    def consume_confirmation(self, *args, **kwargs):
        self.consumed += 1
        return super().consume_confirmation(*args, **kwargs)


def test_real_router_keeps_confirmation_consumption_in_final_policy(
    monkeypatch,
) -> None:
    """The adviser neither issues nor consumes a confirmed action token."""
    manifest = _manifest("confirmed", requires_confirmation=True)
    candidate = _manifest_candidate(manifest)
    manager = _ManifestManager(manifest)
    broker = _CountingConfirmationBroker()
    request = broker.create_request(manifest, manifest.execution_policy)
    broker.confirm_request(request.confirmation_id)
    broker.created = 0
    router = PluginRouter(
        plugin_manager=manager,
        logger=_Logger(),
        config_mgr=object(),
        context_manager=object(),
        confirmation_broker=broker,
        execution_timeout_seconds=1,
        plugin_db_session_factory=lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        router,
        "_invoke_plugin_candidate",
        lambda **_kwargs: PluginExecutionResult(
            plugin_id="confirmed",
            content="confirmed operation executed",
        ),
    )
    provider = _Provider(_response(candidate))
    service = PluginExecutionService(
        plugin_router=router,
        plugin_arbiter=PluginArbiter(
            plugin_manager=manager,
            routing_adviser=_adviser(provider),
        ),
        logger=_Logger(),
    )
    result = service.execute(
        prompt="Run the confirmed operation now",
        meta={
            "plugin_confirmation": {
                "confirmation_id": request.confirmation_id,
            }
        },
        handoff=PluginRoutingHandoff(candidates=(candidate,)),
        auth_user="user",
    )
    assert result is not None
    assert result.content == "confirmed operation executed"
    assert broker.inspected == 2
    assert broker.consumed == 1
    assert broker.created == 0
    assert len(provider.calls) == 1


def test_explicit_addressing_preserves_host_routed_prompt_through_service() -> None:
    """Deterministic transformed parameters retain disabled-mode behaviour."""
    original = _candidate(confidence=0.70)
    manager = SimpleNamespace(
        _manifests={
            "home_assistant": SimpleNamespace(
                plugin_id="home_assistant",
                name="Home Assistant",
            )
        }
    )
    router = _RevalidatingRouter()
    service = PluginExecutionService(
        plugin_router=router,
        plugin_arbiter=PluginArbiter(plugin_manager=manager),
        logger=_Logger(),
    )
    service.execute(
        prompt="Ask Home Assistant to turn on the lounge lamp",
        meta={},
        handoff=PluginRoutingHandoff(candidates=(original,)),
        auth_user="user",
    )
    routed = router.calls[0]
    assert routed is not original
    assert routed.extracted_params["routed_prompt"] == "turn on the lounge lamp"
