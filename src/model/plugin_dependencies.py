"""Validate and install manifest-declared plugin Python dependencies."""
# Author: Clive Bostock
# Date: 07-Jun-2026
# Description: Provides safe requirement parsing and shared-environment installation.

from __future__ import annotations

from dataclasses import dataclass
import ast
import hashlib
from importlib import metadata
from pathlib import Path
import re
import subprocess
import sys
from typing import Callable, Iterable, Sequence

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name


class PluginDependencyError(RuntimeError):
    """Raised when plugin dependency validation or installation fails."""


@dataclass(frozen=True)
class PluginDependencyResult:
    """Describe the result of dependency installation and validation."""

    status: str
    fingerprint: str
    requirements: tuple[str, ...]
    message: str


def normalise_requirements(value: object) -> tuple[str, ...]:
    """Validate and canonicalise a manifest dependency list.

    Args:
        value: Raw manifest value expected to contain requirement strings.

    Returns:
        Canonical requirement strings sorted by package name and requirement.

    Raises:
        PluginDependencyError: If a dependency is malformed or unsafe.
    """
    if not isinstance(value, list):
        raise PluginDependencyError("must be a list")

    normalised: list[tuple[str, str]] = []
    seen: set[str] = set()
    for index, raw_requirement in enumerate(value):
        if not isinstance(raw_requirement, str) or not raw_requirement.strip():
            raise PluginDependencyError(
                f"entry {index} must be a non-empty requirement string"
            )
        text = raw_requirement.strip()
        if text.startswith("-"):
            raise PluginDependencyError(f"pip options are not allowed: {text}")
        try:
            requirement = Requirement(text)
        except InvalidRequirement as exc:
            raise PluginDependencyError(
                f"invalid requirement '{text}'"
            ) from exc
        if requirement.url is not None:
            raise PluginDependencyError(
                f"direct references and URLs are not allowed: {text}"
            )
        name = canonicalize_name(requirement.name)
        if name in seen:
            raise PluginDependencyError(
                f"duplicate dependency declaration for '{name}'"
            )
        seen.add(name)
        canonical = _canonical_requirement(requirement)
        normalised.append((name, canonical))
    return tuple(item[1] for item in sorted(normalised))


def dependency_fingerprint(requirements: Iterable[str]) -> str:
    """Return a stable SHA-256 fingerprint for validated requirements."""
    canonical = normalise_requirements(list(requirements))
    return hashlib.sha256("\n".join(canonical).encode("utf-8")).hexdigest()


