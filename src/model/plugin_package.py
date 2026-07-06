"""Build, inspect, and stage transportable Orac plugin packages."""
# Author: Clive Bostock
# Date: 07-Jun-2026
# Description: Provides deterministic plugin archives and safe extraction.

from __future__ import annotations

from dataclasses import dataclass
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile
from typing import BinaryIO

from model.plugin_dependencies import validate_requirements_mirror
from model.plugin_routing.discovery import PluginDiscovery
from model.plugin_routing.models import PluginManifest


DEFAULT_MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
DEFAULT_MAX_MEMBER_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_MEMBERS = 10_000


class PluginPackageError(RuntimeError):
    """Raised when a plugin package is malformed or unsafe."""


@dataclass(frozen=True)
class PluginPackage:
    """Describe a validated plugin package or source tree."""

    manifest: PluginManifest
    package_root: Path
    plugin_dir: Path
    package_hash: str
    source_type: str
    source_ref: str


class PluginPackageBuilder:
    """Build deterministic plugin distribution archives."""

    def package(self, source_dir: Path, output_dir: Path) -> Path:
        """Validate and package a bundled/development plugin source directory."""
        source = Path(source_dir).resolve()
        manifest_path = source.parent / f"{source.name}.json"
        if not manifest_path.is_file():
            raise PluginPackageError(
                f"Plugin manifest not found beside source directory: {manifest_path}"
            )
        manifest = PluginDiscovery(source.parent).load_manifest(manifest_path)
        validate_entry_point_files(manifest)
        validate_requirements_mirror(
            source / "requirements.txt",
            manifest.python_dependencies,
        )
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        archive_path = output / (
            f"orac-plugin-{manifest.plugin_id}-{manifest.version}.tar.gz"
        )
        entries = self._source_entries(manifest)
        with archive_path.open("wb") as raw_output:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=raw_output,
                compresslevel=9,
                mtime=0,
            ) as compressed:
                with tarfile.open(fileobj=compressed, mode="w") as archive:
                    self._add_file(
                        archive,
                        manifest.manifest_path,
                        "manifest.json",
                    )
                    for source_path, archive_name in entries:
                        self._add_file(archive, source_path, archive_name)
        return archive_path

    @staticmethod
    def _source_entries(manifest: PluginManifest) -> list[tuple[Path, str]]:
        """Return deterministic package inputs, excluding mutable/generated files."""
        ignored_parts = {"__pycache__", ".venv", "venv", ".git", "logs"}
        ignored_suffixes = {".pyc", ".pyo", ".log"}
        entries: list[tuple[Path, str]] = []
        for path in sorted(manifest.plugin_dir.rglob("*")):
            relative = path.relative_to(manifest.plugin_dir)
            if path.is_dir() or any(part in ignored_parts for part in relative.parts):
                continue
            if path.suffix in ignored_suffixes or path.name == "plugin.ini":
                continue
            entries.append((path, f"plugin/{relative.as_posix()}"))
        readme = manifest.plugin_dir / "README.md"
        if readme.is_file():
            entries = [item for item in entries if item[0] != readme]
            entries.append((readme, "README.md"))
        requirements = manifest.plugin_dir / "requirements.txt"
        if requirements.is_file():
            entries = [item for item in entries if item[0] != requirements]
            entries.append((requirements, "requirements.txt"))
        return sorted(entries, key=lambda item: item[1])

    @staticmethod
    def _add_file(archive: tarfile.TarFile, path: Path, archive_name: str) -> None:
        """Add one file with reproducible metadata."""
        data = path.read_bytes()
        info = tarfile.TarInfo(archive_name)
        info.size = len(data)
        info.mtime = 0
        info.uid = 0
        info.gid = 0
        info.uname = ""
        info.gname = ""
        info.mode = 0o644
        archive.addfile(info, io.BytesIO(data))


