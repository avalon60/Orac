"""Deterministic canonical intent text generation for plugin manifests."""
# Author: Clive Bostock
# Date: 2026-04-23
# Description: Builds stable canonical intent text used for plugin routing embeddings.

from __future__ import annotations

from model.plugin_routing.models import PluginManifest

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
