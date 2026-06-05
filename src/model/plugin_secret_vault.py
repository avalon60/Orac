"""Encrypted plugin-scoped personal access token vault."""
# Author: Clive Bostock
# Date: 05-Jun-2026
# Description: Stores encrypted plugin personal access tokens and exposes scoped runtime access.

from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path
import re
from typing import Iterable

from lib.user_security import decrypted_user_credential
from lib.user_security import encrypted_user_credential
from model.plugin_routing.discovery import PluginDiscovery
from model.plugin_routing.models import PluginManifest
from model.plugin_routing.models import PluginSecretKey

__author__ = "Clive Bostock"
__date__ = "05-Jun-2026"
__description__ = "Stores encrypted plugin personal access tokens and exposes scoped runtime access."


DEFAULT_PAT_VAULT_PATH = Path("~/.Orac/pat_vault.ini").expanduser()
DEFAULT_PAT_KEY = "access_token"

_PLUGIN_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_SECRET_KEY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


class PluginSecretVaultError(RuntimeError):
    """Raised when a plugin PAT vault operation cannot be completed safely."""


class PluginPatVaultStore:
    """Internal encrypted PAT vault store with plugin validation."""

    def __init__(
        self,
        *,
        vault_path: Path | None = None,
        plugins_dir: Path | None = None,
        allowed_plugins: Iterable[str] | None = None,
    ) -> None:
        """Initialise the encrypted PAT vault store.

        Args:
            vault_path: Optional explicit vault path, mainly for tests.
            plugins_dir: Plugin manifest directory used for validation.
            allowed_plugins: Optional explicit plugin id allow-list for tests.
        """
        self.vault_path = Path(vault_path or DEFAULT_PAT_VAULT_PATH).expanduser()
        self.plugins_dir = Path(plugins_dir or "plugins")
        self._allowed_plugins = (
            frozenset(_normalise_plugin_id(plugin_id) for plugin_id in allowed_plugins)
            if allowed_plugins is not None
            else None
        )

    def set_secret(self, plugin_id: str, key: str, value: str) -> None:
        """Create or update one encrypted plugin secret."""
        manifest = self._validate_known_plugin(plugin_id)
        plugin = manifest.plugin_id
        secret_key = self._validate_secret_key(manifest, key)
        secret_value = str(value or "")
        if not secret_value:
            raise PluginSecretVaultError("Secret value must not be empty.")

        config = self._read_config()
        if not config.has_section(plugin):
            config.add_section(plugin)
        config.set(plugin, secret_key, encrypted_user_credential(secret_value))
        self._write_config(config)

    def edit_secret(self, plugin_id: str, key: str, value: str) -> None:
        """Update an existing encrypted plugin secret."""
        manifest = self._validate_known_plugin(plugin_id)
        plugin = manifest.plugin_id
        secret_key = self._validate_secret_key(manifest, key)
        config = self._read_config()
        if not config.has_section(plugin) or not config.has_option(plugin, secret_key):
            raise PluginSecretVaultError(
                f"Plugin secret '{secret_key}' is not configured for '{plugin}'."
            )
        self.set_secret(plugin, secret_key, value)

    def get_secret(self, plugin_id: str, key: str = DEFAULT_PAT_KEY) -> str:
        """Return one decrypted plugin secret."""
        manifest = self._validate_known_plugin(plugin_id)
        plugin = manifest.plugin_id
        secret_key = self._validate_secret_key(manifest, key)
        config = self._read_config()
        if not config.has_section(plugin) or not config.has_option(plugin, secret_key):
            raise PluginSecretVaultError(self._missing_secret_message(manifest, secret_key))

        encrypted_value = config.get(plugin, secret_key)
        try:
            return decrypted_user_credential(encrypted_value)
        except Exception as exc:
            raise PluginSecretVaultError(
                f"Plugin secret '{secret_key}' for '{plugin}' could not be decrypted on this machine."
            ) from exc

    def delete_key(self, plugin_id: str, key: str) -> bool:
        """Delete one plugin secret key if present."""
        manifest = self._validate_known_plugin(plugin_id)
        plugin = manifest.plugin_id
        secret_key = self._validate_secret_key(manifest, key)
        config = self._read_config()
        if not config.has_section(plugin):
            return False
        removed = config.remove_option(plugin, secret_key)
        if not config.items(plugin):
            config.remove_section(plugin)
        self._write_config(config)
        return removed

    def delete_plugin(self, plugin_id: str) -> bool:
        """Delete all vault secrets for one plugin section."""
        manifest = self._validate_known_plugin(plugin_id)
        plugin = manifest.plugin_id
        config = self._read_config()
        removed = config.remove_section(plugin)
        self._write_config(config)
        return removed

    def list_plugins(self) -> tuple[str, ...]:
        """Return plugin ids with configured PAT vault sections."""
        return tuple(sorted(self._read_config().sections()))

    def list_keys(self, plugin_id: str) -> tuple[str, ...]:
        """Return configured key names for one plugin without secret values."""
        manifest = self._validate_known_plugin(plugin_id)
        plugin = manifest.plugin_id
        config = self._read_config()
        if not config.has_section(plugin):
            return ()
        return tuple(sorted(key for key, _value in config.items(plugin)))

    def list_expected_keys(self, plugin_id: str) -> tuple[PluginSecretKey, ...]:
        """Return manifest-declared expected secret keys for one plugin."""
        manifest = self._validate_known_plugin(plugin_id)
        if manifest.secrets is None:
            return ()
        return manifest.secrets.keys

    def check_secret(self, plugin_id: str, key: str | None = None) -> bool:
        """Return whether one validated plugin secret is configured."""
        manifest = self._validate_known_plugin(plugin_id)
        plugin = manifest.plugin_id
        secret_key = self._validate_secret_key(manifest, key or self.default_key(plugin))
        config = self._read_config()
        return config.has_section(plugin) and config.has_option(plugin, secret_key)

    def default_key(self, plugin_id: str) -> str:
        """Return the manifest default secret key for one plugin."""
        manifest = self._validate_known_plugin(plugin_id)
        if manifest.secrets is not None:
            return manifest.secrets.default_key
        return DEFAULT_PAT_KEY

    def _validate_known_plugin(self, plugin_id: str) -> PluginManifest:
        """Return a manifest after installed-plugin validation."""
        plugin = _normalise_plugin_id(plugin_id)
        manifest = self._known_manifests().get(plugin)
        if manifest is None:
            raise PluginSecretVaultError(
                f"Unknown plugin '{plugin}'. Install or enable a valid plugin manifest first."
            )
        return manifest

    def _known_manifests(self) -> dict[str, PluginManifest]:
        """Return known plugin manifests from the allow-list or discovery."""
        if self._allowed_plugins is not None:
            return {
                plugin_id: _manifest_stub(plugin_id)
                for plugin_id in self._allowed_plugins
            }

        manifests, errors = PluginDiscovery(self.plugins_dir).discover()
        if errors:
            raise PluginSecretVaultError(
                "Unable to validate plugin name because plugin discovery failed."
            )
        return {manifest.plugin_id: manifest for manifest in manifests}

    def _validate_secret_key(self, manifest: PluginManifest, key: str | None) -> str:
        """Return a key allowed by the plugin manifest secret declaration."""
        secret_key = _normalise_secret_key(key or self.default_key(manifest.plugin_id))
        if manifest.secrets is None:
            return secret_key
        if secret_key in manifest.secrets.key_names():
            return secret_key
        if manifest.secrets.allow_custom_keys:
            return secret_key
        raise PluginSecretVaultError(
            f"Secret key '{secret_key}' is not declared for plugin '{manifest.plugin_id}'."
        )

    @staticmethod
    def _missing_secret_message(manifest: PluginManifest, key: str) -> str:
        """Return an actionable missing-secret message."""
        setup_hint = None
        if manifest.secrets is not None:
            metadata = manifest.secrets.get_key(key)
            if metadata is not None:
                setup_hint = metadata.setup_hint
        if setup_hint:
            return (
                f"Required plugin secret '{key}' is not configured for "
                f"'{manifest.plugin_id}'. {setup_hint} Run: "
                f"bin/plugin-pat-mgr.sh --plugin {manifest.plugin_id} --set {key}"
            )
        return (
            "Plugin personal access token is not configured. Create it with: "
            f"bin/plugin-pat-mgr.sh --plugin {manifest.plugin_id} --set {key}"
        )

    def _read_config(self) -> ConfigParser:
        """Read the vault file, creating it first when needed."""
        self._ensure_vault_file()
        config = ConfigParser(interpolation=None)
        config.read(self.vault_path)
        return config

    def _write_config(self, config: ConfigParser) -> None:
        """Persist the vault config with restrictive permissions where possible."""
        self._ensure_vault_file()
        with self.vault_path.open("w", encoding="utf-8") as handle:
            config.write(handle)
        _chmod_best_effort(self.vault_path, 0o600)

    def _ensure_vault_file(self) -> None:
        """Create the vault directory and file with restrictive permissions."""
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        _chmod_best_effort(self.vault_path.parent, 0o700)
        if not self.vault_path.exists():
            self.vault_path.touch(mode=0o600)
        _chmod_best_effort(self.vault_path, 0o600)


