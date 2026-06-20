"""Deterministic canonical intent text generation for plugin manifests."""
# Author: Clive Bostock
# Date: 2026-04-23
# Description: Builds stable canonical intent text used for plugin routing embeddings.

from __future__ import annotations

from model.plugin_routing.models import PluginManifest, PluginRouteCapability, PluginRouteIntent

INTENT_TEXT_VERSION = "plugin-intent-text-v1"


def build_canonical_intent_text(manifest: PluginManifest) -> str:
    """Builds deterministic canonical text for manifest-driven routing.

    Formatting rules:
      - Sections always appear in the same order.
      - Only routing-semantic fields are included.
      - Required scalar fields are emitted as single lines.
      - Optional list sections are omitted when empty.
      - List item order follows manifest order after validation/normalisation.
      - Each list item is emitted on its own `- value` line.
      - Output always ends with a trailing newline.

    Args:
        manifest: Validated plugin manifest.

    Returns:
        Stable canonical text for embedding.
    """
    lines = [
        f"plugin_id: {manifest.plugin_id}",
        f"name: {manifest.name}",
        f"description: {manifest.description}",
        "capabilities:",
    ]

    for value in manifest.capabilities:
        lines.append(f"- {value}")

    if manifest.entities:
        lines.append("entities:")
        for value in manifest.entities:
            lines.append(f"- {value}")

    if manifest.examples:
        lines.append("examples:")
        for value in manifest.examples:
            lines.append(f"- {value}")

    return "\n".join(lines) + "\n"


def build_canonical_route_intent_text(
    manifest: PluginManifest,
    capability: PluginRouteCapability,
    intent: PluginRouteIntent,
) -> str:
    """Build deterministic canonical text for one route intent embedding."""
    lines = [
        f"plugin_id: {manifest.plugin_id}",
        f"name: {manifest.name}",
        f"description: {manifest.description}",
        f"capability_id: {capability.capability_id}",
    ]
    if capability.description:
        lines.append(f"capability_description: {capability.description}")
    lines.append(f"intent_name: {intent.name}")
    if intent.description:
        lines.append(f"intent_description: {intent.description}")
    if manifest.entities:
        lines.append("entities:")
        for value in manifest.entities:
            lines.append(f"- {value}")
    examples = intent.examples or manifest.examples
    if examples:
        lines.append("examples:")
        for value in examples:
            lines.append(f"- {value}")
    return "\n".join(lines) + "\n"


def route_intent_key(
    plugin_id: str,
    capability_id: str,
    intent_name: str,
) -> str:
    """Return the stable route-intent key used by cache and index entries."""
    return f"{plugin_id}::{capability_id}::{intent_name}"
