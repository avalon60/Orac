"""Minimal plugin runtime helpers for manifest-driven plugin execution."""
# Author: Clive Bostock
# Date: 2026-04-30
# Description: Provides a modest execution contract, entitlement-checked data
#   access, and loader for Orac plugins.

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import importlib
import inspect
from pathlib import Path
import sys
from typing import Any, Iterator

from model.plugin_routing.models import PluginManifest


class PluginRuntimeError(RuntimeError):
    """Raised when a plugin cannot be loaded or executed through the runtime seam."""


@dataclass(frozen=True)
class PluginExecutionResult:
    """Represents a handled plugin response ready to return to the client."""

    plugin_id: str
    content: str
    handled: bool = True
    stop_reason: str = "stop"


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

    try:
        module_name, class_name = manifest.entry_point.split(":", 1)
    except ValueError as exc:
        raise PluginRuntimeError(
            f"Plugin '{manifest.plugin_id}' entry_point must be in '<module>:<ClassName>' format."
        ) from exc

    full_module_name = f"{manifest.plugin_id}.{module_name}"
    plugins_root = manifest.manifest_path.parent

    with _temporary_sys_path(plugins_root):
        importlib.invalidate_caches()
        module = importlib.import_module(full_module_name)

    plugin_class = getattr(module, class_name, None)
    if plugin_class is None:
        raise PluginRuntimeError(
            f"Plugin '{manifest.plugin_id}' entry_point class '{class_name}' was not found."
        )
    if not isinstance(plugin_class, type):
        raise PluginRuntimeError(
            f"Plugin '{manifest.plugin_id}' entry_point '{class_name}' is not a class."
        )
    return plugin_class


def instantiate_plugin(
    plugin_class: type,
    *,
    logger: Any,
    config_mgr: Any,
    data_access: PluginDataAccess,
) -> Any:
    """Instantiate a plugin class with supported runtime dependencies."""
    kwargs = {
        "logger": logger,
        "config_mgr": config_mgr,
        "data_access": data_access,
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


def _resolve_user_preference(context_manager: Any, username: str, pref_key: str) -> Any | None:
    """Return a user preference through the published context manager API."""
    return context_manager.get_user_preference_value(username=username, pref_key=pref_key)


def _resolve_user_profile_field(context_manager: Any, username: str, field_name: str) -> Any | None:
    """Return a user profile field through the published context manager API."""
    profile = context_manager.get_user_profile(username)
    return profile.get(field_name)


_ENTITLEMENT_RESOLVERS = {
    "user_preferences.weather_location": (
        lambda context_manager, username: _resolve_user_preference(
            context_manager,
            username,
            "weather_location",
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
