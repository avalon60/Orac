"""Data models for plugin routing manifests and candidate results."""
# Author: Clive Bostock
# Date: 2026-04-30
# Description: Defines core dataclasses used by the plugin routing subsystem.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

PluginRuntimeMode = Literal["on_demand", "service", "hybrid"]
PluginConfigValueType = Literal["string", "bool", "int", "float", "path", "list"]
PluginServiceExecutionModel = Literal["scheduled", "long_running"]
PluginServiceStartPolicy = Literal["auto", "manual"]
PluginServiceRestartPolicy = Literal["never", "on_failure"]
PluginDatabaseOnMissing = Literal["warn_disable", "warn_only", "fail_refresh"]
PluginDatabaseManagedBy = Literal["orac"]
PluginDatabaseDeploymentType = Literal["sqlplus", "liquibase"]
PluginUiStatusFormat = Literal["plugin_status_v1"]
PluginUiSurfaceTarget = Literal["apex", "react"]
PluginUiSurfaceType = Literal["admin_status", "diagnostic_panel"]
PluginUiAudience = Literal["admin", "user", "system"]
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
class PluginRouteIntent:
    """Declarative routing metadata for one plugin intent."""

    name: str
    description: str = ""
    examples: tuple[str, ...] = ()
    requires_confirmation: bool | None = None
    safety_level: str | None = None
    priority_class: str = "normal"


@dataclass(frozen=True)
class PluginRouteCapability:
    """Declarative routing metadata for one plugin capability."""

    capability_id: str
    description: str = ""
    intents: tuple[PluginRouteIntent, ...] = ()


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
class PluginDatabaseDeployment:
    """Represents plugin database deployment mechanism metadata."""

    deployment_type: PluginDatabaseDeploymentType = "sqlplus"
    controller: str | None = None


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
class PluginUiStatusProvider:
    """Represents a plugin-owned operational status provider declaration."""

    provider_id: str
    description: str = ""
    format: PluginUiStatusFormat = "plugin_status_v1"
    redaction_required: bool = True


@dataclass(frozen=True)
class PluginApexSurfaceMetadata:
    """Represents optional APEX metadata for a plugin UI surface."""

    app_alias: str | None = None
    app_export: str | None = None
    entry_page_id: int | None = None
    install_required: bool = False


@dataclass(frozen=True)
class PluginReactSurfaceMetadata:
    """Represents optional React metadata for a plugin UI surface."""

    component: str | None = None
    status_endpoint: str | None = None
    install_required: bool = False


@dataclass(frozen=True)
class PluginUiSurface:
    """Represents one plugin-declared operational UI surface."""

    surface_id: str
    surface_type: PluginUiSurfaceType
    label: str
    target: PluginUiSurfaceTarget
    audience: PluginUiAudience
    enabled: bool
    description: str = ""
    required_roles: tuple[str, ...] = ()
    apex: PluginApexSurfaceMetadata | None = None
    react: PluginReactSurfaceMetadata | None = None


@dataclass(frozen=True)
class PluginUi:
    """Represents optional plugin UI/status metadata."""

    status_provider: PluginUiStatusProvider | None = None
    surfaces: tuple[PluginUiSurface, ...] = ()


@dataclass(frozen=True)
class PluginApexApp:
    """Represents one plugin-supplied APEX application export declaration."""

    app_alias: str
    label: str
    app_export: str
    description: str = ""
    workspace: str = "ORAC"
    parsing_schema: str = "ORAC_APX_PUB"
    application_id: int | None = None
    entry_page_id: int = 1
    install_required: bool = False
    replace_existing: bool = False
    required_roles: tuple[str, ...] = ()
    icon: str | None = None
    card_title: str | None = None
    card_subtitle: str | None = None
    enabled: bool = True

    @property
    def alias(self) -> str:
        """Return the stable APEX application alias."""
        return self.app_alias


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
    route_capabilities: tuple[PluginRouteCapability, ...] = ()
    configuration_required: tuple[PluginConfigKey, ...] = ()
    configuration_optional: tuple[PluginConfigKey, ...] = ()
    database_required: bool = False
    database_on_missing: PluginDatabaseOnMissing = "warn_disable"
    database_deployment: PluginDatabaseDeployment = PluginDatabaseDeployment()
    database_schemas: tuple[PluginDatabaseSchema, ...] = ()
    secrets: PluginSecrets | None = None
    ui: PluginUi | None = None
    apex_apps: tuple[PluginApexApp, ...] = ()
    python_dependencies: tuple[str, ...] = ()
    config_path: Path | None = None


@dataclass(frozen=True)
class PluginCandidate:
    """Represents a scored plugin candidate returned by vector search."""

    plugin_id: str
    score: float
    route_key: str = ""
    capability_id: str = ""
    intent_name: str = ""


@dataclass(frozen=True)
class PluginRouteCandidate:
    """Represents one enriched plugin route candidate for arbitration."""

    plugin_id: str
    capability_id: str
    intent_name: str
    confidence: float
    match_reasons: tuple[str, ...] = ()
    extracted_params: dict[str, Any] | None = None
    missing_params: tuple[str, ...] = ()
    requires_confirmation: bool = False
    safety_level: str = "informational_read_only"
    priority_class: str = "normal"
    route_key: str = ""


@dataclass(frozen=True)
class ArbitrationDecision:
    """Core-owned decision for a plugin routing arbitration attempt."""

    decision_type: Literal[
        "execute_plugin",
        "clarify",
        "confirm",
        "llm_fallback",
        "core_command",
        "reject",
    ]
    selected_plugin_id: str | None
    selected_capability_id: str | None
    selected_intent_name: str | None
    candidates: tuple[PluginRouteCandidate, ...]
    reason: str
    clarification_prompt: str | None = None
    utterance: str = ""
