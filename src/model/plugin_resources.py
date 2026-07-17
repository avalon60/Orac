"""Resolve immutable resource files from active Orac plugin manifests."""
# Author: Clive Bostock
# Date: 17-Jul-2026
# Description: Provides safe plugin package resource lookup across install layouts.

from __future__ import annotations

from pathlib import Path, PurePosixPath

from model.plugin_package_layout import package_spec
from model.plugin_package_layout import repository_install_root
from model.plugin_routing.discovery import PluginDiscovery
from model.plugin_routing.models import PluginManifest


class PluginResourceError(RuntimeError):
    """Raised when a plugin resource path is invalid or unavailable."""


def resolve_plugin_resource(
    manifest: PluginManifest,
    relative_path: str | Path,
    *,
    required: bool = True,
) -> Path:
    """Resolve one immutable file beneath the plugin ``resources/`` directory."""
    return resolve_plugin_package_path(
        manifest,
        "resources",
        relative_path,
        required=required,
    )


def resolve_plugin_package_path(
    manifest: PluginManifest,
    directory: str,
    relative_path: str | Path = "",
    *,
    required: bool = True,
) -> Path:
    """Resolve one safe package path across repository and managed layouts.

    Args:
        manifest: Active plugin manifest.
        directory: BOM package directory name, such as ``resources``.
        relative_path: Relative path within the package directory.
        required: Whether a missing path should raise.

    Returns:
        The first existing candidate path, or the preferred repository-layout
        candidate when ``required`` is false.

    Raises:
        PluginResourceError: If the directory is unknown, the relative path is
        unsafe, or a required resource cannot be found.
    """
    spec = package_spec(directory)
    if spec is None:
        raise PluginResourceError(f"Unknown plugin package directory: {directory}")

    relative = _safe_relative_path(relative_path)
    repository_candidate = repository_install_root(manifest.plugin_dir, spec) / relative
    package_candidate = manifest.manifest_path.parent / spec.package_name / relative
    candidates = _unique_paths((repository_candidate, package_candidate))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    if required:
        raise PluginResourceError(
            "Plugin resource was not found: "
            + " or ".join(str(candidate) for candidate in candidates)
        )
    return candidates[0]


def manifest_for_plugin_module(
    module_file: str,
    plugin_id: str,
) -> PluginManifest:
    """Load the active-ish manifest adjacent to a direct plugin module import."""
    module_path = Path(module_file).resolve()
    plugin_dir = module_path.parent
    if plugin_dir.name == "plugin":
        manifest_path = plugin_dir.parent / "manifest.json"
        enforce_filename = False
    else:
        manifest_path = plugin_dir.parent / f"{plugin_id}.json"
        enforce_filename = True

    if not manifest_path.is_file():
        raise PluginResourceError(
            f"Plugin manifest was not found for '{plugin_id}': {manifest_path}"
        )
    return PluginDiscovery(manifest_path.parent).load_manifest(
        manifest_path,
        plugin_dir=plugin_dir,
        enforce_filename=enforce_filename,
    )


def _safe_relative_path(relative_path: str | Path) -> Path:
    """Return a platform path after rejecting absolute or traversing input."""
    text = str(relative_path or "").replace("\\", "/")
    path = PurePosixPath(text)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise PluginResourceError(f"Unsafe plugin resource path: {relative_path}")
    parts = tuple(part for part in path.parts if part not in {"", "."})
    return Path(*parts) if parts else Path()


def _unique_paths(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    """Return paths in order while removing exact duplicates."""
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        resolved = path.resolve(strict=False)
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return tuple(unique)
