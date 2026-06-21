"""Install packaged or bundled plugins through Orac-owned lifecycle controls."""
# Author: Clive Bostock
# Date: 07-Jun-2026
# Description: Orchestrates plugin validation, dependencies, database deployment, and readiness.

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any, Protocol

from lib.fsutils import project_home
from model.plugin_apex_installation import DockerPluginApexAppInstaller
from model.plugin_apex_installation import PluginApexAppInstallError
from model.plugin_apex_installation import PluginApexAppInstallResult
from model.plugin_apex_installation import PluginApexAppInstaller
from model.plugin_config import PluginConfigManager
from model.plugin_database_deployment import PluginDatabaseDeployer
from model.plugin_dependencies import PluginDependencyInstaller
from model.plugin_dependencies import dependency_fingerprint
from model.plugin_dependencies import validate_declared_imports
from model.plugin_package import PluginPackage
from model.plugin_package import PluginPackageBuilder
from model.plugin_package import PluginPackageReader
from model.plugin_package import source_package
from model.plugin_routing.discovery import PluginDiscovery
from model.plugin_routing.models import PluginApexApp
from model.plugin_routing.models import PluginManifest
from model.plugin_registry import PluginApexAppRegistryStore
from model.plugin_registry import PluginRegistryStore
from model.plugin_runtime import load_plugin_class
from model.plugin_runtime import load_plugin_service_class
from model.plugin_secret_vault import PluginPatVaultStore


class PluginInstallationError(RuntimeError):
    """Raised when a plugin installation cannot complete safely."""


@dataclass(frozen=True)
class PluginInstallResult:
    """Summarise one plugin installation attempt."""

    plugin_id: str
    version: str
    status: str
    enabled: bool
    installed_path: Path | None
    message: str


class PluginRegistryWriter(Protocol):
    """Persistence boundary used by the installer for registry state."""

    def record(self, values: dict[str, Any]) -> None:
        """Create or update the current registry row for a plugin."""

    def get(self, plugin_id: str) -> dict[str, Any] | None:
        """Return the current registry row when available."""


class PluginApexAppRegistryWriter(Protocol):
    """Persistence boundary used by the installer for plugin APEX apps."""

    def record(self, values: dict[str, Any]) -> None:
        """Create or update one plugin APEX app registry row."""


