"""Minimal plugin runtime helpers for manifest-driven plugin execution."""
# Author: Clive Bostock
# Date: 2026-04-30
# Description: Provides a modest execution contract, entitlement-checked data
#   access, and loader for Orac plugins.

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import importlib
from importlib.machinery import ModuleSpec
import inspect
from pathlib import Path
import sys
from types import ModuleType
from typing import Any, Iterator

from model.plugin_config import PluginConfigManager
from model.plugin_routing.models import PluginManifest
from model.plugin_secret_vault import PluginSecretVault


class PluginRuntimeError(RuntimeError):
    """Raised when a plugin cannot be loaded or executed through the runtime seam."""


@dataclass(frozen=True)
class PluginExecutionResult:
    """Represents a handled plugin response ready to return to the client."""

    plugin_id: str
    content: str
    handled: bool = True
    stop_reason: str = "stop"
    provenance: dict[str, Any] = field(default_factory=dict)
    silent: bool = False


@dataclass(frozen=True)
class PluginDataAccess:
    """Entitlement-checked data access service exposed to plugins."""

    manifest: PluginManifest
    context_manager: Any
    auth_user: str
    logger: Any

    def get(self, entitlement_key: str) -> Any | None:
        """Return a declared entitlement value for the authenticated user."""
        entitlement = str(entitlement_key or "").strip()
        if not entitlement:
            raise PluginRuntimeError("Entitlement key is required.")

        if entitlement not in self.manifest.entitlements:
            raise PluginRuntimeError(
                f"Plugin '{self.manifest.plugin_id}' requested undeclared entitlement "
                f"'{entitlement}'."
            )

        resolver = _ENTITLEMENT_RESOLVERS.get(entitlement)
        if resolver is None:
            raise PluginRuntimeError(
                f"Plugin entitlement '{entitlement}' is not supported by the runtime."
            )

        username = str(self.auth_user or "").strip()
        if not username:
            raise PluginRuntimeError(
                f"Plugin '{self.manifest.plugin_id}' cannot access entitlement "
                f"'{entitlement}' without an authenticated user."
            )

        try:
            return resolver(self.context_manager, username)
        except Exception as exc:
            self.logger.log_error(
                f"Plugin data access failed for '{self.manifest.plugin_id}' entitlement "
                f"'{entitlement}': {exc}"
            )
            raise PluginRuntimeError(
                f"Plugin '{self.manifest.plugin_id}' could not access entitlement "
                f"'{entitlement}'."
            ) from exc

    def get_many(self, entitlement_keys: tuple[str, ...] | list[str]) -> dict[str, Any | None]:
        """Return a mapping of entitlement keys to values."""
        return {
            str(entitlement_key): self.get(str(entitlement_key))
            for entitlement_key in entitlement_keys
        }


def load_plugin_class(manifest: PluginManifest) -> type:
    """Loads a plugin class from a manifest entry point.

    The current execution contract expects entry points in the form
    `<module>:<ClassName>`, where the module resolves within `plugins/<plugin-id>/`.

    Args:
        manifest: Plugin manifest containing the `entry_point` metadata.

    Returns:
        The plugin class referenced by the manifest.

    Raises:
        PluginRuntimeError: If the entry point is missing or invalid.
    """
    if not manifest.entry_point:
        raise PluginRuntimeError(f"Plugin '{manifest.plugin_id}' has no entry_point.")
    return load_plugin_entry_point(
        manifest=manifest,
        entry_point=manifest.entry_point,
        field_name="entry_point",
    )


def load_plugin_service_class(
    manifest: PluginManifest,
    service_runtime: Any | None = None,
) -> type:
    """Load the service class declared by a service-capable manifest.

    Args:
        manifest: Plugin manifest containing `runtime.service` metadata.

    Returns:
        The plugin service class referenced by the manifest.

    Raises:
        PluginRuntimeError: If the service entry point is missing or invalid.
    """
    service_runtime = service_runtime or manifest.service_runtime
    if service_runtime is None:
        raise PluginRuntimeError(
            f"Plugin '{manifest.plugin_id}' has no runtime.service metadata."
        )
    return load_plugin_entry_point(
        manifest=manifest,
        entry_point=service_runtime.entry_point,
        field_name="runtime.service.entry_point",
    )


def load_plugin_entry_point(
    *,
    manifest: PluginManifest,
    entry_point: str,
    field_name: str,
) -> type:
    """Load a plugin class from a manifest entry point string."""

    try:
        module_name, class_name = entry_point.split(":", 1)
    except ValueError as exc:
        raise PluginRuntimeError(
            f"Plugin '{manifest.plugin_id}' {field_name} must be in "
            "'<module>:<ClassName>' format."
        ) from exc

    full_module_name = f"{manifest.plugin_id}.{module_name}"
    plugins_root = manifest.manifest_path.parent

    if manifest.plugin_dir.name == manifest.plugin_id:
        with _temporary_sys_path(plugins_root):
            importlib.invalidate_caches()
            module = importlib.import_module(full_module_name)
    else:
        with _temporary_plugin_package(
            manifest.plugin_id,
            manifest.plugin_dir,
        ):
            importlib.invalidate_caches()
            module = importlib.import_module(full_module_name)

    plugin_class = getattr(module, class_name, None)
    if plugin_class is None:
        raise PluginRuntimeError(
            f"Plugin '{manifest.plugin_id}' {field_name} class "
            f"'{class_name}' was not found."
        )
    if not isinstance(plugin_class, type):
        raise PluginRuntimeError(
            f"Plugin '{manifest.plugin_id}' {field_name} '{class_name}' is not a class."
        )
    return plugin_class


