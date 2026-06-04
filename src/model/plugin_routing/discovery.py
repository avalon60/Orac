"""Manifest discovery and validation for plugin routing."""
# Author: Clive Bostock
# Date: 2026-04-30
# Description: Scans manifest files, validates schema v2, and constructs manifest models.

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from model.plugin_routing.models import (
    PluginConfigKey,
    PluginDatabaseBackup,
    PluginDatabaseSchema,
    PluginDatabaseVersionCheck,
    PluginExecutionPolicy,
    PluginHealthCheck,
    PluginManifest,
    PluginServiceSchedule,
    PluginServiceRuntime,
)
from model.plugin_database_deployment import PROTECTED_ORAC_SCHEMAS

PLUGIN_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
DATABASE_SCHEMA_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$", re.IGNORECASE)
MANIFEST_SCHEMA_VERSION = 2
RUNTIME_MODES = {"on_demand", "service", "hybrid"}
CONFIG_VALUE_TYPES = {"string", "bool", "int", "float", "path", "list"}
SERVICE_EXECUTION_MODELS = {"scheduled", "long_running"}
SERVICE_START_POLICIES = {"auto", "manual"}
SERVICE_RESTART_POLICIES = {"never", "on_failure"}
DATABASE_ON_MISSING_POLICIES = {"warn_disable", "warn_only", "fail_refresh"}
DATABASE_MANAGERS = {"orac"}
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
    "configuration",
    "database",
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

    def _load_manifest(self, manifest_path: Path) -> PluginManifest:
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
        if plugin_id != manifest_stem:
            raise PluginManifestError(
                f"plugin_id '{plugin_id}' must exactly match manifest filename stem '{manifest_stem}'"
            )

        plugin_dir = self._plugins_dir / plugin_id
        if not plugin_dir.exists() or not plugin_dir.is_dir():
            raise PluginManifestError(
                f"Matching plugin directory is required: {plugin_dir}"
            )
        if plugin_dir.name != plugin_id:
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
        runtime_mode, service_runtime = self._load_runtime(data["runtime"])
        execution_policy = self._load_execution_policy(
            data.get("execution"),
            capabilities=capabilities,
            entitlements=entitlements,
        )
        configuration_required, configuration_optional = self._load_configuration(
            data.get("configuration", {})
        )
        database_required, database_on_missing, database_schemas = self._load_database(
            data.get("database", {})
        )

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
            execution_policy=execution_policy,
            configuration_required=tuple(configuration_required),
            configuration_optional=tuple(configuration_optional),
            database_required=database_required,
            database_on_missing=database_on_missing,
            database_schemas=tuple(database_schemas),
        )

    def _load_runtime(self, value: Any) -> tuple[str, PluginServiceRuntime | None]:
        if not isinstance(value, dict):
            raise PluginManifestError("runtime must be an object")

        unknown_fields = sorted(set(value.keys()) - {"mode", "service"})
        if unknown_fields:
            raise PluginManifestError(
                f"runtime has unknown field(s): {', '.join(unknown_fields)}"
            )

        mode = self._require_enum(value.get("mode"), "runtime.mode", RUNTIME_MODES)
        service_value = value.get("service")
        if mode in {"service", "hybrid"}:
            if service_value is None:
                raise PluginManifestError(
                    "runtime.service is required when runtime.mode is service or hybrid"
                )
            service_runtime = self._load_service_runtime(service_value)
        elif service_value is not None:
            raise PluginManifestError(
                "runtime.service is only allowed when runtime.mode is service or hybrid"
            )
        else:
            service_runtime = None

        return mode, service_runtime

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

    def _load_service_runtime(self, value: Any) -> PluginServiceRuntime:
        if not isinstance(value, dict):
            raise PluginManifestError("runtime.service must be an object")

        required_fields = {
            "entry_point",
            "execution_model",
            "start_policy",
            "restart_policy",
            "shutdown_timeout_seconds",
        }
        optional_fields = {"health_check", "schedule"}
        self._reject_unknown_fields(value, required_fields | optional_fields, "runtime.service")
        self._require_fields(value, required_fields, "runtime.service")

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

    def _load_database(self, value: Any) -> tuple[bool, str, list[PluginDatabaseSchema]]:
        if not isinstance(value, dict):
            raise PluginManifestError("database must be an object")

        allowed_fields = {"required", "on_missing", "schemas"}
        self._reject_unknown_fields(value, allowed_fields, "database")

        required = self._require_bool(value.get("required", False), "database.required")
        on_missing = self._require_enum(
            value.get("on_missing", "warn_disable"),
            "database.on_missing",
            DATABASE_ON_MISSING_POLICIES,
        )
        schemas = self._load_database_schemas(value.get("schemas", []))

        if required and not schemas:
            raise PluginManifestError("database.schemas must contain at least one value when database.required is true")

        return required, on_missing, schemas

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