class PluginSecretVault:
    """Plugin-facing scoped secret vault.

    Plugin code receives this narrowed object from the Orac runtime context and
    never passes a plugin id.
    """

    def __init__(
        self,
        *,
        plugin_id: str,
        store: PluginPatVaultStore | None = None,
    ) -> None:
        """Initialise a plugin-scoped vault facade."""
        self._plugin_id = _normalise_plugin_id(plugin_id)
        self._store = store or PluginPatVaultStore()

    @property
    def plugin_id(self) -> str:
        """Return the plugin id this vault is scoped to."""
        return self._plugin_id

    def get(self, key: str | None = None) -> str:
        """Return one decrypted secret for the current plugin."""
        if key is None:
            key = self._store.default_key(self._plugin_id)
        return self._store.get_secret(self._plugin_id, key)


def _normalise_plugin_id(plugin_id: str) -> str:
    """Return a validated plugin id."""
    plugin = str(plugin_id or "").strip()
    if not _PLUGIN_ID_PATTERN.fullmatch(plugin):
        raise PluginSecretVaultError(
            "Plugin id must match ^[a-z][a-z0-9_]*$."
        )
    return plugin


def _normalise_secret_key(key: str | None) -> str:
    """Return a validated plugin secret key."""
    secret_key = str(key or DEFAULT_PAT_KEY).strip()
    if not _SECRET_KEY_PATTERN.fullmatch(secret_key):
        raise PluginSecretVaultError(
            "Secret key must start with a letter and contain only letters, numbers and underscores."
        )
    return secret_key


def _chmod_best_effort(path: Path, mode: int) -> None:
    """Apply file permissions without failing on unsupported platforms."""
    try:
        path.chmod(mode)
    except OSError:
        pass


def _manifest_stub(plugin_id: str) -> PluginManifest:
    """Return a minimal manifest for tests that inject allowed plugin ids."""
    return PluginManifest(
        schema_version=2,
        plugin_id=plugin_id,
        name=plugin_id,
        description="Allowed test plugin.",
        version="1.0.0",
        enabled=True,
        capabilities=(),
        entitlements=(),
        entities=(),
        examples=(),
        entry_point=None,
        manifest_path=Path("plugins") / f"{plugin_id}.json",
        plugin_dir=Path("plugins") / plugin_id,
        manifest_hash="",
    )
