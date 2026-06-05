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
PluginActionType = Literal[
    "informational_read_only",
    "external_read",
    "local_mutation",
    "external_mutation",
    "device_control",
    "privileged_system_action",
]


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
class PluginExecutionPolicy:
    """Represents action-risk metadata declared by a plugin manifest."""

    action_type: PluginActionType
    requires_confirmation: bool
    allowed_by_default: bool
    capabilities: tuple[str, ...] = ()
    entitlements: tuple[str, ...] = ()
    scaffold: bool = False
    notes: str | None = None


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
class PluginSecretKey:
    """Represents one plugin secret key declared by a manifest."""

    key: str
    required: bool
    description: str
    setup_hint: str | None = None
    rotation_supported: bool = False


@dataclass(frozen=True)
class PluginSecrets:
    """Represents plugin secret vault metadata declared by a manifest."""

    vault: str = "pat_vault"
    default_key: str = "access_token"
    allow_custom_keys: bool = False
    keys: tuple[PluginSecretKey, ...] = ()

    def key_names(self) -> tuple[str, ...]:
        """Return declared secret key names."""
        return tuple(secret.key for secret in self.keys)

    def get_key(self, key: str) -> PluginSecretKey | None:
        """Return declared metadata for one key when present."""
        for secret in self.keys:
            if secret.key == key:
                return secret
        return None


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
    execution_policy: PluginExecutionPolicy | None = None
    configuration_required: tuple[PluginConfigKey, ...] = ()
    configuration_optional: tuple[PluginConfigKey, ...] = ()
    database_required: bool = False
    database_on_missing: PluginDatabaseOnMissing = "warn_disable"
    database_schemas: tuple[PluginDatabaseSchema, ...] = ()
    secrets: PluginSecrets | None = None


@dataclass(frozen=True)
class PluginCandidate:
    """Represents a scored plugin candidate returned by vector search."""

    plugin_id: str
    score: float