def requirements_file_values(path: Path) -> tuple[str, ...]:
    """Read and validate a human-readable requirements mirror."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise PluginDependencyError(f"unable to read {path}: {exc}") from exc
    values = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
    return normalise_requirements(values)


def validate_requirements_mirror(
    path: Path,
    expected: Sequence[str],
) -> None:
    """Require an optional requirements file to match the manifest."""
    if not path.is_file():
        return
    actual = requirements_file_values(path)
    canonical_expected = normalise_requirements(list(expected))
    if actual != canonical_expected:
        raise PluginDependencyError(
            f"{path} does not match manifest python_dependencies"
        )


class PluginDependencyInstaller:
    """Install validated dependencies into the active Orac interpreter."""

    def __init__(
        self,
        *,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        interpreter: str | None = None,
    ) -> None:
        """Initialise the dependency installer.

        Args:
            runner: Injectable subprocess runner for tests.
            interpreter: Python executable receiving dependency installations.
        """
        self._runner = runner
        self._interpreter = interpreter or sys.executable

    def install(self, requirements: Sequence[str]) -> PluginDependencyResult:
        """Install dependencies and run pip's environment consistency check."""
        canonical = normalise_requirements(list(requirements))
        fingerprint = dependency_fingerprint(canonical)
        if canonical:
            self._run(
                [self._interpreter, "-m", "pip", "install", *canonical],
                "install plugin Python dependencies",
            )
        self._run(
            [self._interpreter, "-m", "pip", "check"],
            "validate the Python environment",
        )
        return PluginDependencyResult(
            status="success" if canonical else "not_required",
            fingerprint=fingerprint,
            requirements=canonical,
            message=(
                "Plugin Python dependencies installed and validated."
                if canonical
                else "Plugin declares no Python dependencies."
            ),
        )

    def check(self, requirements: Sequence[str]) -> PluginDependencyResult:
        """Validate an unchanged dependency set without invoking pip install."""
        canonical = normalise_requirements(list(requirements))
        for value in canonical:
            requirement = Requirement(value)
            if requirement.marker is not None and not requirement.marker.evaluate():
                continue
            try:
                installed_version = metadata.version(requirement.name)
            except metadata.PackageNotFoundError as exc:
                raise PluginDependencyError(
                    f"Required plugin dependency is not installed: {requirement.name}"
                ) from exc
            if requirement.specifier and installed_version not in requirement.specifier:
                raise PluginDependencyError(
                    f"Installed {requirement.name} {installed_version} does not satisfy {value}"
                )
        self._run(
            [self._interpreter, "-m", "pip", "check"],
            "validate the Python environment",
        )
        return PluginDependencyResult(
            status="success" if canonical else "not_required",
            fingerprint=dependency_fingerprint(canonical),
            requirements=canonical,
            message="Plugin Python dependencies are already satisfied.",
        )

    def _run(self, command: list[str], action: str) -> None:
        """Run one pip command without shell interpretation."""
        try:
            completed = self._runner(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            raise PluginDependencyError(f"Unable to {action}: {exc}") from exc
        if completed.returncode != 0:
            detail = _redact_package_index_credentials(
                (completed.stderr or completed.stdout or "").strip()
            )
            raise PluginDependencyError(
                f"Unable to {action}: {detail or 'pip returned a non-zero status'}"
            )


def installed_distribution_names() -> frozenset[str]:
    """Return canonical names for distributions installed in the environment."""
    return frozenset(
        canonicalize_name(distribution.metadata["Name"])
        for distribution in metadata.distributions()
        if distribution.metadata.get("Name")
    )


def validate_declared_imports(
    plugin_dir: Path,
    requirements: Sequence[str],
    *,
    plugin_id: str | None = None,
) -> None:
    """Reject direct third-party imports missing from the manifest.

    The check uses installed distribution metadata to map import package names
    to distribution names. Unknown imports are left to the readiness import
    check because a distribution may not be installed before installation.
    """
    declared = {
        canonicalize_name(Requirement(value).name)
        for value in normalise_requirements(list(requirements))
    }
    package_distributions = metadata.packages_distributions()
    local_modules = {
        path.stem
        for path in plugin_dir.glob("*.py")
    } | {
        path.name
        for path in plugin_dir.iterdir()
        if path.is_dir() and (path / "__init__.py").is_file()
    }
    ignored = set(sys.stdlib_module_names) | local_modules | {
        "model",
        "lib",
        "controller",
        "view",
        plugin_dir.name,
    }
    if plugin_id:
        ignored.add(plugin_id)
    missing: dict[str, set[str]] = {}
    for path in sorted(plugin_dir.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as exc:
            raise PluginDependencyError(f"Unable to inspect imports in {path}: {exc}") from exc
        for node in ast.walk(tree):
            root = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    _record_import(
                        alias.name.split(".", 1)[0],
                        path,
                        ignored,
                        package_distributions,
                        declared,
                        missing,
                    )
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                root = node.module.split(".", 1)[0]
            if root:
                _record_import(
                    root,
                    path,
                    ignored,
                    package_distributions,
                    declared,
                    missing,
                )
    if missing:
        detail = "; ".join(
            f"{name} imported by {', '.join(sorted(paths))}"
            for name, paths in sorted(missing.items())
        )
        raise PluginDependencyError(
            f"Plugin has undeclared third-party imports: {detail}"
        )


def _canonical_requirement(requirement: Requirement) -> str:
    """Render a stable requirement string without direct references."""
    value = canonicalize_name(requirement.name)
    if requirement.extras:
        value += "[" + ",".join(sorted(requirement.extras)) + "]"
    value += str(requirement.specifier)
    if requirement.marker is not None:
        value += f"; {requirement.marker}"
    return value


def _record_import(
    import_name: str,
    path: Path,
    ignored: set[str],
    package_distributions: dict[str, list[str]],
    declared: set[str],
    missing: dict[str, set[str]],
) -> None:
    """Record a mapped third-party import when it is undeclared."""
    if import_name in ignored:
        return
    distributions = package_distributions.get(import_name, [])
    if not distributions:
        if canonicalize_name(import_name) not in declared:
            missing.setdefault(import_name, set()).add(str(path))
        return
    canonical_distributions = {
        canonicalize_name(distribution) for distribution in distributions
    }
    if canonical_distributions.isdisjoint(declared):
        missing.setdefault(import_name, set()).add(str(path))


def _redact_package_index_credentials(value: str) -> str:
    """Remove URL user information from pip output before reporting errors."""
    return re.sub(r"(?i)(https?://)[^/@\s]+@", r"\1***@", value)
