"""Opt-in live Ollama smoke test for LLM routing arbitration."""

# Author: Clive Bostock
# Date: 20-Sep-2026
# Description: Exercises structured routing without invoking a real plugin.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from model.arbitration_configuration import ArbitrationConfiguration
from model.arbitration_provider import OllamaArbitrationProvider
from model.llm_routing_adviser import LLMRoutingAdviser
from model.plugin_routing.models import PluginRouteCandidate

MODEL = os.environ.get("ORAC_ARBITRATION_SMOKE_MODEL", "").strip()
ENDPOINT = os.environ.get("ORAC_ARBITRATION_SMOKE_ENDPOINT", "").strip()


@pytest.mark.skipif(
    not MODEL or not ENDPOINT,
    reason="set ORAC_ARBITRATION_SMOKE_MODEL and ORAC_ARBITRATION_SMOKE_ENDPOINT",
)
def test_live_ollama_returns_valid_bounded_advice() -> None:
    """Exercise operational and informational arbitration through real Ollama."""
    candidate = PluginRouteCandidate(
        plugin_id="synthetic_lighting",
        capability_id="synthetic_lighting.read_state",
        intent_name="read_light_state",
        confidence=0.80,
        match_reasons=("route_intent_embedding",),
        route_key="synthetic_lighting::synthetic_lighting.read_state::read_light_state",
    )
    manifest = SimpleNamespace(plugin_id="synthetic_lighting")
    capability = SimpleNamespace(
        capability_id="synthetic_lighting.read_state",
        description="Read the current on/off state of a named light device.",
    )
    intent = SimpleNamespace(
        name="read_light_state",
        description="Inspect a named device's current state.",
        examples=("Show the current state of the lounge lamp.",),
    )
    manager = SimpleNamespace(route_records=lambda: ((manifest, capability, intent),))
    configuration = ArbitrationConfiguration(
        enabled=True,
        provider="ollama",
        model=MODEL,
        endpoint=ENDPOINT,
        timeout_seconds=120,
        min_confidence=0.90,
    )
    adviser = LLMRoutingAdviser(
        provider=OllamaArbitrationProvider(configuration),
        provider_name="ollama",
        model=MODEL,
        min_confidence=0.90,
        plugin_manager=manager,
    )

    operational = adviser.advise(
        request_text="Show the current state of the lounge lamp device.",
        permitted_candidates=(candidate,),
        invocation_reason="smoke_operational",
    )
    informational = adviser.advise(
        request_text="Tell me about the history of electric lights.",
        permitted_candidates=(candidate,),
        invocation_reason="smoke_informational",
    )

    transport_failures = {
        "timeout",
        "connection_failure",
        "provider_error",
        "malformed_envelope",
        "invalid_output",
    }
    assert operational.fallback_code not in transport_failures
    assert operational.selected_route == "plugin", (
        operational.selected_route,
        operational.fallback_code,
        operational.confidence,
    )
    assert operational.selected_candidate is candidate
    assert operational.selected_candidate_id == candidate.route_key
    assert operational.confidence >= 0.90
    assert informational.selected_route in {"direct_llm", "no_plugin_match"}
    assert informational.fallback_code in {None, "informational_request_veto"}