class PluginPackageReader:
    """Validate and extract untrusted plugin tarballs into controlled staging."""

    def __init__(
        self,
        *,
        max_archive_bytes: int = DEFAULT_MAX_ARCHIVE_BYTES,
        max_member_bytes: int = DEFAULT_MAX_MEMBER_BYTES,
        max_members: int = DEFAULT_MAX_MEMBERS,
    ) -> None:
        self._max_archive_bytes = max_archive_bytes
        self._max_member_bytes = max_member_bytes
        self._max_members = max_members

    def extract(self, archive_path: Path, staging_dir: Path) -> PluginPackage:
        """Inspect and safely extract a plugin package."""
        archive = Path(archive_path).resolve()
        if not archive.is_file():
            raise PluginPackageError(f"Plugin package does not exist: {archive}")
        if not archive.name.endswith(".tar.gz"):
            raise PluginPackageError("Plugin package must use the .tar.gz format")
        if archive.stat().st_size > self._max_archive_bytes:
            raise PluginPackageError("Plugin package exceeds the configured size limit")

        destination = Path(staging_dir).resolve()
        destination.mkdir(parents=True, exist_ok=True)
        try:
            with tarfile.open(archive, mode="r:gz") as package:
                members = package.getmembers()
                self._validate_members(members)
                for member in members:
                    if member.isdir():
                        (destination / member.name).mkdir(parents=True, exist_ok=True)
                        continue
                    extracted = package.extractfile(member)
                    if extracted is None:
                        raise PluginPackageError(
                            f"Unable to read package member: {member.name}"
                        )
                    target = destination / member.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    self._copy_member(extracted, target)
        except (tarfile.TarError, OSError) as exc:
            raise PluginPackageError(f"Unable to extract plugin package: {exc}") from exc

        manifest_path = destination / "manifest.json"
        plugin_dir = destination / "plugin"
        if not manifest_path.is_file() or not plugin_dir.is_dir():
            raise PluginPackageError(
                "Plugin package must contain manifest.json and plugin/"
            )
        manifest = PluginDiscovery(destination).load_manifest(
            manifest_path,
            plugin_dir=plugin_dir,
            enforce_filename=False,
        )
        validate_entry_point_files(manifest)
        validate_requirements_mirror(
            destination / "requirements.txt",
            manifest.python_dependencies,
        )
        return PluginPackage(
            manifest=manifest,
            package_root=destination,
            plugin_dir=plugin_dir,
            package_hash=_sha256_file(archive),
            source_type="tarball",
            source_ref=str(archive),
        )

    def _validate_members(self, members: list[tarfile.TarInfo]) -> None:
        """Reject archive members that could escape or abuse staging."""
        if len(members) > self._max_members:
            raise PluginPackageError("Plugin package contains too many members")
        names: set[str] = set()
        total_size = 0
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise PluginPackageError(
                    f"Unsafe package path rejected: {member.name}"
                )
            if member.issym() or member.islnk():
                raise PluginPackageError(
                    f"Package links are not supported: {member.name}"
                )
            if not (member.isfile() or member.isdir()):
                raise PluginPackageError(
                    f"Unsupported package member type: {member.name}"
                )
            if member.size > self._max_member_bytes:
                raise PluginPackageError(
                    f"Package member exceeds size limit: {member.name}"
                )
            total_size += member.size
            if total_size > self._max_archive_bytes:
                raise PluginPackageError(
                    "Plugin package extracted content exceeds the configured size limit"
                )
            if member.name in names:
                raise PluginPackageError(f"Duplicate package member: {member.name}")
            names.add(member.name)

    @staticmethod
    def _copy_member(source: BinaryIO, target: Path) -> None:
        """Copy an already validated regular file into staging."""
        with target.open("wb") as output:
            shutil.copyfileobj(source, output)
        target.chmod(0o644)


def source_package(source_dir: Path) -> PluginPackage:
    """Load a bundled/development source plugin without copying it."""
    source = Path(source_dir).resolve()
    manifest_path = source.parent / f"{source.name}.json"
    manifest = PluginDiscovery(source.parent).load_manifest(manifest_path)
    validate_entry_point_files(manifest)
    validate_requirements_mirror(
        source / "requirements.txt",
        manifest.python_dependencies,
    )
    return PluginPackage(
        manifest=manifest,
        package_root=source.parent,
        plugin_dir=source,
        package_hash=_source_hash(manifest),
        source_type="source",
        source_ref=str(source),
    )


def _source_hash(manifest: PluginManifest) -> str:
    """Hash manifest and immutable source files for source installations."""
    digest = hashlib.sha256(manifest.manifest_path.read_bytes())
    for path in sorted(manifest.plugin_dir.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.name == "plugin.ini":
            continue
        digest.update(path.relative_to(manifest.plugin_dir).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for one file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_entry_point_files(manifest: PluginManifest) -> None:
    """Require modules declared by manifest entry points to exist in the package."""
    entry_points = [manifest.entry_point]
    entry_points.extend(
        service_runtime.entry_point for service_runtime in manifest.service_runtimes
    )
    for entry_point in entry_points:
        if not entry_point:
            continue
        module_name = entry_point.split(":", 1)[0]
        module_path = manifest.plugin_dir.joinpath(*module_name.split("."))
        if not module_path.with_suffix(".py").is_file() and not (
            module_path / "__init__.py"
        ).is_file():
            raise PluginPackageError(
                f"Declared entry-point module does not exist: {entry_point}"
            )