def instantiate_plugin(
    plugin_class: type,
    *,
    logger: Any,
    config_mgr: Any,
    data_access: PluginDataAccess,
    runtime_context: PluginRuntimeContext | None = None,
) -> Any:
    """Instantiate a plugin class with supported runtime dependencies."""
    kwargs = {
        "logger": logger,
        "config_mgr": config_mgr,
        "data_access": data_access,
        "runtime_context": runtime_context,
    }
    try:
        signature = inspect.signature(plugin_class)
    except (TypeError, ValueError):
        signature = None

    if signature is not None:
        kwargs = {
            key: value
            for key, value in kwargs.items()
            if key in signature.parameters
        }

    return plugin_class(**kwargs)


@contextmanager
def _temporary_sys_path(path: Path) -> Iterator[None]:
    """Temporarily prepends a path to `sys.path` for plugin imports."""
    path_str = str(path)
    inserted = False
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = True
    try:
        yield
    finally:
        if inserted:
            try:
                sys.path.remove(path_str)
            except ValueError:
                pass


@contextmanager
def _temporary_plugin_package(plugin_id: str, plugin_dir: Path) -> Iterator[None]:
    """Expose an installed generic ``plugin/`` directory as its plugin ID."""
    prefix = f"{plugin_id}."
    previous_modules = {
        name: module
        for name, module in tuple(sys.modules.items())
        if name == plugin_id or name.startswith(prefix)
    }
    for name in previous_modules:
        sys.modules.pop(name, None)

    package = ModuleType(plugin_id)
    package.__package__ = plugin_id
    package.__path__ = [str(plugin_dir)]
    package.__spec__ = ModuleSpec(plugin_id, loader=None, is_package=True)
    package.__spec__.submodule_search_locations = [str(plugin_dir)]
    sys.modules[plugin_id] = package
    try:
        yield
    finally:
        for name in tuple(sys.modules):
            if name == plugin_id or name.startswith(prefix):
                sys.modules.pop(name, None)
        sys.modules.update(previous_modules)


def _resolve_user_preference(context_manager: Any, username: str, pref_key: str) -> Any | None:
    """Return a user preference through the published context manager API."""
    return context_manager.get_user_preference_value(username=username, pref_key=pref_key)


def _resolve_user_profile_field(context_manager: Any, username: str, field_name: str) -> Any | None:
    """Return a user profile field through the published context manager API."""
    profile = context_manager.get_user_profile(username)
    return profile.get(field_name)


_ENTITLEMENT_RESOLVERS = {
    "user_preferences.user_location": (
        lambda context_manager, username: _resolve_user_preference(
            context_manager,
            username,
            "user_location",
        )
    ),
    "user_preferences.timezone": (
        lambda context_manager, username: _resolve_user_preference(
            context_manager,
            username,
            "timezone",
        )
    ),
    "users.display_name": (
        lambda context_manager, username: _resolve_user_profile_field(
            context_manager,
            username,
            "display_name",
        )
    ),
    "users.username": (
        lambda context_manager, username: _resolve_user_profile_field(
            context_manager,
            username,
            "authenticated_username",
        )
    ),
}


@dataclass(frozen=True)
class PluginRuntimeContext:
    """Narrow Orac-owned runtime context exposed to on-demand plugins."""

    manifest: PluginManifest
    logger: Any
    config_mgr: Any
    auth_user: str
    plugin_db_session_factory: Any | None = None
    plugin_service_manager: Any | None = None
    plugin_config_manager: PluginConfigManager | None = None
    _secret_vault: PluginSecretVault | None = None

    @property
    def plugin_id(self) -> str:
        """Return the current plugin identifier."""
        return self.manifest.plugin_id

    def plugin_db_session(self) -> Any:
        """Return a managed ORAC_PLUGIN database session for plugin runtime use."""
        if self.plugin_db_session_factory is None:
            raise PluginRuntimeError(
                f"Plugin '{self.plugin_id}' requested database access, but no "
                "managed plugin database session factory is configured."
            )
        return self.plugin_db_session_factory()

    def plugin_config(self) -> PluginConfigManager:
        """Return this plugin's scoped configuration manager."""
        if self.plugin_config_manager is None:
            raise PluginRuntimeError(
                f"Plugin '{self.plugin_id}' requested configuration access, but no "
                "plugin configuration manager is configured."
            )
        return self.plugin_config_manager

    @property
    def secret_vault(self) -> PluginSecretVault:
        """Return this plugin's scoped personal access token vault."""
        if self._secret_vault is None:
            return PluginSecretVault(plugin_id=self.plugin_id, manifest=self.manifest)
        return self._secret_vault

    def run_service_command(
        self,
        plugin_id: str,
        command: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        """Dispatch a plugin command to an Orac-managed service instance."""
        if self.plugin_service_manager is None:
            raise PluginRuntimeError(
                "Plugin service manager is unavailable for service command dispatch."
            )
        run_command = getattr(self.plugin_service_manager, "run_service_command", None)
        if not callable(run_command):
            raise PluginRuntimeError(
                "Plugin service manager does not support service command dispatch."
            )
        return run_command(plugin_id, command, payload or {})
