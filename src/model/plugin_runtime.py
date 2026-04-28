"""Minimal plugin runtime helpers for manifest-driven plugin execution."""
# Author: Clive Bostock
# Date: 2026-04-23
# Description: Provides a modest execution contract and loader for Orac plugins.

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import importlib
from pathlib import Path
import sys
from typing import Iterator

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
