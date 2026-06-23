"""Handoff models and rendering helpers for plugin routing integration."""
# Author: Clive Bostock
# Date: 2026-04-23
# Description: Defines the stable handoff shape and prompt-hint rendering for plugin routing.

from __future__ import annotations

from dataclasses import dataclass

from model.plugin_routing.models import PluginCandidate, PluginRouteCandidate


@dataclass(frozen=True)
class PluginRoutingHandoff:
    """Represents candidate-routing output handed to downstream selection logic."""

    candidates: tuple[PluginRouteCandidate | PluginCandidate, ...]
    refreshed: bool = False


def render_plugin_routing_hints(handoff: PluginRoutingHandoff | None) -> str:
    """Formats candidate retrieval output as a narrow prompt hint block."""
    if handoff is None or not handoff.candidates:
        return ""

    lines = [
        "PLUGIN ROUTING CANDIDATES (retrieval hints only, not final decisions):"
    ]
    for candidate in handoff.candidates:
        score = getattr(candidate, "confidence", getattr(candidate, "score", 0.0))
        capability_id = getattr(candidate, "capability_id", "")
        intent_name = getattr(candidate, "intent_name", "")
        route_detail = ""
        if capability_id or intent_name:
            route_detail = (
                f"; capability_id: {capability_id}; intent_name: {intent_name}"
            )
        lines.append(
            f"- plugin_id: {candidate.plugin_id}; score: {float(score):.4f}"
            f"{route_detail}"
        )
    lines.append("")
    return "\n".join(lines)
