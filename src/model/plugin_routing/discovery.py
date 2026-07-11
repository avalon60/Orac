"""Manifest discovery and validation for plugin routing."""
# Author: Clive Bostock
# Date: 2026-04-30
# Description: Scans manifest files, validates schema v2, and constructs manifest models.

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

from model.plugin_routing.models import (
    PluginConfigKey,
    PluginApexApp,
    PluginApexSurfaceMetadata,
    PluginDatabaseBackup,
    PluginDatabaseDeployment,
    PluginDatabaseSchema,
    PluginDatabaseVersionCheck,
    PluginExecutionPolicy,
    PluginHealthCheck,
    PluginManifest,
    PluginRouteCapability,
    PluginRouteIntent,
    PluginReactSurfaceMetadata,
    PluginSecretKey,
    PluginSecrets,
    PluginServiceSchedule,
    PluginServiceRuntime,
    PluginUi,
    PluginUiStatusProvider,
    PluginUiSurface,
)
from model.plugin_database_deployment import PROTECTED_ORAC_SCHEMAS
from model.plugin_dependencies import PluginDependencyError
from model.plugin_dependencies import normalise_requirements

PLUGIN_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
DATABASE_SCHEMA_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$", re.IGNORECASE)
SECRET_KEY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
APEX_ALIAS_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
ICON_TOKEN_PATTERN = re.compile(r"^fa-[a-z0-9][a-z0-9-]*$")
ICON_CLASS_PATTERN = re.compile(r"^fa fa-[a-z0-9][a-z0-9-]*$")
MANIFEST_SCHEMA_VERSION = 2
RUNTIME_MODES = {"on_demand", "service", "hybrid"}
CONFIG_VALUE_TYPES = {"string", "bool", "int", "float", "path", "list"}
SERVICE_EXECUTION_MODELS = {"scheduled", "long_running"}
SERVICE_START_POLICIES = {"disabled", "auto", "manual"}
SERVICE_RESTART_POLICIES = {"never", "on_failure"}
DATABASE_ON_MISSING_POLICIES = {"warn_disable", "warn_only", "fail_refresh"}
DATABASE_MANAGERS = {"orac"}
DATABASE_DEPLOYMENT_TYPES = {"sqlplus", "liquibase"}
PLUGIN_UI_STATUS_FORMATS = {"plugin_status_v1"}
PLUGIN_UI_SURFACE_TARGETS = {"apex", "react"}
PLUGIN_UI_SURFACE_TYPES = {"admin_status", "diagnostic_panel"}
PLUGIN_UI_AUDIENCES = {"admin", "user", "system"}
SUPPORTED_APEX_WORKSPACES = {"ORAC"}
PLUGIN_UI_ACCENT_CLASSES = {
    "u-color-1",
    "u-color-2",
    "u-color-3",
    "u-color-4",
    "u-color-5",
    "u-color-6",
    "u-color-7",
    "u-color-8",
    "u-color-9",
    "u-color-10",
    "u-color-11",
    "u-color-12",
    "u-color-13",
    "u-color-14",
    "u-color-15",
}
PLUGIN_ACTION_TYPES = {
    "informational_read_only",
    "external_read",
    "local_mutation",
    "external_mutation",
    "device_control",
    "privileged_system_action",
}
MAX_SERVICE_SECONDS = 86400
MAX_HEALTH_FAILURE_THRESHOLD = 100
REQUIRED_FIELDS = {
    "schema_version",
    "plugin_id",
    "name",
    "description",
    "version",
    "enabled",
    "capabilities",
    "entitlements",
    "runtime",
}
OPTIONAL_FIELDS = {
    "entities",
    "examples",
    "entry_point",
    "execution",
    "routing",
    "configuration",
    "database",
    "secrets",
    "ui",
    "apex_apps",
    "python_dependencies",
}
ALLOWED_FIELDS = REQUIRED_FIELDS | OPTIONAL_FIELDS


class PluginManifestError(ValueError):
    """Raised when a plugin manifest fails validation."""


