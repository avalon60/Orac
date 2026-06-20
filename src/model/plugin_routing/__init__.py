"""Plugin routing subsystem for manifest-driven discovery and candidate search."""
# Author: Clive Bostock
# Date: 2026-04-23
# Description: Exposes the plugin routing facade, models, and embedding interfaces.

from model.plugin_routing.embeddings import EmbeddingProvider, HashEmbeddingProvider
from model.plugin_routing.handoff import PluginRoutingHandoff, render_plugin_routing_hints
from model.plugin_routing.manager import PluginManager
from model.plugin_routing.models import (
    PluginCandidate,
    PluginConfigKey,
    PluginDatabaseBackup,
    PluginDatabaseSchema,
    PluginDatabaseVersionCheck,
    PluginRouteCandidate,
    PluginRouteCapability,
    PluginRouteIntent,
    ArbitrationDecision,
    PluginHealthCheck,
    PluginManifest,
    PluginServiceSchedule,
    PluginServiceRuntime,
)

__all__ = [
    "EmbeddingProvider",
    "HashEmbeddingProvider",
    "PluginCandidate",
    "PluginConfigKey",
    "PluginDatabaseBackup",
    "PluginDatabaseSchema",
    "PluginDatabaseVersionCheck",
    "PluginHealthCheck",
    "PluginManager",
    "PluginManifest",
    "PluginRouteCandidate",
    "PluginRouteCapability",
    "PluginRouteIntent",
    "PluginRoutingHandoff",
    "PluginServiceSchedule",
    "PluginServiceRuntime",
    "render_plugin_routing_hints",
    "ArbitrationDecision",
]
