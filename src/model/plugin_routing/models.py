"""Data models for plugin routing manifests and candidate results."""
# Author: Clive Bostock
# Date: 2026-04-23
# Description: Defines core dataclasses used by the plugin routing subsystem.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PluginManifest:
    """Represents a validated plugin manifest and its discovery metadata."""

    schema_version: int
    plugin_id: str
    name: str
    description: str
    version: str
    enabled: bool
    capabilities: tuple[str, ...]
    entities: tuple[str, ...]
    examples: tuple[str, ...]
    entry_point: str | None
    manifest_path: Path
    plugin_dir: Path
    manifest_hash: str


@dataclass(frozen=True)
class PluginCandidate:
    """Represents a scored plugin candidate returned by vector search."""

    plugin_id: str
    score: float
