"""Plugin-scoped configuration loading and validation."""
# Author: Clive Bostock
# Date: 04-Jun-2026
# Description: Provides scoped plugin.ini access for Orac plugins.

from __future__ import annotations

from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from model.plugin_routing.models import PluginManifest

__author__ = "Clive Bostock"
__date__ = "04-Jun-2026"
__description__ = "Provides scoped plugin.ini access for Orac plugins."


PluginConfigurationStatus = Literal[
    "not_required",
    "configured",
    "missing_required",
    "uninitialised",
]

_UNINITIALISED_PLACEHOLDER = re.compile(r"%[A-Za-z0-9_.-]+%")


class PluginConfigError(RuntimeError):
    """Raised when plugin configuration cannot be loaded or used safely."""


@dataclass(frozen=True)
class PluginConfigurationResult:
    """Result of validating one plugin's local configuration."""

    plugin_id: str
    status: PluginConfigurationStatus
    eligible: bool
    message: str
    missing_keys: tuple[str, ...] = ()
    uninitialised_keys: tuple[str, ...] = ()


class PluginConfigManager:
    """Loads and exposes configuration for exactly one plugin."""

    def __init__(
        self,
        manifest: PluginManifest,
        *,
        logger: Any | None = None,
    ) -> None:
        """Initialise a plugin-scoped config manager.

        Args:
            manifest: The plugin manifest that owns the configuration.
            logger: Optional Orac logger.
        """
        self._manifest = manifest
        self._logger = logger
        self._config_path = manifest.plugin_dir / "plugin.ini"
        self._config = ConfigParser(interpolation=None)
        self._loaded = False

    @property
    def plugin_id(self) -> str:
        """Return the owning plugin identifier."""
        return self._manifest.plugin_id

    @property
    def config_path(self) -> Path:
        """Return the plugin-local config path."""
        return self._config_path

    def validate(self) -> PluginConfigurationResult:
        """Validate this plugin's local configuration.

        Returns:
            A result describing whether the plugin may proceed to deployment and
            runtime eligibility.
        """
        self._load_if_present()
        required_keys = self._required_key_names()
        if not self._config_path.is_file():
            if not required_keys:
                return PluginConfigurationResult(
                    plugin_id=self.plugin_id,
                    status="not_required",
                    eligible=True,
                    message="Plugin has no required local configuration.",
                )
            return PluginConfigurationResult(
                plugin_id=self.plugin_id,
                status="missing_required",
                eligible=False,
                message=(
                    "Required plugin configuration is missing. Run "
                    f"plugin_init.sh {self.plugin_id} to initialise plugin configuration."
                ),
                missing_keys=required_keys,
            )

        uninitialised_keys = self._uninitialised_keys()
        if uninitialised_keys:
            return PluginConfigurationResult(
                plugin_id=self.plugin_id,
                status="uninitialised",
                eligible=False,
                message=(
                    "Plugin configuration contains uninitialised placeholders. Run "
                    f"plugin_init.sh {self.plugin_id} to initialise plugin configuration."
                ),
                uninitialised_keys=uninitialised_keys,
            )

        missing_keys = tuple(
            key_name
            for key_name in required_keys
            if not self._has_non_empty_key_name(key_name)
        )
        if missing_keys:
            return PluginConfigurationResult(
                plugin_id=self.plugin_id,
                status="missing_required",
                eligible=False,
                message=(
                    "Required plugin configuration keys are missing. Run "
                    f"plugin_init.sh {self.plugin_id} to initialise plugin configuration."
                ),
                missing_keys=missing_keys,
            )

        return PluginConfigurationResult(
            plugin_id=self.plugin_id,
            status="configured" if required_keys else "not_required",
            eligible=True,
            message="Plugin local configuration is valid.",
        )

    def config_value(self, section: str, key: str, default: Any = None) -> Any:
        """Return a plugin-local string config value."""
        self._load_if_present()
        if not self._config.has_section(section) or not self._config.has_option(section, key):
            if default is not None:
                return default
            raise PluginConfigError(
                f"Missing plugin config key {section}.{key} in {self._config_path}"
            )
        return self._config.get(section, key)

    def int_config_value(self, section: str, key: str, default: int | None = None) -> int:
        """Return a plugin-local integer config value."""
        self._load_if_present()
        if not self._config.has_section(section) or not self._config.has_option(section, key):
            if default is not None:
                return default
            raise PluginConfigError(
                f"Missing plugin config key {section}.{key} in {self._config_path}"
            )
        return self._config.getint(section, key)

    def bool_config_value(
        self,
        section: str,
        key: str,
        default: bool | None = None,
    ) -> bool:
        """Return a plugin-local boolean config value."""
        self._load_if_present()
        if not self._config.has_section(section) or not self._config.has_option(section, key):
            if default is not None:
                return default
            raise PluginConfigError(
                f"Missing plugin config key {section}.{key} in {self._config_path}"
            )
        return self._config.getboolean(section, key)

    def section_dict(self, section: str) -> dict[str, str]:
        """Return all keys from one plugin-local config section."""
        self._load_if_present()
        if not self._config.has_section(section):
            return {}
        return dict(self._config.items(section))

    def _load_if_present(self) -> None:
        """Load ``plugin.ini`` once when present."""
        if self._loaded:
            return
        self._loaded = True
        if not self._config_path.exists():
            return
        if not self._config_path.is_file():
            raise PluginConfigError(
                f"Plugin configuration path is not a file: {self._config_path}"
            )
        try:
            with self._config_path.open(encoding="utf-8") as handle:
                self._config.read_file(handle)
        except OSError as exc:
            raise PluginConfigError(
                f"Unable to read plugin configuration for '{self.plugin_id}': {exc}"
            ) from exc

    def _required_key_names(self) -> tuple[str, ...]:
        """Return manifest-declared required keys as ``section.key`` strings."""
        return tuple(
            f"{config_key.section}.{config_key.key}"
            for config_key in self._manifest.configuration_required
        )

    def _has_non_empty_key_name(self, key_name: str) -> bool:
        """Return whether a required key is present and non-empty."""
        section, key = key_name.split(".", 1)
        if not self._config.has_section(section) or not self._config.has_option(section, key):
            return False
        return bool(str(self._config.get(section, key) or "").strip())

    def _uninitialised_keys(self) -> tuple[str, ...]:
        """Return keys whose raw values still contain init placeholders."""
        keys: list[str] = []
        for section in self._config.sections():
            for key, value in self._config.items(section):
                if _UNINITIALISED_PLACEHOLDER.search(str(value or "")):
                    keys.append(f"{section}.{key}")
        return tuple(keys)
