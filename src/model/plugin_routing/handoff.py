"""Handoff models and rendering helpers for plugin routing integration."""
# Author: Clive Bostock
# Date: 2026-04-23
# Description: Defines the stable handoff shape and prompt-hint rendering for plugin routing.

from __future__ import annotations

from dataclasses import dataclass

from model.plugin_routing.models import PluginCandidate


@dataclass(frozen=True)
class PluginRoutingHandoff:
    """Represents candidate-routing output handed to downstream selection logic."""

    candidates: tuple[PluginCandidate, ...]
    refreshed: bool = False


def render_plugin_routing_hints(handoff: PluginRoutingHandoff | None) -> str:
    """Formats candidate retrieval output as a narrow prompt hint block."""
    if handoff is None or not handoff.candidates:
        return ""

    lines = [
        "PLUGIN ROUTING CANDIDATES (retrieval hints only, not final decisions):"
    ]
    for candidate in handoff.candidates:
        lines.append(f"- plugin_id: {candidate.plugin_id}; score: {candidate.score:.4f}")
    lines.append("")
    return "\n".join(lines)