class PluginInstaller:
    """Coordinate plugin packaging and installation into Orac-managed paths."""

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        managed_root: Path | None = None,
        config_root: Path | None = None,
        dependency_installer: PluginDependencyInstaller | None = None,
        database_deployer: PluginDatabaseDeployer | None = None,
        package_reader: PluginPackageReader | None = None,
        registry: PluginRegistryWriter | None = None,
        apex_app_installer: PluginApexAppInstaller | None = None,
        apex_app_registry: PluginApexAppRegistryWriter | None = None,
        logger: Any | None = None,
        keep_failed_staging: bool = False,
    ) -> None:
        """Initialise an Orac plugin installer with injectable side effects."""
        self.project_root = Path(project_root or project_home()).resolve()
        self.managed_root = Path(
            managed_root or self.project_root / "var" / "plugins"
        ).resolve()
        self.config_root = Path(
            config_root or Path("~/.Orac/plugin_config").expanduser()
        ).resolve()
        self._dependency_installer = dependency_installer or PluginDependencyInstaller()
        self._database_deployer = database_deployer or PluginDatabaseDeployer(logger=logger)
        self._package_reader = package_reader or PluginPackageReader()
        self._registry = registry or PluginRegistryStore(logger=logger)
        self._apex_app_installer = apex_app_installer or DockerPluginApexAppInstaller(
            logger=logger
        )
        self._apex_app_registry = apex_app_registry or PluginApexAppRegistryStore(
            logger=logger
        )
        self._logger = logger
        self._keep_failed_staging = keep_failed_staging

    def package(self, source_dir: Path, output_dir: Path) -> Path:
        """Build a validated distribution archive from a source plugin."""
        return PluginPackageBuilder().package(source_dir, output_dir)

    def install_archive(self, archive_path: Path) -> PluginInstallResult:
        """Install one plugin distribution archive."""
        with self._staging_directory() as staging:
            package = self._package_reader.extract(archive_path, staging / "package")
            return self._install(package, staging)

    def install_source(
        self,
        source_dir: Path,
        *,
        source_type: str = "source",
    ) -> PluginInstallResult:
        """Install one bundled or development source plugin."""
        package = source_package(source_dir)
        package = PluginPackage(
            manifest=package.manifest,
            package_root=package.package_root,
            plugin_dir=package.plugin_dir,
            package_hash=package.package_hash,
            source_type=source_type,
            source_ref=package.source_ref,
        )
        with self._staging_directory() as staging:
            return self._install(package, staging)

    def install_bundled(self, plugin_id: str) -> PluginInstallResult:
        """Install one plugin from the repository's bundled plugin root."""
        return self.install_source(
            self.project_root / "plugins" / plugin_id,
            source_type="bundled",
        )

    def install_all_bundled(self) -> list[PluginInstallResult]:
        """Install every valid bundled manifest in deterministic order."""
        manifests, errors = PluginDiscovery(self.project_root / "plugins").discover()
        if errors:
            raise PluginInstallationError(
                "Bundled plugin discovery failed: " + "; ".join(errors)
            )
        return [self.install_bundled(manifest.plugin_id) for manifest in manifests]

    def status(self, plugin_id: str) -> dict[str, Any] | None:
        """Return the current persisted installation state for one plugin."""
        return self._registry.get(plugin_id)

    def check(self, plugin_id: str) -> PluginInstallResult:
        """Re-run non-mutating readiness checks for an installed plugin."""
        row = self._registry.get(plugin_id)
        if row is None:
            raise PluginInstallationError(f"Plugin '{plugin_id}' is not registered.")
        installed_path = Path(str(row.get("installed_path") or ""))
        manifest = PluginDiscovery(installed_path).load_manifest(
            installed_path / "manifest.json",
            plugin_dir=installed_path / "plugin",
            enforce_filename=False,
        )
        config_result = PluginConfigManager(
            manifest,
            config_path=Path(str(row.get("config_path") or "")),
            logger=self._logger,
        ).validate()
        if not config_result.eligible:
            raise PluginInstallationError(config_result.message)
        missing_secrets = self._missing_required_secrets(manifest)
        if missing_secrets:
            raise PluginInstallationError(
                "Required plugin secrets are missing: " + ", ".join(missing_secrets)
            )
        validate_declared_imports(
            manifest.plugin_dir,
            manifest.python_dependencies,
            plugin_id=manifest.plugin_id,
        )
        self._readiness_check(manifest)
        return PluginInstallResult(
            plugin_id=plugin_id,
            version=manifest.version,
            status="success",
            enabled=bool(str(row.get("enabled", "N")).upper() == "Y"),
            installed_path=installed_path,
            message="Plugin installation passed non-starting readiness checks.",
        )

    def _install(self, package: PluginPackage, staging: Path) -> PluginInstallResult:
        """Run all required installation gates for one validated package."""
        source_manifest = package.manifest
        candidate_root = staging / "candidate"
        candidate_plugin_dir = candidate_root / "plugin"
        candidate_root.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_manifest.manifest_path, candidate_root / "manifest.json")
        shutil.copytree(
            package.plugin_dir,
            candidate_plugin_dir,
            ignore=shutil.ignore_patterns(
                "plugin.ini",
                "__pycache__",
                "*.pyc",
                ".venv",
                "venv",
                ".git",
            ),
        )
        manifest = PluginDiscovery(candidate_root).load_manifest(
            candidate_root / "manifest.json",
            plugin_dir=candidate_plugin_dir,
            enforce_filename=False,
        )
        validate_declared_imports(
            candidate_plugin_dir,
            manifest.python_dependencies,
            plugin_id=manifest.plugin_id,
        )
        config_path = self._initialise_config(package, manifest)
        config_result = PluginConfigManager(
            manifest,
            config_path=config_path,
            logger=self._logger,
        ).validate()
        if not config_result.eligible:
            return self._failure(
                manifest,
                package,
                "configuration_failed",
                config_result.message,
                configuration_status=config_result.status,
            )
        missing_secrets = self._missing_required_secrets(manifest)
        if missing_secrets:
            keys = ", ".join(missing_secrets)
            return self._failure(
                manifest,
                package,
                "secret_failed",
                "Required plugin secrets are missing: "
                f"{keys}. Run bin/plugin-pat-mgr.sh --plugin "
                f"{manifest.plugin_id} --list-expected.",
                configuration_status="success",
            )

        try:
            previous = self._registry.get(manifest.plugin_id)
            fingerprint = dependency_fingerprint(manifest.python_dependencies)
            if (
                previous
                and previous.get("dependency_fingerprint") == fingerprint
                and previous.get("dependency_status") in {"success", "not_required"}
                and hasattr(self._dependency_installer, "check")
            ):
                dependency_result = self._dependency_installer.check(
                    manifest.python_dependencies
                )
            else:
                dependency_result = self._dependency_installer.install(
                    manifest.python_dependencies
                )
        except Exception as exc:
            return self._failure(
                manifest,
                package,
                "dependency_failed",
                str(exc),
                configuration_status="success",
            )

        database_result = self._database_deployer.deploy_if_needed(manifest)
        if not database_result.eligible:
            return self._failure(
                manifest,
                package,
                "database_failed",
                database_result.message,
                configuration_status="success",
                dependency_status=dependency_result.status,
                database_status=database_result.status,
            )
        try:
            self._readiness_check(manifest)
        except Exception as exc:
            return self._failure(
                manifest,
                package,
                "readiness_failed",
                str(exc),
                configuration_status="success",
                dependency_status=dependency_result.status,
                database_status=database_result.status,
            )

        installed_path, previous_path = self._activate_candidate(candidate_root, manifest)
        active_manifest = replace(
            manifest,
            manifest_path=installed_path / "manifest.json",
            plugin_dir=installed_path / "plugin",
        )
        try:
            self._install_apex_apps(active_manifest, package)
        except PluginInstallationError as exc:
            self._rollback_activation(installed_path, previous_path)
            return self._failure(
                manifest,
                package,
                "apex_failed",
                str(exc),
                configuration_status="success",
                dependency_status=dependency_result.status,
                database_status=database_result.status,
            )
        values = self._registry_values(
            active_manifest,
            package,
            installed_path,
            config_path,
            install_status="success",
            configuration_status=(
                "success" if manifest.configuration_required else "not_required"
            ),
            dependency_status=dependency_result.status,
            database_status=database_result.status,
            readiness_status="success",
            enabled=True,
        )
        try:
            self._record(values)
        except PluginInstallationError:
            self._rollback_activation(installed_path, previous_path)
            raise
        self._finalise_activation(previous_path)
        self._log_info(
            f"Plugin '{active_manifest.plugin_id}' {active_manifest.version} installed and enabled."
        )
        return PluginInstallResult(
            plugin_id=active_manifest.plugin_id,
            version=active_manifest.version,
            status="success",
            enabled=True,
            installed_path=installed_path,
            message="Plugin installed and passed readiness checks.",
        )

    def _initialise_config(self, package: PluginPackage, manifest: PluginManifest) -> Path:
        """Create external mutable configuration once without overwriting it."""
        plugin_config_dir = self.config_root / manifest.plugin_id
        plugin_config_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        config_path = plugin_config_dir / "plugin.ini"
        if config_path.exists():
            return config_path
        source_config = package.plugin_dir / "plugin.ini"
        template = package.plugin_dir / "plugin.ini.example"
        selected = source_config if source_config.is_file() else template
        if selected.is_file():
            shutil.copy2(selected, config_path)
            config_path.chmod(0o600)
        return config_path

    @staticmethod
    def _missing_required_secrets(manifest: PluginManifest) -> tuple[str, ...]:
        """Return required secret keys absent from the encrypted PAT vault."""
        if manifest.secrets is None:
            return ()
        store = PluginPatVaultStore(manifests=(manifest,))
        return tuple(
            secret.key
            for secret in manifest.secrets.keys
            if secret.required and not store.check_secret(manifest.plugin_id, secret.key)
        )

    @staticmethod
    def _readiness_check(manifest: PluginManifest) -> None:
        """Import declared entry points without starting plugin services."""
        if manifest.entry_point:
            plugin_class = load_plugin_class(manifest)
            if not callable(getattr(plugin_class, "execute", None)):
                raise PluginInstallationError(
                    f"Plugin '{manifest.plugin_id}' entry point does not expose execute()."
                )
        if manifest.service_runtime is not None:
            service_class = load_plugin_service_class(manifest)
            required_method = (
                "tick"
                if manifest.service_runtime.execution_model == "scheduled"
                else "run"
            )
            if not callable(getattr(service_class, required_method, None)):
                raise PluginInstallationError(
                    f"Plugin service '{manifest.plugin_id}' does not expose "
                    f"{required_method}()."
                )
            health_check = manifest.service_runtime.health_check
            if health_check.enabled and not callable(
                getattr(service_class, health_check.method or "health", None)
            ):
                raise PluginInstallationError(
                    f"Plugin service '{manifest.plugin_id}' does not expose its "
                    "declared health-check method."
                )
        PluginInstaller._validate_ui_assets(manifest)
        PluginInstaller._validate_apex_app_assets(manifest)

    @staticmethod
    def _validate_ui_assets(manifest: PluginManifest) -> None:
        """Verify required plugin UI assets are present without installing them."""
        if manifest.ui is None:
            return
        for surface in manifest.ui.surfaces:
            if surface.target == "apex" and surface.apex is not None:
                if surface.apex.install_required and not surface.apex.app_export:
                    raise PluginInstallationError(
                        f"Plugin UI surface '{surface.surface_id}' requires an "
                        "APEX export but does not declare apex.app_export."
                    )
                if surface.apex.install_required and surface.apex.app_export:
                    export_path = manifest.plugin_dir / surface.apex.app_export
                    if not export_path.is_file():
                        raise PluginInstallationError(
                            f"Plugin UI surface '{surface.surface_id}' declares "
                            f"missing APEX export: {surface.apex.app_export}"
                        )

    @staticmethod
    def _validate_apex_app_assets(manifest: PluginManifest) -> None:
        """Verify declared plugin APEX app exports are present."""
        for app in manifest.apex_apps:
            export_path = manifest.plugin_dir / app.app_export
            if app.install_required and not export_path.is_file():
                raise PluginInstallationError(
                    f"Plugin APEX app '{app.alias}' declares missing export: "
                    f"{app.app_export}"
                )

    def _install_apex_apps(
        self,
        manifest: PluginManifest,
        package: PluginPackage,
    ) -> None:
        """Install and register plugin-supplied APEX apps."""
        for app in manifest.apex_apps:
            if app.install_required:
                try:
                    result = self._apex_app_installer.install(manifest, app)
                except PluginApexAppInstallError as exc:
                    self._record_apex_app(
                        self._apex_app_values(
                            manifest,
                            app,
                            package,
                            install_status="failed",
                            install_log=str(exc),
                            last_error_message=str(exc),
                        )
                    )
                    raise PluginInstallationError(str(exc)) from exc
                self._record_apex_app(
                    self._apex_app_values(
                        manifest,
                        app,
                        package,
                        result=result,
                        install_status=result.install_status,
                        install_log=result.install_log,
                        last_error_message=result.last_error_message,
                    )
                )
            else:
                self._record_apex_app(
                    self._apex_app_values(
                        manifest,
                        app,
                        package,
                        install_status="metadata_only",
                        install_log=None,
                    )
                )

    def _activate_candidate(
        self,
        candidate_root: Path,
        manifest: PluginManifest,
    ) -> tuple[Path, Path | None]:
        """Activate a candidate while retaining any prior version for rollback."""
        destination = self.managed_root / "installed" / manifest.plugin_id / manifest.version
        destination.parent.mkdir(parents=True, exist_ok=True)
        incoming = destination.parent / f".{manifest.version}.incoming"
        backup = destination.parent / f".{manifest.version}.previous"
        shutil.rmtree(incoming, ignore_errors=True)
        shutil.rmtree(backup, ignore_errors=True)
        shutil.copytree(candidate_root, incoming)
        if destination.exists():
            destination.rename(backup)
        incoming.rename(destination)
        return destination, backup if backup.exists() else None

    @staticmethod
    def _finalise_activation(previous_path: Path | None) -> None:
        """Remove the retained previous installation after registry success."""
        if previous_path is not None:
            shutil.rmtree(previous_path, ignore_errors=True)

    @staticmethod
    def _rollback_activation(destination: Path, previous_path: Path | None) -> None:
        """Restore the prior installation after a late registry failure."""
        shutil.rmtree(destination, ignore_errors=True)
        if previous_path is not None and previous_path.exists():
            previous_path.rename(destination)

    def _failure(
        self,
        manifest: PluginManifest,
        package: PluginPackage,
        status: str,
        message: str,
        *,
        configuration_status: str = "failed",
        dependency_status: str = "not_run",
        database_status: str = "not_run",
    ) -> PluginInstallResult:
        """Record a failed installation without activating the candidate."""
        self._record(
            self._registry_values(
                manifest,
                package,
                None,
                self.config_root / manifest.plugin_id / "plugin.ini",
                install_status=status,
                configuration_status=configuration_status,
                dependency_status=dependency_status,
                database_status=database_status,
                readiness_status="failed" if status == "readiness_failed" else "not_run",
                enabled=False,
                last_error_message=message,
            )
        )
        self._log_error(f"Plugin '{manifest.plugin_id}' installation failed: {message}")
        return PluginInstallResult(
            plugin_id=manifest.plugin_id,
            version=manifest.version,
            status=status,
            enabled=False,
            installed_path=None,
            message=message,
        )

    def _registry_values(
        self,
        manifest: PluginManifest,
        package: PluginPackage,
        installed_path: Path | None,
        config_path: Path,
        *,
        install_status: str,
        configuration_status: str,
        dependency_status: str,
        database_status: str,
        readiness_status: str,
        enabled: bool,
        last_error_message: str | None = None,
    ) -> dict[str, Any]:
        """Build registry values without secret material."""
        return {
            "plugin_id": manifest.plugin_id,
            "plugin_name": manifest.name,
            "plugin_version": manifest.version,
            "runtime_mode": manifest.runtime_mode,
            "manifest_hash": manifest.manifest_hash,
            "package_hash": package.package_hash,
            "install_source_type": package.source_type,
            "install_source_ref": package.source_ref,
            "installed_path": str(installed_path) if installed_path else None,
            "config_path": str(config_path),
            "capabilities_summary": json.dumps(manifest.capabilities),
            "entitlements_summary": json.dumps(manifest.entitlements),
            "database_schemas_summary": json.dumps(
                [schema.schema_name for schema in manifest.database_schemas]
            ),
            "dependency_declarations": json.dumps(manifest.python_dependencies),
            "dependency_fingerprint": dependency_fingerprint(
                manifest.python_dependencies
            ),
            "install_status": install_status,
            "configuration_status": configuration_status,
            "dependency_status": dependency_status,
            "database_status": database_status,
            "readiness_status": readiness_status,
            "enabled": enabled,
            "last_error_code": install_status if not enabled else None,
            "last_error_message": last_error_message,
        }

    def _apex_app_values(
        self,
        manifest: PluginManifest,
        app: PluginApexApp,
        package: PluginPackage,
        *,
        result: PluginApexAppInstallResult | None = None,
        install_status: str,
        install_log: str | None,
        last_error_message: str | None = None,
    ) -> dict[str, Any]:
        """Build plugin APEX app registry values."""
        return {
            "plugin_id": manifest.plugin_id,
            "plugin_version": manifest.version,
            "app_alias": app.alias,
            "workspace": app.workspace,
            "parsing_schema": app.parsing_schema,
            "app_export": app.app_export,
            "declared_application_id": app.application_id,
            "installed_app_id": result.installed_app_id if result else None,
            "entry_page_id": app.entry_page_id,
            "label": app.label,
            "description": app.description,
            "required_roles": json.dumps(app.required_roles),
            "icon": app.icon,
            "card_title": app.card_title,
            "card_subtitle": app.card_subtitle,
            "install_status": install_status,
            "install_log": install_log,
            "last_error_message": last_error_message,
            "enabled": app.enabled,
            "package_hash": package.package_hash,
        }

    def _record(self, values: dict[str, Any]) -> None:
        """Persist registry state when a registry adapter is configured."""
        if self._registry is None:
            return
        try:
            self._registry.record(values)
        except Exception as exc:
            raise PluginInstallationError(
                f"Unable to persist plugin registry state: {exc}"
            ) from exc

    def _record_apex_app(self, values: dict[str, Any]) -> None:
        """Persist plugin APEX app registry state."""
        if self._apex_app_registry is None:
            return
        try:
            self._apex_app_registry.record(values)
        except Exception as exc:
            raise PluginInstallationError(
                f"Unable to persist plugin APEX app registry state: {exc}"
            ) from exc

    def _staging_directory(self):
        """Return a temporary staging context below the managed root."""
        staging_root = self.managed_root / "staging"
        staging_root.mkdir(parents=True, exist_ok=True)
        if self._keep_failed_staging:
            path = Path(tempfile.mkdtemp(prefix="install-", dir=staging_root))
            return _RetainedDirectory(path)
        return _TemporaryPathDirectory(staging_root)

    def _log_info(self, message: str) -> None:
        if self._logger and hasattr(self._logger, "log_info"):
            self._logger.log_info(message)

    def _log_error(self, message: str) -> None:
        if self._logger and hasattr(self._logger, "log_error"):
            self._logger.log_error(message)


class _RetainedDirectory:
    """Context manager retaining a staging path for installation debugging."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def __enter__(self) -> Path:
        return self._path

    def __exit__(self, *_args: object) -> None:
        return None


class _TemporaryPathDirectory:
    """Temporary directory context returning a ``Path`` instance."""

    def __init__(self, parent: Path) -> None:
        self._temporary = tempfile.TemporaryDirectory(prefix="install-", dir=parent)

    def __enter__(self) -> Path:
        return Path(self._temporary.__enter__())

    def __exit__(self, *args: object) -> None:
        self._temporary.__exit__(*args)
