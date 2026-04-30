"""Manifest discovery and validation for plugin routing."""
# Author: Clive Bostock
# Date: 2026-04-30
# Description: Scans manifest files, validates schema v1, and constructs manifest models.

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from model.plugin_routing.models import PluginManifest

PLUGIN_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
MANIFEST_SCHEMA_VERSION = 1
REQUIRED_FIELDS = {
    "schema_version",
    "plugin_id",
    "name",
    "description",
    "version",
    "enabled",
    "capabilities",
    "entitlements",
}
OPTIONAL_FIELDS = {
    "entities",
    "examples",
    "entry_point",
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
    def _require_bool(value: Any, field_name: str) -> bool:
        if not isinstance(value, bool):
            raise PluginManifestError(f"{field_name} must be a boolean")
        return value

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
