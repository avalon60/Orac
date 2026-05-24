"""Data models for plugin routing manifests and candidate results."""
# Author: Clive Bostock
# Date: 2026-04-30
# Description: Defines core dataclasses used by the plugin routing subsystem.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

PluginRuntimeMode = Literal["on_demand", "service", "hybrid"]
PluginConfigValueType = Literal["string", "bool", "int", "float", "path", "list"]
PluginServiceExecutionModel = Literal["scheduled", "long_running"]
PluginServiceStartPolicy = Literal["auto", "manual"]
PluginServiceRestartPolicy = Literal["never", "on_failure"]
PluginDatabaseOnMissing = Literal["warn_disable", "warn_only", "fail_refresh"]
PluginDatabaseManagedBy = Literal["orac"]


@dataclass(frozen=True)
class PluginConfigKey:
    """Represents a plugin configuration key declared by a manifest."""

    section: str
    key: str
    value_type: PluginConfigValueType
    description: str


@dataclass(frozen=True)
class PluginHealthCheck:
    """Represents service health-check metadata declared by a manifest."""

    enabled: bool = False
    method: str | None = None
    interval_seconds: int | None = None
    timeout_seconds: int | None = None
    failure_threshold: int | None = None


@dataclass(frozen=True)
class PluginServiceSchedule:
    """Represents Orac-owned schedule metadata for a service plugin."""

    interval_seconds: int
    run_on_start: bool = False
    jitter_seconds: int | None = None
    timeout_seconds: int | None = None


@dataclass(frozen=True)
class PluginServiceRuntime:
    """Represents background service metadata declared by a manifest."""

    entry_point: str
    execution_model: PluginServiceExecutionModel
    start_policy: PluginServiceStartPolicy
    restart_policy: PluginServiceRestartPolicy
    shutdown_timeout_seconds: int
    health_check: PluginHealthCheck
    schedule: PluginServiceSchedule | None = None


@dataclass(frozen=True)
class PluginDatabaseVersionCheck:
    """Represents plugin database version-check metadata."""

    enabled: bool


@dataclass(frozen=True)
class PluginDatabaseBackup:
    """Represents plugin database backup/export metadata."""

    include: bool
    export_mode: str | None = None


@dataclass(frozen=True)
class PluginDatabaseSchema:
    """Represents a plugin-owned database schema declaration."""

    schema_name: str
    purpose: str
    managed_by: PluginDatabaseManagedBy
    minimum_version: str
    version_check: PluginDatabaseVersionCheck
    backup: PluginDatabaseBackup | None = None


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
    entitlements: tuple[str, ...]
    entities: tuple[str, ...]
    examples: tuple[str, ...]
    entry_point: str | None
    manifest_path: Path
    plugin_dir: Path
    manifest_hash: str
    runtime_mode: PluginRuntimeMode = "on_demand"
    service_runtime: PluginServiceRuntime | None = None
    configuration_required: tuple[PluginConfigKey, ...] = ()
    configuration_optional: tuple[PluginConfigKey, ...] = ()
    database_required: bool = False
    database_on_missing: PluginDatabaseOnMissing = "warn_disable"
    database_schemas: tuple[PluginDatabaseSchema, ...] = ()


@dataclass(frozen=True)
class PluginCandidate:
    """Represents a scored plugin candidate returned by vector search."""

    plugin_id: str
    score: float