class PluginDiscovery:
    """Discovers and validates plugin manifests from the filesystem."""

    def __init__(self, plugins_dir: Path):
        self._plugins_dir = Path(plugins_dir)

    def discover(self) -> tuple[list[PluginManifest], list[str]]:
        """Discovers valid manifests and accumulates validation errors."""
        manifests: list[PluginManifest] = []
        errors: list[str] = []

        if not self._plugins_dir.exists():
            return manifests, [f"Plugin directory does not exist: {self._plugins_dir}"]

        for manifest_path in sorted(self._plugins_dir.glob("*.json")):
            try:
                manifests.append(self._load_manifest(manifest_path))
            except PluginManifestError as exc:
                errors.append(f"{manifest_path}: {exc}")

        return manifests, errors

    def load_manifest(
        self,
        manifest_path: Path,
        *,
        plugin_dir: Path | None = None,
        enforce_filename: bool = True,
    ) -> PluginManifest:
        """Load one manifest, optionally using a packaged plugin directory.

        Args:
            manifest_path: JSON manifest to validate.
            plugin_dir: Explicit implementation directory for package installs.
            enforce_filename: Whether the filename stem must match ``plugin_id``.

        Returns:
            A validated plugin manifest.
        """
        return self._load_manifest(
            Path(manifest_path),
            plugin_dir=plugin_dir,
            enforce_filename=enforce_filename,
        )

    def _load_manifest(
        self,
        manifest_path: Path,
        *,
        plugin_dir: Path | None = None,
        enforce_filename: bool = True,
    ) -> PluginManifest:
        try:
            manifest_text = manifest_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise PluginManifestError(f"Unable to read manifest: {exc}") from exc

        try:
            data = json.loads(manifest_text)
        except json.JSONDecodeError as exc:
            raise PluginManifestError(f"Invalid JSON: {exc.msg}") from exc

        if not isinstance(data, dict):
            raise PluginManifestError("Manifest root must be a JSON object")

        unknown_fields = sorted(set(data.keys()) - ALLOWED_FIELDS)
        if unknown_fields:
            raise PluginManifestError(f"Unknown field(s): {', '.join(unknown_fields)}")

        missing_fields = sorted(REQUIRED_FIELDS - set(data.keys()))
        if missing_fields:
            raise PluginManifestError(f"Missing required field(s): {', '.join(missing_fields)}")

        schema_version = data["schema_version"]
        if schema_version != MANIFEST_SCHEMA_VERSION:
            raise PluginManifestError(
                f"schema_version must be integer {MANIFEST_SCHEMA_VERSION}"
            )

        plugin_id = self._require_non_empty_string(data["plugin_id"], "plugin_id")
        if not PLUGIN_ID_PATTERN.fullmatch(plugin_id):
            raise PluginManifestError(
                "plugin_id must match ^[a-z][a-z0-9_]*$"
            )

        manifest_stem = manifest_path.stem
        if enforce_filename and plugin_id != manifest_stem:
            raise PluginManifestError(
                f"plugin_id '{plugin_id}' must exactly match manifest filename stem '{manifest_stem}'"
            )

        plugin_dir = Path(plugin_dir) if plugin_dir else self._plugins_dir / plugin_id
        if not plugin_dir.exists() or not plugin_dir.is_dir():
            raise PluginManifestError(
                f"Matching plugin directory is required: {plugin_dir}"
            )
        if enforce_filename and plugin_dir.name != plugin_id:
            raise PluginManifestError(
                f"Plugin directory name '{plugin_dir.name}' must exactly match plugin_id '{plugin_id}'"
            )

        name = self._require_non_empty_string(data["name"], "name")
        description = self._require_non_empty_string(data["description"], "description")
        version = self._require_non_empty_string(data["version"], "version")
        enabled = self._require_bool(data["enabled"], "enabled")
        capabilities = self._require_string_list(
            data["capabilities"],
            "capabilities",
            allow_empty=False,
        )
        entitlements = self._require_string_list(
            data["entitlements"],
            "entitlements",
        )
        entities = self._require_string_list(data.get("entities", []), "entities")
        examples = self._require_string_list(data.get("examples", []), "examples")
        entry_point = self._require_optional_string(data.get("entry_point"), "entry_point")
        runtime_mode, service_runtimes = self._load_runtime(data["runtime"])
        service_runtime = service_runtimes[0] if service_runtimes else None
        execution_policy = self._load_execution_policy(
            data.get("execution"),
            capabilities=capabilities,
            entitlements=entitlements,
        )
        route_capabilities = self._load_routing(
            data.get("routing"),
            capabilities=capabilities,
            examples=examples,
            execution_policy=execution_policy,
        )
        configuration_required, configuration_optional = self._load_configuration(
            data.get("configuration", {})
        )
        (
            database_required,
            database_on_missing,
            database_deployment,
            database_schemas,
        ) = self._load_database(data.get("database", {}))
        secrets = self._load_secrets(data.get("secrets"))
        ui = self._load_ui(data.get("ui"))
        apex_apps = self._load_apex_apps(data.get("apex_apps"))
        try:
            python_dependencies = normalise_requirements(
                data.get("python_dependencies", [])
            )
        except PluginDependencyError as exc:
            raise PluginManifestError(f"python_dependencies: {exc}") from exc

        manifest_hash = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()

        return PluginManifest(
            schema_version=schema_version,
            plugin_id=plugin_id,
            name=name,
            description=description,
            version=version,
            enabled=enabled,
            capabilities=tuple(capabilities),
            entitlements=tuple(entitlements),
            entities=tuple(entities),
            examples=tuple(examples),
            entry_point=entry_point,
            manifest_path=manifest_path,
            plugin_dir=plugin_dir,
            manifest_hash=manifest_hash,
            runtime_mode=runtime_mode,
            service_runtime=service_runtime,
            service_runtimes=service_runtimes,
            execution_policy=execution_policy,
            route_capabilities=tuple(route_capabilities),
            configuration_required=tuple(configuration_required),
            configuration_optional=tuple(configuration_optional),
            database_required=database_required,
            database_on_missing=database_on_missing,
            database_deployment=database_deployment,
            database_schemas=tuple(database_schemas),
            secrets=secrets,
            ui=ui,
            apex_apps=tuple(apex_apps),
            python_dependencies=python_dependencies,
        )

    def _load_routing(
        self,
        value: Any,
        *,
        capabilities: list[str],
        examples: list[str],
        execution_policy: PluginExecutionPolicy,
    ) -> list[PluginRouteCapability]:
        """Load declarative route metadata without importing plugin code."""
        if value is None:
            return [
                PluginRouteCapability(
                    capability_id=capability,
                    description=capability.replace("_", " ").replace(".", " "),
                    intents=(
                        PluginRouteIntent(
                            name=capability.rsplit(".", 1)[-1],
                            examples=tuple(examples),
                            requires_confirmation=execution_policy.requires_confirmation,
                            safety_level=execution_policy.action_type,
                        ),
                    ),
                )
                for capability in capabilities
            ]
        if not isinstance(value, dict):
            raise PluginManifestError("routing must be an object")

        self._reject_unknown_fields(value, {"capabilities"}, "routing")
        route_values = value.get("capabilities", [])
        if not isinstance(route_values, list):
            raise PluginManifestError("routing.capabilities must be a list")

        route_capabilities: list[PluginRouteCapability] = []
        for index, capability_value in enumerate(route_values):
            field = f"routing.capabilities[{index}]"
            if not isinstance(capability_value, dict):
                raise PluginManifestError(f"{field} must be an object")
            self._reject_unknown_fields(
                capability_value,
                {"id", "description", "intents"},
                field,
            )
            capability_id = self._require_non_empty_string(
                capability_value.get("id"),
                f"{field}.id",
            )
            if capability_id not in capabilities:
                raise PluginManifestError(
                    f"{field}.id '{capability_id}' must be declared in capabilities"
                )
            intents_value = capability_value.get("intents", [])
            if not isinstance(intents_value, list) or not intents_value:
                raise PluginManifestError(f"{field}.intents must be a non-empty list")
            intents: list[PluginRouteIntent] = []
            for intent_index, intent_value in enumerate(intents_value):
                intent_field = f"{field}.intents[{intent_index}]"
                if not isinstance(intent_value, dict):
                    raise PluginManifestError(f"{intent_field} must be an object")
                self._reject_unknown_fields(
                    intent_value,
                    {
                        "name",
                        "description",
                        "examples",
                        "requires_confirmation",
                        "safety_level",
                        "priority_class",
                    },
                    intent_field,
                )
                intents.append(
                    PluginRouteIntent(
                        name=self._require_non_empty_string(
                            intent_value.get("name"),
                            f"{intent_field}.name",
                        ),
                        description=self._require_optional_string(
                            intent_value.get("description"),
                            f"{intent_field}.description",
                        )
                        or "",
                        examples=tuple(
                            self._require_string_list(
                                intent_value.get("examples", []),
                                f"{intent_field}.examples",
                            )
                        ),
                        requires_confirmation=(
                            self._require_bool(
                                intent_value.get("requires_confirmation"),
                                f"{intent_field}.requires_confirmation",
                            )
                            if "requires_confirmation" in intent_value
                            else execution_policy.requires_confirmation
                        ),
                        safety_level=(
                            self._require_optional_string(
                                intent_value.get("safety_level"),
                                f"{intent_field}.safety_level",
                            )
                            or execution_policy.action_type
                        ),
                        priority_class=(
                            self._require_optional_string(
                                intent_value.get("priority_class"),
                                f"{intent_field}.priority_class",
                            )
                            or "normal"
                        ),
                    )
                )
            route_capabilities.append(
                PluginRouteCapability(
                    capability_id=capability_id,
                    description=self._require_optional_string(
                        capability_value.get("description"),
                        f"{field}.description",
                    )
                    or "",
                    intents=tuple(intents),
                )
            )
        return route_capabilities

    def _load_runtime(self, value: Any) -> tuple[str, tuple[PluginServiceRuntime, ...]]:
        if not isinstance(value, dict):
            raise PluginManifestError("runtime must be an object")

        unknown_fields = sorted(set(value.keys()) - {"mode", "service", "services"})
        if unknown_fields:
            raise PluginManifestError(
                f"runtime has unknown field(s): {', '.join(unknown_fields)}"
            )

        mode = self._require_enum(value.get("mode"), "runtime.mode", RUNTIME_MODES)
        service_value = value.get("service")
        services_value = value.get("services")
        if service_value is not None and services_value is not None:
            raise PluginManifestError("runtime.service and runtime.services are mutually exclusive")
        if mode in {"service", "hybrid"}:
            if service_value is None and services_value is None:
                raise PluginManifestError(
                    "runtime.service or runtime.services is required when runtime.mode is service or hybrid"
                )
            if services_value is not None:
                if not isinstance(services_value, list) or not services_value:
                    raise PluginManifestError("runtime.services must be a non-empty array")
                service_runtimes = tuple(
                    self._load_service_runtime(item, default_service_code=None)
                    for item in services_value
                )
                service_codes = [runtime.service_code for runtime in service_runtimes]
                if len(service_codes) != len(set(service_codes)):
                    raise PluginManifestError("runtime.services service_code values must be unique")
            else:
                service_runtimes = (
                    self._load_service_runtime(
                        service_value,
                        default_service_code="default",
                    ),
                )
        elif service_value is not None or services_value is not None:
            raise PluginManifestError(
                "runtime service metadata is only allowed when runtime.mode is service or hybrid"
            )
        else:
            service_runtimes = ()

        return mode, service_runtimes

    def _load_execution_policy(
        self,
        value: Any,
        *,
        capabilities: list[str],
        entitlements: list[str],
    ) -> PluginExecutionPolicy:
        """Load first-pass plugin action policy metadata."""
        if value is None:
            return self._default_execution_policy(
                capabilities=capabilities,
                entitlements=entitlements,
            )
        if not isinstance(value, dict):
            raise PluginManifestError("execution must be an object")

        required_fields = {"action_type", "requires_confirmation", "allowed_by_default"}
        optional_fields = {"capabilities", "entitlements", "scaffold", "notes"}
        self._reject_unknown_fields(value, required_fields | optional_fields, "execution")
        self._require_fields(value, required_fields, "execution")

        policy_capabilities = tuple(
            self._require_string_list(
                value.get("capabilities", capabilities),
                "execution.capabilities",
            )
        )
        policy_entitlements = tuple(
            self._require_string_list(
                value.get("entitlements", entitlements),
                "execution.entitlements",
            )
        )
        self._require_subset(policy_capabilities, capabilities, "execution.capabilities", "capabilities")
        self._require_subset(policy_entitlements, entitlements, "execution.entitlements", "entitlements")

        return PluginExecutionPolicy(
            action_type=self._require_enum(
                value["action_type"],
                "execution.action_type",
                PLUGIN_ACTION_TYPES,
            ),
            requires_confirmation=self._require_bool(
                value["requires_confirmation"],
                "execution.requires_confirmation",
            ),
            allowed_by_default=self._require_bool(
                value["allowed_by_default"],
                "execution.allowed_by_default",
            ),
            capabilities=policy_capabilities,
            entitlements=policy_entitlements,
            scaffold=self._require_bool(value.get("scaffold", False), "execution.scaffold"),
            notes=self._require_optional_string(value.get("notes"), "execution.notes"),
        )

    def _default_execution_policy(
        self,
        *,
        capabilities: list[str],
        entitlements: list[str],
    ) -> PluginExecutionPolicy:
        """Infer a conservative policy for older manifests without execution metadata."""
        risky_terms = (
            "control",
            "activate",
            "activation",
            "write",
            "sync",
            "backup",
            "delete",
            "mutation",
            "filesystem",
            "shell",
            "system",
            "token",
        )
        action_text = " ".join([*capabilities, *entitlements]).lower()
        if any(term in action_text for term in risky_terms):
            return PluginExecutionPolicy(
                action_type="privileged_system_action",
                requires_confirmation=True,
                allowed_by_default=False,
                capabilities=tuple(capabilities),
                entitlements=tuple(entitlements),
                notes="Inferred fail-safe policy for manifest without explicit execution metadata.",
            )
        return PluginExecutionPolicy(
            action_type="informational_read_only",
            requires_confirmation=False,
            allowed_by_default=True,
            capabilities=tuple(capabilities),
            entitlements=tuple(entitlements),
        )

    def _load_service_runtime(
        self,
        value: Any,
        *,
        default_service_code: str | None,
    ) -> PluginServiceRuntime:
        if not isinstance(value, dict):
            raise PluginManifestError("runtime.service must be an object")

        required_fields = {
            "entry_point",
            "execution_model",
            "start_policy",
            "restart_policy",
            "shutdown_timeout_seconds",
        }
        if default_service_code is None:
            required_fields.add("service_code")
        optional_fields = {"health_check", "schedule"}
        if default_service_code is not None:
            optional_fields.add("service_code")
        self._reject_unknown_fields(value, required_fields | optional_fields, "runtime.service")
        self._require_fields(value, required_fields, "runtime.service")

        service_code = self._require_non_empty_string(
            value.get("service_code", default_service_code),
            "runtime.service.service_code",
        )
        if not PLUGIN_ID_PATTERN.fullmatch(service_code):
            raise PluginManifestError("runtime.service.service_code must match ^[a-z][a-z0-9_]*$")

        execution_model = self._require_enum(
            value["execution_model"],
            "runtime.service.execution_model",
            SERVICE_EXECUTION_MODELS,
        )
        schedule = self._load_service_schedule(
            value.get("schedule"),
            execution_model=execution_model,
        )
        health_check = self._load_health_check(value.get("health_check", {"enabled": False}))
        return PluginServiceRuntime(
            entry_point=self._require_non_empty_string(
                value["entry_point"],
                "runtime.service.entry_point",
            ),
            execution_model=execution_model,
            start_policy=self._require_enum(
                value["start_policy"],
                "runtime.service.start_policy",
                SERVICE_START_POLICIES,
            ),
            restart_policy=self._require_enum(
                value["restart_policy"],
                "runtime.service.restart_policy",
                SERVICE_RESTART_POLICIES,
            ),
            shutdown_timeout_seconds=self._require_bounded_positive_int(
                value["shutdown_timeout_seconds"],
                "runtime.service.shutdown_timeout_seconds",
                max_value=MAX_SERVICE_SECONDS,
            ),
            health_check=health_check,
            service_code=service_code,
            schedule=schedule,
        )

    def _load_service_schedule(
        self,
        value: Any,
        *,
        execution_model: str,
    ) -> PluginServiceSchedule | None:
        if execution_model == "long_running":
            if value is not None:
                raise PluginManifestError(
                    "runtime.service.schedule is only allowed when execution_model is scheduled"
                )
            return None

        if value is None:
            raise PluginManifestError(
                "runtime.service.schedule is required when execution_model is scheduled"
            )
        if not isinstance(value, dict):
            raise PluginManifestError("runtime.service.schedule must be an object")

        required_fields = {"interval_seconds"}
        optional_fields = {"run_on_start", "jitter_seconds", "timeout_seconds"}
        self._reject_unknown_fields(value, required_fields | optional_fields, "runtime.service.schedule")
        self._require_fields(value, required_fields, "runtime.service.schedule")

        interval_seconds = self._require_bounded_positive_int(
            value["interval_seconds"],
            "runtime.service.schedule.interval_seconds",
            max_value=MAX_SERVICE_SECONDS,
        )
        jitter_seconds = self._require_non_negative_int(
            value.get("jitter_seconds"),
            "runtime.service.schedule.jitter_seconds",
        )
        if jitter_seconds is not None and jitter_seconds >= interval_seconds:
            raise PluginManifestError(
                "runtime.service.schedule.jitter_seconds must be less than "
                "runtime.service.schedule.interval_seconds"
            )

        timeout_seconds = None
        if value.get("timeout_seconds") is not None:
            timeout_seconds = self._require_bounded_positive_int(
                value["timeout_seconds"],
                "runtime.service.schedule.timeout_seconds",
                max_value=MAX_SERVICE_SECONDS,
            )

        return PluginServiceSchedule(
            interval_seconds=interval_seconds,
            run_on_start=self._require_bool(
                value.get("run_on_start", False),
                "runtime.service.schedule.run_on_start",
            ),
            jitter_seconds=jitter_seconds,
            timeout_seconds=timeout_seconds,
        )

    def _load_health_check(self, value: Any) -> PluginHealthCheck:
        if not isinstance(value, dict):
            raise PluginManifestError("runtime.service.health_check must be an object")

        allowed_fields = {
            "enabled",
            "method",
            "interval_seconds",
            "timeout_seconds",
            "failure_threshold",
        }
        self._reject_unknown_fields(value, allowed_fields, "runtime.service.health_check")
        enabled = self._require_bool(value.get("enabled", False), "runtime.service.health_check.enabled")

        if not enabled:
            return PluginHealthCheck(enabled=False)

        required_fields = {
            "method",
            "interval_seconds",
            "timeout_seconds",
            "failure_threshold",
        }
        self._require_fields(value, required_fields, "runtime.service.health_check")
        return PluginHealthCheck(
            enabled=True,
            method=self._require_non_empty_string(
                value["method"],
                "runtime.service.health_check.method",
            ),
            interval_seconds=self._require_bounded_positive_int(
                value["interval_seconds"],
                "runtime.service.health_check.interval_seconds",
                max_value=MAX_SERVICE_SECONDS,
            ),
            timeout_seconds=self._require_bounded_positive_int(
                value["timeout_seconds"],
                "runtime.service.health_check.timeout_seconds",
                max_value=MAX_SERVICE_SECONDS,
            ),
            failure_threshold=self._require_bounded_positive_int(
                value["failure_threshold"],
                "runtime.service.health_check.failure_threshold",
                max_value=MAX_HEALTH_FAILURE_THRESHOLD,
            ),
        )

    def _load_configuration(
        self,
        value: Any,
    ) -> tuple[list[PluginConfigKey], list[PluginConfigKey]]:
        if not isinstance(value, dict):
            raise PluginManifestError("configuration must be an object")

        allowed_fields = {"required", "optional"}
        self._reject_unknown_fields(value, allowed_fields, "configuration")
        return (
            self._load_config_keys(value.get("required", []), "configuration.required"),
            self._load_config_keys(value.get("optional", []), "configuration.optional"),
        )

    def _load_config_keys(self, value: Any, field_name: str) -> list[PluginConfigKey]:
        if not isinstance(value, list):
            raise PluginManifestError(f"{field_name} must be a list")

        result: list[PluginConfigKey] = []
        for index, item in enumerate(value):
            item_name = f"{field_name}[{index}]"
            if not isinstance(item, dict):
                raise PluginManifestError(f"{item_name} must be an object")
            required_fields = {"section", "key", "type", "description"}
            self._reject_unknown_fields(item, required_fields, item_name)
            self._require_fields(item, required_fields, item_name)
            result.append(
                PluginConfigKey(
                    section=self._require_non_empty_string(item["section"], f"{item_name}.section"),
                    key=self._require_non_empty_string(item["key"], f"{item_name}.key"),
                    value_type=self._require_enum(
                        item["type"],
                        f"{item_name}.type",
                        CONFIG_VALUE_TYPES,
                    ),
                    description=self._require_non_empty_string(
                        item["description"],
                        f"{item_name}.description",
                    ),
                )
            )
        return result

    def _load_database(
        self,
        value: Any,
    ) -> tuple[bool, str, PluginDatabaseDeployment, list[PluginDatabaseSchema]]:
        if not isinstance(value, dict):
            raise PluginManifestError("database must be an object")

        allowed_fields = {"required", "on_missing", "deployment", "schemas"}
        self._reject_unknown_fields(value, allowed_fields, "database")

        required = self._require_bool(value.get("required", False), "database.required")
        on_missing = self._require_enum(
            value.get("on_missing", "warn_disable"),
            "database.on_missing",
            DATABASE_ON_MISSING_POLICIES,
        )
        deployment = self._load_database_deployment(value.get("deployment", {}))
        schemas = self._load_database_schemas(value.get("schemas", []))

        if required and not schemas:
            raise PluginManifestError("database.schemas must contain at least one value when database.required is true")

        return required, on_missing, deployment, schemas

    def _load_database_deployment(self, value: Any) -> PluginDatabaseDeployment:
        """Load optional plugin database deployment mechanism metadata."""
        if not isinstance(value, dict):
            raise PluginManifestError("database.deployment must be an object")
        self._reject_unknown_fields(value, {"type", "controller"}, "database.deployment")
        deployment_type = self._require_enum(
            value.get("type", "sqlplus"),
            "database.deployment.type",
            DATABASE_DEPLOYMENT_TYPES,
        )
        controller = self._require_optional_relative_path(
            value.get("controller"),
            "database.deployment.controller",
        )
        if deployment_type == "liquibase" and controller is None:
            controller = "db/liquibase/pluginController.xml"
        return PluginDatabaseDeployment(
            deployment_type=deployment_type,
            controller=controller,
        )

    def _load_secrets(self, value: Any) -> PluginSecrets | None:
        """Load plugin secret vault metadata."""
        if value is None:
            return None
        if not isinstance(value, dict):
            raise PluginManifestError("secrets must be an object")

        required_fields = {"vault", "default_key", "allow_custom_keys", "keys"}
        self._reject_unknown_fields(value, required_fields, "secrets")
        self._require_fields(value, required_fields, "secrets")

        vault = self._require_enum(value["vault"], "secrets.vault", {"pat_vault"})
        default_key = self._require_secret_key(value["default_key"], "secrets.default_key")
        allow_custom_keys = self._require_bool(
            value["allow_custom_keys"],
            "secrets.allow_custom_keys",
        )
        keys = self._load_secret_keys(value["keys"])
        key_names = {secret.key for secret in keys}
        if default_key not in key_names and not allow_custom_keys:
            raise PluginManifestError(
                "secrets.default_key must be declared in secrets.keys when "
                "secrets.allow_custom_keys is false"
            )

        return PluginSecrets(
            vault=vault,
            default_key=default_key,
            allow_custom_keys=allow_custom_keys,
            keys=tuple(keys),
        )

    def _load_secret_keys(self, value: Any) -> list[PluginSecretKey]:
        """Load the declared plugin secret keys."""
        if not isinstance(value, dict):
            raise PluginManifestError("secrets.keys must be an object")

        result: list[PluginSecretKey] = []
        for raw_key, metadata in sorted(value.items()):
            key_name = self._require_secret_key(raw_key, f"secrets.keys.{raw_key}")
            if not isinstance(metadata, dict):
                raise PluginManifestError(f"secrets.keys.{key_name} must be an object")
            required_fields = {"required", "description", "setup_hint", "rotation_supported"}
            self._reject_unknown_fields(metadata, required_fields, f"secrets.keys.{key_name}")
            self._require_fields(metadata, {"required", "description"}, f"secrets.keys.{key_name}")
            result.append(
                PluginSecretKey(
                    key=key_name,
                    required=self._require_bool(
                        metadata["required"],
                        f"secrets.keys.{key_name}.required",
                    ),
                    description=self._require_non_empty_string(
                        metadata["description"],
                        f"secrets.keys.{key_name}.description",
                    ),
                    setup_hint=self._require_optional_string(
                        metadata.get("setup_hint"),
                        f"secrets.keys.{key_name}.setup_hint",
                    ),
                    rotation_supported=self._require_bool(
                        metadata.get("rotation_supported", False),
                        f"secrets.keys.{key_name}.rotation_supported",
                    ),
                )
            )
        return result

    def _load_database_schemas(self, value: Any) -> list[PluginDatabaseSchema]:
        if not isinstance(value, list):
            raise PluginManifestError("database.schemas must be a list")

        result: list[PluginDatabaseSchema] = []
        for index, item in enumerate(value):
            item_name = f"database.schemas[{index}]"
            if not isinstance(item, dict):
                raise PluginManifestError(f"{item_name} must be an object")
            required_fields = {
                "schema_name",
                "purpose",
                "managed_by",
                "minimum_version",
            }
            optional_fields = {"version_check", "backup"}
            self._reject_unknown_fields(item, required_fields | optional_fields, item_name)
            self._require_fields(item, required_fields, item_name)

            raw_schema_name = self._require_non_empty_string(item["schema_name"], f"{item_name}.schema_name")
            schema_name = raw_schema_name.lower()
            if schema_name in PROTECTED_ORAC_SCHEMAS:
                raise PluginManifestError(
                    f"{item_name}.schema_name must not target protected Orac schema '{raw_schema_name}'"
                )
            if not DATABASE_SCHEMA_PATTERN.fullmatch(schema_name):
                raise PluginManifestError(
                    f"{item_name}.schema_name must match ^[a-z][a-z0-9_]*$"
                )

            result.append(
                PluginDatabaseSchema(
                    schema_name=schema_name,
                    purpose=self._require_non_empty_string(item["purpose"], f"{item_name}.purpose"),
                    managed_by=self._require_enum(
                        item["managed_by"],
                        f"{item_name}.managed_by",
                        DATABASE_MANAGERS,
                    ),
                    minimum_version=self._require_non_empty_string(
                        item["minimum_version"],
                        f"{item_name}.minimum_version",
                    ),
                    version_check=self._load_database_version_check(
                        item.get("version_check", {"enabled": False}),
                        f"{item_name}.version_check",
                    ),
                    backup=self._load_database_backup(item.get("backup"), f"{item_name}.backup"),
                )
            )
        return result

    def _load_database_version_check(
        self,
        value: Any,
        field_name: str,
    ) -> PluginDatabaseVersionCheck:
        if not isinstance(value, dict):
            raise PluginManifestError(f"{field_name} must be an object")
        self._reject_unknown_fields(value, {"enabled"}, field_name)
        return PluginDatabaseVersionCheck(
            enabled=self._require_bool(value.get("enabled", False), f"{field_name}.enabled")
        )

    def _load_database_backup(
        self,
        value: Any,
        field_name: str,
    ) -> PluginDatabaseBackup | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise PluginManifestError(f"{field_name} must be an object")
        self._reject_unknown_fields(value, {"include", "export_mode"}, field_name)
        include = self._require_bool(value.get("include", False), f"{field_name}.include")
        export_mode = self._require_optional_string(value.get("export_mode"), f"{field_name}.export_mode")
        return PluginDatabaseBackup(include=include, export_mode=export_mode)

    def _load_ui(self, value: Any) -> PluginUi | None:
        """Load optional plugin-owned UI/status metadata."""
        if value is None:
            return None
        if not isinstance(value, dict):
            raise PluginManifestError("ui must be an object")
        self._reject_unknown_fields(
            value,
            {"status_provider", "surfaces", "icon_class", "accent_class"},
            "ui",
        )
        status_provider = self._load_ui_status_provider(value.get("status_provider"))
        surfaces_value = value.get("surfaces", [])
        if not isinstance(surfaces_value, list):
            raise PluginManifestError("ui.surfaces must be a list")
        surfaces = tuple(
            self._load_ui_surface(surface_value, index)
            for index, surface_value in enumerate(surfaces_value)
        )
        return PluginUi(
            status_provider=status_provider,
            surfaces=surfaces,
            icon_class=self._require_optional_icon_class(
                value.get("icon_class"),
                "ui.icon_class",
            ),
            accent_class=self._require_optional_accent_class(
                value.get("accent_class"),
                "ui.accent_class",
            ),
        )

    def _load_ui_status_provider(self, value: Any) -> PluginUiStatusProvider | None:
        """Load one status provider declaration."""
        if value is None:
            return None
        if not isinstance(value, dict):
            raise PluginManifestError("ui.status_provider must be an object")
        self._reject_unknown_fields(
            value,
            {"id", "description", "format", "redaction_required"},
            "ui.status_provider",
        )
        self._require_fields(value, {"id", "format"}, "ui.status_provider")
        return PluginUiStatusProvider(
            provider_id=self._require_non_empty_string(
                value.get("id"),
                "ui.status_provider.id",
            ),
            description=(
                self._require_optional_string(
                    value.get("description"),
                    "ui.status_provider.description",
                )
                or ""
            ),
            format=self._require_enum(
                value.get("format"),
                "ui.status_provider.format",
                PLUGIN_UI_STATUS_FORMATS,
            ),
            redaction_required=self._require_bool(
                value.get("redaction_required", True),
                "ui.status_provider.redaction_required",
            ),
        )

    def _load_ui_surface(self, value: Any, index: int) -> PluginUiSurface:
        """Load one operational UI surface declaration."""
        field_name = f"ui.surfaces[{index}]"
        if not isinstance(value, dict):
            raise PluginManifestError(f"{field_name} must be an object")
        required_fields = {"id", "type", "label", "target", "audience", "enabled"}
        optional_fields = {"description", "required_roles", "apex", "react"}
        self._reject_unknown_fields(value, required_fields | optional_fields, field_name)
        self._require_fields(value, required_fields, field_name)
        target = self._require_enum(
            value.get("target"),
            f"{field_name}.target",
            PLUGIN_UI_SURFACE_TARGETS,
        )
        return PluginUiSurface(
            surface_id=self._require_non_empty_string(value.get("id"), f"{field_name}.id"),
            surface_type=self._require_enum(
                value.get("type"),
                f"{field_name}.type",
                PLUGIN_UI_SURFACE_TYPES,
            ),
            label=self._require_non_empty_string(
                value.get("label"),
                f"{field_name}.label",
            ),
            target=target,
            audience=self._require_enum(
                value.get("audience"),
                f"{field_name}.audience",
                PLUGIN_UI_AUDIENCES,
            ),
            enabled=self._require_bool(value.get("enabled"), f"{field_name}.enabled"),
            description=(
                self._require_optional_string(
                    value.get("description"),
                    f"{field_name}.description",
                )
                or ""
            ),
            required_roles=tuple(
                self._require_string_list(
                    value.get("required_roles", []),
                    f"{field_name}.required_roles",
                )
            ),
            apex=self._load_apex_surface_metadata(
                value.get("apex"),
                f"{field_name}.apex",
            ),
            react=self._load_react_surface_metadata(
                value.get("react"),
                f"{field_name}.react",
            ),
        )

    def _load_apex_surface_metadata(
        self,
        value: Any,
        field_name: str,
    ) -> PluginApexSurfaceMetadata | None:
        """Load optional APEX surface metadata."""
        if value is None:
            return None
        if not isinstance(value, dict):
            raise PluginManifestError(f"{field_name} must be an object")
        self._reject_unknown_fields(
            value,
            {"app_alias", "app_export", "entry_page_id", "install_required"},
            field_name,
        )
        return PluginApexSurfaceMetadata(
            app_alias=self._require_optional_string(
                value.get("app_alias"),
                f"{field_name}.app_alias",
            ),
            app_export=self._require_optional_string(
                value.get("app_export"),
                f"{field_name}.app_export",
            ),
            entry_page_id=self._require_non_negative_int(
                value.get("entry_page_id"),
                f"{field_name}.entry_page_id",
            ),
            install_required=self._require_bool(
                value.get("install_required", False),
                f"{field_name}.install_required",
            ),
        )

    def _load_react_surface_metadata(
        self,
        value: Any,
        field_name: str,
    ) -> PluginReactSurfaceMetadata | None:
        """Load optional React surface metadata."""
        if value is None:
            return None
        if not isinstance(value, dict):
            raise PluginManifestError(f"{field_name} must be an object")
        self._reject_unknown_fields(
            value,
            {"component", "status_endpoint", "install_required"},
            field_name,
        )
        return PluginReactSurfaceMetadata(
            component=self._require_optional_string(
                value.get("component"),
                f"{field_name}.component",
            ),
            status_endpoint=self._require_optional_string(
                value.get("status_endpoint"),
                f"{field_name}.status_endpoint",
            ),
            install_required=self._require_bool(
                value.get("install_required", False),
                f"{field_name}.install_required",
            ),
        )

    def _load_apex_apps(self, value: Any) -> list[PluginApexApp]:
        """Load optional plugin-supplied APEX application declarations."""
        if value is None:
            return []
        if not isinstance(value, list):
            raise PluginManifestError("apex_apps must be a list")
        return [
            self._load_apex_app(app_value, index)
            for index, app_value in enumerate(value)
        ]

    def _load_apex_app(self, value: Any, index: int) -> PluginApexApp:
        """Load one plugin-supplied APEX application declaration."""
        field_name = f"apex_apps[{index}]"
        if not isinstance(value, dict):
            raise PluginManifestError(f"{field_name} must be an object")
        required_fields = {"label", "app_export", "install_required"}
        optional_fields = {
            "alias",
            "app_alias",
            "description",
            "workspace",
            "parsing_schema",
            "application_id",
            "entry_page_id",
            "replace_existing",
            "required_roles",
            "icon",
            "icon_class",
            "card_title",
            "card_subtitle",
            "enabled",
        }
        self._reject_unknown_fields(value, required_fields | optional_fields, field_name)
        self._require_fields(value, required_fields, field_name)
        alias_value = value.get("app_alias", value.get("alias"))
        if alias_value is None:
            raise PluginManifestError(
                f"{field_name} missing required field(s): app_alias"
            )
        return PluginApexApp(
            app_alias=self._require_apex_alias(alias_value, f"{field_name}.app_alias"),
            label=self._require_non_empty_string(value.get("label"), f"{field_name}.label"),
            app_export=self._require_relative_export_path(
                value.get("app_export"),
                f"{field_name}.app_export",
            ),
            description=(
                self._require_optional_string(
                    value.get("description"),
                    f"{field_name}.description",
                )
                or ""
            ),
            workspace=self._require_enum(
                value.get("workspace", "ORAC"),
                f"{field_name}.workspace",
                SUPPORTED_APEX_WORKSPACES,
            ),
            parsing_schema=self._require_oracle_identifier(
                value.get("parsing_schema", "ORAC_APX_PUB"),
                f"{field_name}.parsing_schema",
            ),
            application_id=(
                None
                if value.get("application_id") is None
                else self._require_positive_int(
                    value.get("application_id"),
                    f"{field_name}.application_id",
                )
            ),
            entry_page_id=self._require_positive_int(
                value.get("entry_page_id", 1),
                f"{field_name}.entry_page_id",
            ),
            install_required=self._require_bool(
                value.get("install_required"),
                f"{field_name}.install_required",
            ),
            replace_existing=self._require_bool(
                value.get("replace_existing", False),
                f"{field_name}.replace_existing",
            ),
            required_roles=tuple(
                self._require_string_list(
                    value.get("required_roles", []),
                    f"{field_name}.required_roles",
                )
            ),
            icon=self._require_optional_icon_class(
                value.get("icon"),
                f"{field_name}.icon",
            ),
            icon_class=self._require_optional_icon_class(
                value.get("icon_class"),
                f"{field_name}.icon_class",
            ),
            card_title=self._require_optional_string(
                value.get("card_title"),
                f"{field_name}.card_title",
            ),
            card_subtitle=self._require_optional_string(
                value.get("card_subtitle"),
                f"{field_name}.card_subtitle",
            ),
            enabled=self._require_bool(value.get("enabled", True), f"{field_name}.enabled"),
        )

    @staticmethod
    def _require_non_empty_string(value: Any, field_name: str) -> str:
        if not isinstance(value, str):
            raise PluginManifestError(f"{field_name} must be a string")
        cleaned = value.strip()
        if not cleaned:
            raise PluginManifestError(f"{field_name} must be a non-empty string")
        return cleaned

    @staticmethod
    def _require_optional_string(value: Any, field_name: str) -> str | None:
        if value is None:
            return None
        return PluginDiscovery._require_non_empty_string(value, field_name)

    @staticmethod
    def _require_optional_icon_class(value: Any, field_name: str) -> str | None:
        """Return a normalized safe Font APEX icon class string."""
        if value is None:
            return None
        if not isinstance(value, str):
            raise PluginManifestError(f"{field_name} must be a string")
        if value != value.strip():
            raise PluginManifestError(
                f"{field_name} must be a safe Font APEX icon class"
            )
        if ICON_TOKEN_PATTERN.fullmatch(value):
            return f"fa {value}"
        if ICON_CLASS_PATTERN.fullmatch(value):
            return value
        raise PluginManifestError(
            f"{field_name} must match fa fa-[a-z0-9-]+ or fa-[a-z0-9-]+"
        )

    @staticmethod
    def _require_optional_accent_class(value: Any, field_name: str) -> str | None:
        """Return a fixed-allowlist Universal Theme accent class."""
        if value is None:
            return None
        cleaned = PluginDiscovery._require_non_empty_string(value, field_name)
        if cleaned not in PLUGIN_UI_ACCENT_CLASSES:
            raise PluginManifestError(
                f"{field_name} must be one of: "
                f"{', '.join(sorted(PLUGIN_UI_ACCENT_CLASSES))}"
            )
        return cleaned

    @staticmethod
    def _require_apex_alias(value: Any, field_name: str) -> str:
        """Return a validated APEX application alias."""
        cleaned = PluginDiscovery._require_non_empty_string(value, field_name)
        if not APEX_ALIAS_PATTERN.fullmatch(cleaned):
            raise PluginManifestError(
                f"{field_name} must start with a letter and contain only letters, numbers, underscores and hyphens"
            )
        return cleaned.upper()

    @staticmethod
    def _require_oracle_identifier(value: Any, field_name: str) -> str:
        """Return a validated simple Oracle identifier."""
        cleaned = PluginDiscovery._require_non_empty_string(value, field_name)
        if not SECRET_KEY_PATTERN.fullmatch(cleaned):
            raise PluginManifestError(
                f"{field_name} must start with a letter and contain only letters, numbers and underscores"
            )
        return cleaned.upper()

    @staticmethod
    def _require_relative_export_path(value: Any, field_name: str) -> str:
        """Return a safe plugin-relative SQL export path."""
        cleaned = PluginDiscovery._require_non_empty_string(value, field_name)
        path = PurePosixPath(cleaned)
        if path.is_absolute() or ".." in path.parts:
            raise PluginManifestError(f"{field_name} must be a relative path")
        if path.suffix.lower() != ".sql":
            raise PluginManifestError(f"{field_name} must reference a .sql file")
        return path.as_posix()

    @staticmethod
    def _require_optional_relative_path(value: Any, field_name: str) -> str | None:
        """Return a safe plugin-relative path when one is provided."""
        if value is None:
            return None
        cleaned = PluginDiscovery._require_non_empty_string(value, field_name)
        path = PurePosixPath(cleaned)
        if path.is_absolute() or ".." in path.parts:
            raise PluginManifestError(f"{field_name} must be a relative path")
        return path.as_posix()

    @staticmethod
    def _require_secret_key(value: Any, field_name: str) -> str:
        """Return a validated plugin secret key name."""
        cleaned = PluginDiscovery._require_non_empty_string(value, field_name)
        if not SECRET_KEY_PATTERN.fullmatch(cleaned):
            raise PluginManifestError(
                f"{field_name} must start with a letter and contain only letters, numbers and underscores"
            )
        return cleaned

    @staticmethod
    def _require_bool(value: Any, field_name: str) -> bool:
        if not isinstance(value, bool):
            raise PluginManifestError(f"{field_name} must be a boolean")
        return value

    @staticmethod
    def _require_positive_int(value: Any, field_name: str) -> int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise PluginManifestError(f"{field_name} must be an integer")
        if value <= 0:
            raise PluginManifestError(f"{field_name} must be greater than zero")
        return value

    @staticmethod
    def _require_bounded_positive_int(
        value: Any,
        field_name: str,
        *,
        max_value: int,
    ) -> int:
        result = PluginDiscovery._require_positive_int(value, field_name)
        if result > max_value:
            raise PluginManifestError(
                f"{field_name} must be less than or equal to {max_value}"
            )
        return result

    @staticmethod
    def _require_non_negative_int(value: Any, field_name: str) -> int | None:
        if value is None:
            return None
        if not isinstance(value, int) or isinstance(value, bool):
            raise PluginManifestError(f"{field_name} must be an integer")
        if value < 0:
            raise PluginManifestError(f"{field_name} must be greater than or equal to zero")
        return value

    @staticmethod
    def _require_enum(value: Any, field_name: str, allowed_values: set[str]) -> str:
        if not isinstance(value, str):
            raise PluginManifestError(f"{field_name} must be a string")
        cleaned = value.strip()
        if cleaned not in allowed_values:
            allowed = ", ".join(sorted(allowed_values))
            raise PluginManifestError(f"{field_name} must be one of: {allowed}")
        return cleaned

    @staticmethod
    def _reject_unknown_fields(
        value: dict[str, Any],
        allowed_fields: set[str],
        field_name: str,
    ) -> None:
        unknown_fields = sorted(set(value.keys()) - allowed_fields)
        if unknown_fields:
            raise PluginManifestError(
                f"{field_name} has unknown field(s): {', '.join(unknown_fields)}"
            )

    @staticmethod
    def _require_fields(
        value: dict[str, Any],
        required_fields: set[str],
        field_name: str,
    ) -> None:
        missing_fields = sorted(required_fields - set(value.keys()))
        if missing_fields:
            raise PluginManifestError(
                f"{field_name} missing required field(s): {', '.join(missing_fields)}"
            )

    @staticmethod
    def _require_subset(
        values: tuple[str, ...],
        allowed_values: list[str],
        field_name: str,
        parent_field_name: str,
    ) -> None:
        disallowed = sorted(set(values) - set(allowed_values))
        if disallowed:
            raise PluginManifestError(
                f"{field_name} must only reference values declared in "
                f"{parent_field_name}: {', '.join(disallowed)}"
            )

    @staticmethod
    def _require_string_list(
        value: Any,
        field_name: str,
        allow_empty: bool = True,
    ) -> list[str]:
        if not isinstance(value, list):
            raise PluginManifestError(f"{field_name} must be a list of strings")

        result: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise PluginManifestError(f"{field_name} must contain only strings")
            cleaned = item.strip()
            if not cleaned:
                raise PluginManifestError(
                    f"{field_name} must not contain empty string values"
                )
            result.append(cleaned)

        if not allow_empty and not result:
            raise PluginManifestError(f"{field_name} must contain at least one value")

        return result
