"""Shared immutable layout contract for Orac plugin packages."""
# Author: Clive Bostock
# Date: 17-Jul-2026
# Description: Defines plugin package directory mappings without installer/runtime coupling.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath


@dataclass(frozen=True)
class PluginDirectorySpec:
    """Map one source directory into package and repository layouts."""

    package_name: str
    source_path: str
    install_path: str
    required: bool = False
    catch_all: bool = False


# Directory bill of materials for a plugin distribution.
#
# ``package_name`` is the directory at archive root.
# ``source_path`` is its location beneath the ergonomic source plugin directory.
# ``install_path`` is its destination beneath ``plugins/<plugin_id>/``.
#
# The catch-all ``plugin`` entry collects ordinary plugin implementation files
# while excluding source directories claimed by earlier BOM entries. Adding a
# future top-level package directory is therefore a single entry here.
PLUGIN_DIRECTORY_BOM: tuple[PluginDirectorySpec, ...] = (
    PluginDirectorySpec(
        package_name="resources",
        source_path="resources",
        install_path="resources",
    ),
    PluginDirectorySpec(
        package_name="plugin",
        source_path=".",
        install_path=".",
        required=True,
        catch_all=True,
    ),
)

# These source files live at archive root but are installed inside the plugin's
# repository directory. The manifest is handled separately because it installs
# beside the plugin directory as ``plugins/<plugin_id>.json``.
PLUGIN_ROOT_FILE_BOM: tuple[str, ...] = (
    "README.md",
    "requirements.txt",
)

IGNORED_SOURCE_PARTS = {"__pycache__", ".venv", "venv", ".git", "logs"}
IGNORED_SOURCE_SUFFIXES = {".pyc", ".pyo", ".log"}


def claimed_source_directories() -> set[str]:
    """Return source directory names claimed by non-catch-all BOM entries."""
    return {
        PurePosixPath(spec.source_path).parts[0]
        for spec in PLUGIN_DIRECTORY_BOM
        if not spec.catch_all and spec.source_path not in {"", "."}
    }


def source_root_for_spec(plugin_dir: Path, spec: PluginDirectorySpec) -> Path:
    """Return the source tree root for one directory spec."""
    if spec.source_path in {"", "."}:
        return plugin_dir
    return plugin_dir / spec.source_path


def repository_install_root(plugin_dir: Path, spec: PluginDirectorySpec) -> Path:
    """Return the repository install root for one directory spec."""
    if spec.install_path in {"", "."}:
        return plugin_dir
    return plugin_dir / spec.install_path


def is_ignored_source_file(relative: Path) -> bool:
    """Return whether a source file is mutable, generated, or transient."""
    return (
        any(part in IGNORED_SOURCE_PARTS for part in relative.parts)
        or relative.suffix in IGNORED_SOURCE_SUFFIXES
        or relative.name == "plugin.ini"
    )


def package_spec(directory: str) -> PluginDirectorySpec | None:
    """Return the directory spec for one package directory name."""
    package_name = str(directory or "").strip()
    for spec in PLUGIN_DIRECTORY_BOM:
        if spec.package_name == package_name:
            return spec
    return None
