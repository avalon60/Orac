"""Install packaged or bundled plugins through Orac-owned lifecycle controls."""

# Author: Clive Bostock
# Date: 07-Jun-2026
# Description: Orchestrates plugin validation, dependencies, database deployment, and readiness.

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
from typing import Any, Callable, Protocol
import uuid

from lib.fsutils import project_home
from model.plugin_apex_installation import DockerPluginApexAppInstaller
from model.plugin_apex_installation import PluginApexAppInstallError
from model.plugin_apex_installation import PluginApexAppInstallResult
from model.plugin_apex_installation import PluginApexAppInstaller
from model.plugin_config import PluginConfigManager
from model.plugin_command_dependencies import PluginCommandDependencyChecker
from model.plugin_command_dependencies import PluginCommandDependencyResult
from model.plugin_command_dependencies import command_dependency_fingerprint
from model.plugin_database_deployment import PluginDatabaseDeployer
from model.plugin_dependencies import PluginDependencyInstaller
from model.plugin_dependencies import dependency_fingerprint
from model.plugin_dependencies import validate_declared_imports
from model.plugin_package import PluginPackage
from model.plugin_package import PluginPackageBuilder
from model.plugin_package import PluginPackageReader
from model.plugin_package import materialise_repository_plugin
from model.plugin_package import source_package
from model.plugin_package_layout import PLUGIN_DIRECTORY_BOM
from model.plugin_package_layout import PLUGIN_ROOT_FILE_BOM
from model.plugin_package_layout import claimed_source_directories
from model.plugin_package_layout import is_ignored_source_file
from model.plugin_package_layout import source_root_for_spec
from model.plugin_routing.discovery import PluginDiscovery
from model.plugin_routing.models import PluginApexApp
from model.plugin_routing.models import PluginManifest
from model.plugin_registry import PluginApexAppRegistryStore
from model.plugin_registry import PluginRegistryStore
from model.plugin_registry import inspect_registered_plugin_artifact
from model.plugin_runtime import load_plugin_class
from model.plugin_runtime import load_plugin_interceptor_class
from model.plugin_runtime import load_plugin_service_class
from model.plugin_runtime import instantiate_plugin_interceptor
from model.plugin_secret_vault import PluginPatVaultStore
from model.plugin_service_manager import PluginServiceManager
from model.plugin_execution_lock import PluginExecutionLock
from model.plugin_service_lifecycle import PluginServiceLifecycleStore


class PluginInstallationError(RuntimeError):
    """Raised when a plugin installation cannot complete safely."""


class PluginRemovalConfirmationError(PluginInstallationError):
    """Raised before mutation when removal has not been explicitly confirmed."""


@dataclass(frozen=True)
class PluginRemovalResult:
    """Report a preview, completed removal, or recovered completed response."""

    plugin_id: str
    status: str
    removal_id: str | None
    inventory: dict[str, Any]
    message: str


@dataclass(frozen=True)
class PluginInstallResult:
    """Summarise one plugin installation attempt."""

    plugin_id: str
    version: str
    status: str
    enabled: bool
    installed_path: Path | None
    message: str
    warnings: tuple[str, ...] = ()


class PluginRegistryWriter(Protocol):
    """Persistence boundary used by the installer for registry state."""

    def record(self, values: dict[str, Any]) -> None:
        """Create or update the current registry row for a plugin."""

    def get(self, plugin_id: str) -> dict[str, Any] | None:
        """Return the current registry row when available."""

    def list_all(self) -> list[dict[str, Any]]:
        """Return all current registry rows."""

    def record_command_status(
        self,
        plugin_id: str,
        status: str,
        report_json: str,
    ) -> None:
        """Persist a fresh install, check, service, or conversion probe result."""

    def set_enabled(self, plugin_id: str, *, enabled: bool) -> None:
        """Change enablement without recreating an absent installation."""

    def removal_history(self, plugin_id: str) -> list[dict[str, Any]]:
        """Read inert removal history, including an incomplete operation."""

    def begin_removal(
        self,
        *,
        plugin_id: str,
        registry_id: int,
        removal_id: str,
        keep_schema: bool,
        database_identity: str,
        inventory: dict[str, Any],
        confirmed_by: str,
    ) -> None:
        """Atomically disable and fence an explicitly authorised installation.

        The caller must hold maintenance access and validate the bounded
        inventory before invoking this mutation. Approval is not inferred here.
        """

    def checkpoint_removal(
        self,
        *,
        removal_id: str,
        registry_id: int,
        checkpoints: dict[str, Any],
        external_complete: bool,
        files_complete: bool,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Persist verified cleanup progress for exactly one fenced target."""

    def finalize_removal(self, *, removal_id: str, registry_id: int) -> None:
        """Commit Core cleanup and registry deletion as one guarded transaction."""


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
        command_dependency_checker: PluginCommandDependencyChecker | None = None,
        database_deployer: PluginDatabaseDeployer | None = None,
        package_reader: PluginPackageReader | None = None,
        registry: PluginRegistryWriter | None = None,
        apex_app_installer: PluginApexAppInstaller | None = None,
        apex_app_registry: PluginApexAppRegistryWriter | None = None,
        service_manager: Any | None = None,
        service_lifecycle: Any | None = None,
        secret_vault: PluginPatVaultStore | None = None,
        audit_adapter: Any | None = None,
        logger: Any | None = None,
        keep_failed_staging: bool = False,
    ) -> None:
        """Initialise an Orac plugin installer with injectable side effects."""
        self.project_root = Path(project_root or project_home()).resolve()
        self.managed_root = (
            Path(managed_root or self.project_root / "var" / "plugins")
            .expanduser()
            .absolute()
        )
        self.config_root = (
            Path(config_root or Path("~/.Orac/plugin_config").expanduser())
            .expanduser()
            .absolute()
        )
        self._dependency_installer = dependency_installer or PluginDependencyInstaller()
        self._command_dependency_checker = (
            command_dependency_checker or PluginCommandDependencyChecker()
        )
        self._database_deployer = database_deployer or PluginDatabaseDeployer(
            logger=logger
        )
        self._package_reader = package_reader or PluginPackageReader()
        self._registry = registry or PluginRegistryStore(logger=logger)
        self._apex_app_installer = apex_app_installer or DockerPluginApexAppInstaller(
            logger=logger
        )
        self._default_apex_app_installer = apex_app_installer is None
        self._apex_app_registry = apex_app_registry or PluginApexAppRegistryStore(
            logger=logger
        )
        self._service_manager = service_manager
        self._service_lifecycle = service_lifecycle or PluginServiceLifecycleStore()
        self._secret_vault = secret_vault
        self._audit_adapter = audit_adapter
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

    def history(self, plugin_id: str) -> list[dict[str, Any]]:
        """Return explicit historical removal records, without reviving them."""
        return self._registry.removal_history(plugin_id)

    def disable(self, plugin_id: str) -> None:
        """Disable the existing registration while retaining its resources."""
        with PluginExecutionLock(self.project_root, exclusive=True):
            self._registry.set_enabled(plugin_id, enabled=False)

    def enable(self, plugin_id: str) -> None:
        """Validate readiness before enabling an existing, unfenced registration."""
        with PluginExecutionLock(self.project_root, exclusive=True):
            self.check(plugin_id)
            self._registry.set_enabled(plugin_id, enabled=True)

    def remove(
        self,
        plugin_id: str,
        *,
        keep_schema: bool = False,
        dry_run: bool = False,
        confirmed_by: str | None = None,
        confirm: Callable[[dict[str, Any]], bool] | None = None,
    ) -> PluginRemovalResult:
        """Remove one exact registration under exclusive maintenance access.

        Confirmation receives the bounded preflight inventory. An existing
        operation retains its original authorization and schema disposition.
        Every cleanup failure leaves its disabled registration resumable.
        """
        if not re.fullmatch(r"[a-z][a-z0-9_]*", plugin_id):
            raise PluginInstallationError("Invalid plugin identifier.")
        if type(keep_schema) is not bool or type(dry_run) is not bool:
            raise PluginInstallationError("Removal options must be boolean values.")
        with PluginExecutionLock(self.project_root, exclusive=True):
            return self._remove_locked(
                plugin_id,
                keep_schema=keep_schema,
                dry_run=dry_run,
                confirmed_by=confirmed_by,
                confirm=confirm,
            )

    def _remove_locked(
        self,
        plugin_id: str,
        *,
        keep_schema: bool,
        dry_run: bool,
        confirmed_by: str | None,
        confirm: Callable[[dict[str, Any]], bool] | None,
    ) -> PluginRemovalResult:
        """Run preflight, external cleanup and atomic Core finalization in order."""
        row = self._registry.get(plugin_id)
        history = self.history(plugin_id)
        if row is None:
            completed = next(
                (item for item in history if item.get("completed_on")), None
            )
            return PluginRemovalResult(
                plugin_id,
                "already_removed",
                completed["removal_id"] if completed else None,
                completed["resource_inventory"] if completed else {},
                "No current registration remains.",
            )
        registry_id = int(row["plugin_registry_id"])
        operation = next(
            (item for item in history if item["removal_id"] == row.get("removal_id")),
            None,
        )
        if row.get("removal_id") and operation is None:
            raise PluginInstallationError(
                "Removal fence has no matching durable operation."
            )
        if operation:
            if (
                operation["plugin_registry_id"] != registry_id
                or operation.get("completed_on")
                or (operation["schema_disposition"] == "KEEP") != keep_schema
            ):
                raise PluginInstallationError(
                    "Retry must preserve the original removal target and disposition."
                )
            inventory = operation["resource_inventory"]
            manifest = self._manifest_from_removal_inventory(inventory)
            removal_id = operation["removal_id"]
        else:
            manifest = self._registered_removal_manifest(row)
            inventory = self._removal_inventory(manifest, row, keep_schema=keep_schema)
            removal_id = uuid.uuid4().hex
        self._validate_removal_inventory(inventory, row)
        if dry_run:
            return PluginRemovalResult(
                plugin_id,
                "dry_run",
                row.get("removal_id"),
                inventory,
                "Read-only removal inventory; no cleanup was started.",
            )
        if not operation:
            if (
                not confirmed_by
                or len(confirmed_by) > 128
                or confirm is None
                or not confirm(inventory)
            ):
                raise PluginRemovalConfirmationError(
                    "Removal was not confirmed; no changes were made."
                )
            # Approval binds the displayed inventory, not a newly resolved name.
            if (
                self._removal_inventory(manifest, row, keep_schema=keep_schema)
                != inventory
            ):
                raise PluginInstallationError(
                    "Removal resources changed during confirmation; inspect again."
                )
            self._registry.begin_removal(
                plugin_id=plugin_id,
                registry_id=registry_id,
                removal_id=removal_id,
                keep_schema=keep_schema,
                database_identity=inventory["database"]["database_identity"],
                inventory=inventory,
                confirmed_by=confirmed_by,
            )
        checkpoints = dict(operation.get("checkpoints") or {}) if operation else {}
        external_complete = bool(
            operation and operation.get("external_complete_yn") == "Y"
        )
        files_complete = bool(operation and operation.get("files_complete_yn") == "Y")

        def checkpoint(name: str) -> None:
            checkpoints[name] = True
            self._registry.checkpoint_removal(
                removal_id=removal_id,
                registry_id=registry_id,
                checkpoints=checkpoints,
                external_complete=external_complete,
                files_complete=files_complete,
            )

        try:
            self._assert_services_quiescent(plugin_id)
            if not checkpoints.get("audit_started"):
                self._audit_removal(
                    inventory,
                    removal_id,
                    outcome="started",
                    actor=str(operation["confirmed_by"] if operation else confirmed_by),
                )
                checkpoint("audit_started")
            runner = self._database_deployer.administrative_runner_for(manifest)
            database_identity = inventory["database"]["database_identity"]
            apex = self._removal_apex_installer(runner)
            if not external_complete:
                apex.remove(
                    manifest,
                    plugin_registry_id=registry_id,
                    database_identity=database_identity,
                    removal_id=removal_id,
                )
                checkpoint("apex")
                runner.clean_up_schemas(
                    manifest,
                    plugin_registry_id=registry_id,
                    removal_id=removal_id,
                    database_identity=database_identity,
                    keep_schema=keep_schema,
                )
                external_complete = True
                checkpoint("database")
            verified_schemas = runner.schema_removal_inventory(
                manifest,
                plugin_registry_id=registry_id,
                removal_id=removal_id,
            )
            if verified_schemas["database_identity"] != database_identity or any(
                item.get("state") != "NOT_PROVISIONED"
                and item.get("disposition")
                != ("RETAINED" if keep_schema else "DROPPED")
                for item in verified_schemas["schemas"]
            ):
                raise PluginInstallationError(
                    "Schema cleanup state changed before finalization."
                )
            verified_apps = apex.removal_inventory(
                manifest,
                plugin_registry_id=registry_id,
                database_identity=database_identity,
                removal_id=removal_id,
            )
            if any(
                item.get("receipt") and item.get("present") != 0
                for item in verified_apps
            ):
                raise PluginInstallationError(
                    "An owned APEX application remains after cleanup."
                )
            # A paused operation may outlive a separate credential update. Repeat
            # this idempotent cleanup even when its prior checkpoint was saved.
            vault = self._secret_vault or PluginPatVaultStore(manifests=(manifest,))
            vault.delete_plugin(plugin_id)
            checkpoint("secrets")
            if not files_complete:
                for directory in inventory["directories"]:
                    self._remove_managed_directory(directory)
                    checkpoint("directory:" + directory["kind"])
                self._clean_routing_cache(inventory)
                checkpoint("routing_cache")
                files_complete = True
                checkpoint("files")
            else:
                for directory in inventory["directories"]:
                    if (
                        self._directory_identity(
                            Path(directory["path"]), directory["kind"]
                        )["inode"]
                        is not None
                    ):
                        raise PluginInstallationError(
                            "A managed directory reappeared after cleanup."
                        )
                self._clean_routing_cache(inventory)
            self._registry.finalize_removal(
                removal_id=removal_id, registry_id=registry_id
            )
        except Exception as exc:
            # Recover a lost success response without touching any successor.
            try:
                completed = next(
                    (
                        item
                        for item in self.history(plugin_id)
                        if item["removal_id"] == removal_id and item.get("completed_on")
                    ),
                    None,
                )
            except Exception:
                completed = None
            if completed is None:
                try:
                    self._audit_removal(
                        inventory,
                        removal_id,
                        outcome="failed",
                        actor=str(
                            operation["confirmed_by"] if operation else confirmed_by
                        ),
                    )
                except Exception:
                    pass
                try:
                    self._registry.checkpoint_removal(
                        removal_id=removal_id,
                        registry_id=registry_id,
                        checkpoints=checkpoints,
                        external_complete=external_complete,
                        files_complete=files_complete,
                        error_code="PLUGIN_REMOVAL_INCOMPLETE",
                        error_message="Required cleanup or finalization could not be verified. Resume this operation.",
                    )
                except Exception:
                    pass  # The last committed fence remains authoritative.
                raise PluginInstallationError(
                    f"Removal {removal_id} is incomplete; the plugin remains fenced. "
                    "Inspect the failed resource and resume with the original disposition."
                ) from exc
        return PluginRemovalResult(
            plugin_id,
            "removed",
            removal_id,
            inventory,
            "Plugin removal completed; historical Core knowledge was preserved.",
        )

    def _audit_removal(
        self, inventory: dict[str, Any], removal_id: str, *, outcome: str, actor: str
    ) -> None:
        """Use the existing audit adapter for credential-free management facts."""
        from model.plugin_audit_adapter import PluginAuditAdapter
        from model.plugin_registry import _default_session, _close_quietly

        session = None
        adapter = self._audit_adapter
        try:
            if adapter is None:
                session = _default_session()
                adapter = PluginAuditAdapter(
                    db_session=session, logger=self._logger, strict=True
                )
            adapter.record_lifecycle(
                plugin_id=inventory["plugin_id"],
                plugin_version=inventory["plugin_version"],
                action="remove",
                outcome=outcome,
                actor=actor,
                removal_id=removal_id,
                knowledge_scope_id=inventory["knowledge_scope_id"],
                confirmation=inventory["schema_disposition"],
            )
        finally:
            if session is not None:
                _close_quietly(session)

    def _registered_removal_manifest(self, row: dict[str, Any]) -> PluginManifest:
        """Load the exact registered package only from a managed installation root."""
        plugin_id = str(row["plugin_id"])
        installed = Path(str(row.get("installed_path") or ""))
        allowed = (
            self.managed_root / "installed" / plugin_id,
            self.managed_root / "snapshots" / plugin_id,
        )
        if not installed.is_absolute() or not any(
            installed.is_relative_to(root) for root in allowed
        ):
            raise PluginInstallationError(
                "Registered package is outside the managed installation roots."
            )
        self._directory_identity(installed, "registered_package")
        artifact = inspect_registered_plugin_artifact(row)
        if (
            not artifact.ok
            or artifact.manifest is None
            or artifact.manifest.plugin_id != plugin_id
            or artifact.manifest.version != row["plugin_version"]
        ):
            raise PluginInstallationError(
                "Registered package identity could not be verified for removal."
            )
        return artifact.manifest

    def _validate_removal_inventory(
        self, inventory: dict[str, Any], row: dict[str, Any]
    ) -> None:
        """Reject forged journal paths or a snapshot associated with another row."""
        from model.plugin_registry import _bounded_lifecycle_json

        _bounded_lifecycle_json(inventory)
        for key in (
            "plugin_id",
            "plugin_registry_id",
            "knowledge_scope_id",
            "manifest_hash",
            "plugin_version",
        ):
            if inventory.get(key) != row.get(key):
                raise PluginInstallationError(
                    "Removal inventory attribution differs from the current registration."
                )
        plugin_id = row["plugin_id"]
        expected = {
            "configuration": str(self.config_root / plugin_id),
            "installed": str(self.managed_root / "installed" / plugin_id),
            "snapshots": str(self.managed_root / "snapshots" / plugin_id),
        }
        directories = inventory.get("directories", [])
        if (
            len(directories) != len(expected)
            or {item["kind"]: item["path"] for item in directories} != expected
        ):
            raise PluginInstallationError(
                "Removal inventory contains an unauthorized filesystem target."
            )
        from model.plugin_routing.cache import PluginEmbeddingCache

        if inventory["routing_cache"]["path"] != str(
            PluginEmbeddingCache.default_cache_dir(self.project_root).absolute()
        ):
            raise PluginInstallationError(
                "Routing cache target changed after authorization."
            )

    def _removal_inventory(
        self,
        manifest: PluginManifest,
        row: dict[str, Any],
        *,
        keep_schema: bool,
    ) -> dict[str, Any]:
        """Collect bounded resource facts before authorization or lifecycle writes."""
        from model.plugin_registry import _bounded_lifecycle_json

        current = self._registry.get(manifest.plugin_id)
        if (
            current is None
            or current.get("plugin_registry_id") != row["plugin_registry_id"]
            or current.get("manifest_hash") != row["manifest_hash"]
            or current.get("removal_id")
        ):
            raise PluginInstallationError(
                "Current registration changed during removal preflight."
            )
        expected_config = self.config_root / manifest.plugin_id / "plugin.ini"
        if Path(str(row.get("config_path") or "")) != expected_config:
            raise PluginInstallationError(
                "Registered configuration is outside its managed plugin directory."
            )
        services = self._assert_services_quiescent(manifest.plugin_id)
        runner = self._database_deployer.administrative_runner_for(manifest)
        database = runner.schema_removal_inventory(
            manifest,
            plugin_registry_id=int(row["plugin_registry_id"]),
        )
        apex = self._removal_apex_installer(runner).removal_inventory(
            manifest,
            plugin_registry_id=int(row["plugin_registry_id"]),
            database_identity=database["database_identity"],
        )
        directories = [
            self._directory_identity(path, kind)
            for kind, path in (
                ("configuration", expected_config.parent),
                ("installed", self.managed_root / "installed" / manifest.plugin_id),
                ("snapshots", self.managed_root / "snapshots" / manifest.plugin_id),
            )
        ]
        from model.plugin_routing.cache import PluginEmbeddingCache

        cache = self._directory_identity(
            PluginEmbeddingCache.default_cache_dir(self.project_root).absolute(),
            "routing_cache",
        )
        inventory = {
            "plugin_id": manifest.plugin_id,
            "plugin_version": manifest.version,
            "plugin_registry_id": row["plugin_registry_id"],
            "knowledge_scope_id": row["knowledge_scope_id"],
            "manifest_hash": row["manifest_hash"],
            "schema_disposition": "KEEP" if keep_schema else "DROP",
            "database": database,
            "apex": apex,
            "services": services,
            "directories": directories,
            "routing_cache": cache,
            "resources": {
                "deployment_type": manifest.database_deployment.deployment_type,
                "schemas": [
                    {
                        "schema_name": schema.schema_name,
                        "bridge_api_dependencies": list(schema.bridge_api_dependencies),
                    }
                    for schema in manifest.database_schemas
                ],
                "apex_apps": [
                    {
                        "app_alias": app.alias,
                        "workspace": app.workspace,
                        "parsing_schema": app.parsing_schema,
                        "application_id": app.application_id,
                        "install_required": app.install_required,
                    }
                    for app in manifest.apex_apps
                ],
            },
        }
        self._clean_routing_cache(inventory, dry_run=True)
        return _bounded_lifecycle_json(inventory)

    def _clean_routing_cache(
        self, inventory: dict[str, Any], *, dry_run: bool = False
    ) -> None:
        """Invalidate only this plugin's entries in the declared shared cache."""
        from model.plugin_routing.cache import PluginEmbeddingCache

        cache = inventory["routing_cache"]
        PluginEmbeddingCache(Path(cache["path"])).remove_plugin(
            inventory["plugin_id"],
            expected_device=cache["device"],
            expected_inode=cache["inode"],
            dry_run=dry_run,
        )

    def _removal_apex_installer(self, runner: Any) -> PluginApexAppInstaller:
        """Keep APEX cleanup on the same host database target as schema cleanup."""
        if not self._default_apex_app_installer:
            return self._apex_app_installer
        container, pdb = runner.administrative_target
        return DockerPluginApexAppInstaller(
            container_name=container,
            oracle_pdb=pdb,
            project_root=self.project_root,
            logger=self._logger,
        )

    def _assert_services_quiescent(self, plugin_id: str) -> list[dict[str, Any]]:
        """Reject independent service leases without disclosing lease tokens."""
        services = [
            item
            for item in self._service_lifecycle.list_services()
            if item.plugin_id == plugin_id
        ]
        if any(item.lease_active_yn == "Y" for item in services):
            raise PluginInstallationError(
                "An active plugin service lease blocks maintenance removal."
            )
        return [
            {
                "service_code": item.service_code,
                "service_id": item.service_id,
                "current_state": item.current_state,
                "effective_policy": item.effective_policy,
            }
            for item in services
        ]

    @staticmethod
    def _manifest_from_removal_inventory(inventory: dict[str, Any]) -> PluginManifest:
        """Reconstruct only authorized resource declarations after package cleanup."""
        from model.plugin_routing.models import PluginDatabaseDeployment
        from model.plugin_routing.models import PluginDatabaseSchema
        from model.plugin_routing.models import PluginDatabaseVersionCheck

        resources = inventory["resources"]
        return PluginManifest(
            schema_version=2,
            plugin_id=inventory["plugin_id"],
            name=inventory["plugin_id"],
            description="Authorized removal resource snapshot",
            version=inventory["plugin_version"],
            enabled=False,
            capabilities=(),
            entitlements=(),
            entities=(),
            examples=(),
            entry_point=None,
            manifest_path=Path("/"),
            plugin_dir=Path("/"),
            manifest_hash=inventory["manifest_hash"],
            database_deployment=PluginDatabaseDeployment(
                deployment_type=resources["deployment_type"],
            ),
            database_schemas=tuple(
                PluginDatabaseSchema(
                    schema_name=item["schema_name"],
                    purpose="Authorized removal",
                    managed_by="orac",
                    minimum_version="",
                    version_check=PluginDatabaseVersionCheck(enabled=False),
                    bridge_api_dependencies=tuple(item["bridge_api_dependencies"]),
                )
                for item in resources["schemas"]
            ),
            apex_apps=tuple(
                PluginApexApp(label=item["app_alias"], app_export="", **item)
                for item in resources["apex_apps"]
            ),
        )

    @staticmethod
    def _open_managed_directory(path: Path) -> int:
        """Open a directory through descriptors without following parent links."""
        if not path.is_absolute() or ".." in path.parts:
            raise PluginInstallationError(
                "Managed cleanup requires a canonical absolute path."
            )
        descriptor = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in path.parts[1:]:
                child = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
                os.close(descriptor)
                descriptor = child
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    @classmethod
    def _directory_identity(cls, path: Path, kind: str) -> dict[str, Any]:
        """Record a managed root inode and reject links, mounts and special files."""
        identity: dict[str, Any] = {
            "path": str(path),
            "kind": kind,
            "device": None,
            "inode": None,
        }
        try:
            descriptor = cls._open_managed_directory(path)
        except FileNotFoundError:
            return identity
        try:
            info = os.fstat(descriptor)
            cls._walk_managed_directory(descriptor, info.st_dev, remove=False)
            identity.update(device=info.st_dev, inode=info.st_ino)
            return identity
        finally:
            os.close(descriptor)

    @classmethod
    def _walk_managed_directory(
        cls, descriptor: int, device: int, *, remove: bool
    ) -> None:
        """Inspect or unlink entries relative to the verified directory inode."""
        for name in os.listdir(descriptor):
            info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            if info.st_dev != device or not (
                stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)
            ):
                raise PluginInstallationError(
                    "Managed cleanup encountered a link, mount or special file."
                )
            if stat.S_ISDIR(info.st_mode):
                child = os.open(
                    name,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
                try:
                    if (os.fstat(child).st_dev, os.fstat(child).st_ino) != (
                        info.st_dev,
                        info.st_ino,
                    ):
                        raise PluginInstallationError(
                            "Managed directory changed during cleanup."
                        )
                    cls._walk_managed_directory(child, device, remove=remove)
                finally:
                    os.close(child)
                if remove:
                    current = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                    if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                        raise PluginInstallationError(
                            "Managed directory was replaced during cleanup."
                        )
                    os.rmdir(name, dir_fd=descriptor)
            elif remove:
                os.unlink(name, dir_fd=descriptor)
        if remove:
            os.fsync(descriptor)

    def _remove_managed_directory(self, identity: dict[str, Any]) -> None:
        """Delete only the authorized inode under a host-managed plugin root."""
        path = Path(identity["path"])
        try:
            parent = self._open_managed_directory(path.parent)
        except FileNotFoundError:
            return
        try:
            try:
                descriptor = os.open(
                    path.name,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=parent,
                )
            except FileNotFoundError:
                return
            try:
                info = os.fstat(descriptor)
                if (info.st_dev, info.st_ino) != (
                    identity["device"],
                    identity["inode"],
                ):
                    raise PluginInstallationError(
                        "Managed cleanup target was replaced after authorization."
                    )
                self._walk_managed_directory(descriptor, info.st_dev, remove=False)
                self._walk_managed_directory(descriptor, info.st_dev, remove=True)
                current = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
                if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                    raise PluginInstallationError(
                        "Managed cleanup root changed during deletion."
                    )
                os.rmdir(path.name, dir_fd=parent)
                os.fsync(parent)
            finally:
                os.close(descriptor)
        finally:
            os.close(parent)

    def list_plugins(self, *, include_source: bool = False) -> list[dict[str, Any]]:
        """List current registrations, optionally including separate source packages."""
        registry_rows = {
            str(row["plugin_id"]): row
            for row in self._registry.list_all()
            if row.get("plugin_id")
        }
        manifests, errors = PluginDiscovery(self.project_root / "plugins").discover()
        entries: list[dict[str, Any]] = []
        unpacked_plugin_ids: set[str] = set()

        for manifest in manifests:
            row = registry_rows.get(manifest.plugin_id)
            unpacked_plugin_ids.add(manifest.plugin_id)
            if row is not None or include_source:
                entries.append(self._plugin_inventory_entry(manifest=manifest, row=row))

        for plugin_id, row in registry_rows.items():
            if plugin_id not in unpacked_plugin_ids:
                entries.append(self._plugin_inventory_entry(manifest=None, row=row))

        if include_source:
            for error in errors:
                entries.append(self._plugin_discovery_error_entry(error))

        return sorted(
            entries,
            key=lambda entry: (
                str(entry.get("plugin_id") or "~"),
                str(entry.get("manifest_path") or ""),
            ),
        )

    def check(self, plugin_id: str) -> PluginInstallResult:
        """Re-run non-mutating readiness checks for an installed plugin."""
        row = self._registry.get(plugin_id)
        if row is None:
            raise PluginInstallationError(f"Plugin '{plugin_id}' is not registered.")
        if row.get("removal_id"):
            raise PluginInstallationError(
                f"Plugin '{plugin_id}' has an incomplete removal. Resume removal first."
            )
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
        command_result = self._command_dependency_checker.check(
            manifest.command_dependencies,
            context="check",
        )
        if hasattr(self._registry, "record_command_status"):
            self._registry.record_command_status(
                plugin_id,
                command_result.status,
                command_result.report_json(),
            )
        if command_result.status == "failed":
            raise PluginInstallationError(
                _command_dependency_failure_message(command_result)
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
            warnings=command_result.warnings,
        )

    def _plugin_inventory_entry(
        self,
        *,
        manifest: PluginManifest | None,
        row: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build one plugin list row from registry and unpacked-manifest state."""
        plugin_id = (
            manifest.plugin_id
            if manifest is not None
            else str((row or {}).get("plugin_id") or "")
        )
        install_status = str((row or {}).get("install_status") or "not_installed")
        artifact_status, artifact_error, artifact_ok = self._inventory_artifact_status(
            row=row,
            install_status=install_status,
        )
        installed = row is not None and install_status == "success" and artifact_ok
        return {
            "plugin_id": plugin_id,
            "name": (
                manifest.name
                if manifest is not None
                else str((row or {}).get("plugin_name") or "")
            ),
            "installed": installed,
            "unpacked": manifest is not None,
            "enabled": self._inventory_enabled(manifest=manifest, row=row),
            "installed_artifact_status": artifact_status,
            "installed_artifact_error": artifact_error,
            "installed_version": (
                str(row.get("plugin_version"))
                if row and row.get("plugin_version")
                else None
            ),
            "unpacked_version": manifest.version if manifest is not None else None,
            "install_status": install_status,
            "readiness_status": (
                str(row.get("readiness_status"))
                if row and row.get("readiness_status")
                else None
            ),
            "installed_path": (
                str(row.get("installed_path"))
                if row and row.get("installed_path")
                else None
            ),
            "manifest_path": (
                self._relative_inventory_path(manifest.manifest_path)
                if manifest is not None
                else None
            ),
            "plugin_dir": (
                self._relative_inventory_path(manifest.plugin_dir)
                if manifest is not None
                else None
            ),
            "error": None,
        }

    @staticmethod
    def _inventory_artifact_status(
        *,
        row: dict[str, Any] | None,
        install_status: str,
    ) -> tuple[str | None, str | None, bool]:
        """Return artifact inventory status without mutating registry state."""
        if row is None:
            return None, None, False
        if install_status != "success":
            return "not_active", None, False
        status = inspect_registered_plugin_artifact(row)
        return status.code, None if status.ok else status.message, status.ok

    def _plugin_discovery_error_entry(self, error: str) -> dict[str, Any]:
        """Build one inventory row for an unpacked manifest discovery error."""
        manifest_ref = error.split(":", 1)[0]
        manifest_path = Path(manifest_ref)
        return {
            "plugin_id": manifest_path.stem or None,
            "name": None,
            "installed": False,
            "unpacked": True,
            "enabled": False,
            "installed_version": None,
            "unpacked_version": None,
            "install_status": "discovery_error",
            "readiness_status": None,
            "installed_path": None,
            "manifest_path": manifest_ref,
            "plugin_dir": None,
            "error": error,
        }

    def _inventory_enabled(
        self,
        *,
        manifest: PluginManifest | None,
        row: dict[str, Any] | None,
    ) -> bool:
        """Return the effective enabled flag visible in plugin inventory."""
        if row is not None and row.get("enabled") is not None:
            return str(row.get("enabled")).upper() == "Y"
        return bool(manifest.enabled) if manifest is not None else False

    def _relative_inventory_path(self, path: Path) -> str:
        """Return a stable project-relative path for plugin inventory output."""
        try:
            return str(path.resolve().relative_to(self.project_root))
        except ValueError:
            return str(path)

    def _install(self, package: PluginPackage, staging: Path) -> PluginInstallResult:
        """Run all required installation gates for one validated package."""
        candidate_root = staging / "candidate"
        candidate_plugin_dir = candidate_root / "plugin"
        self._stage_candidate_package(package, candidate_root)
        manifest = PluginDiscovery(candidate_root).load_manifest(
            candidate_root / "manifest.json",
            plugin_dir=candidate_plugin_dir,
            enforce_filename=False,
        )
        previous = self._registry.get(manifest.plugin_id)
        if previous and previous.get("removal_id"):
            raise PluginInstallationError(
                "Plugin removal is incomplete; resume removal before installing."
            )
        validate_declared_imports(
            candidate_plugin_dir,
            manifest.python_dependencies,
            plugin_id=manifest.plugin_id,
        )
        snapshot_path = self._persist_install_snapshot(
            candidate_root, manifest, package
        )
        command_result = self._command_dependency_checker.check(
            manifest.command_dependencies,
            context="install",
        )
        if command_result.status == "failed":
            return self._failure(
                manifest,
                package,
                "command_prerequisite_failed",
                _command_dependency_failure_message(command_result),
                command_prerequisite_status=command_result.status,
                command_dependency_report=command_result.report_json(),
            )
        if previous is None:
            self._record(
                self._registry_values(
                    manifest,
                    package,
                    snapshot_path,
                    self.config_root / manifest.plugin_id / "plugin.ini",
                    install_status="installing",
                    configuration_status="not_run",
                    dependency_status="not_run",
                    database_status="not_run",
                    readiness_status="not_run",
                    enabled=False,
                    command_prerequisite_status=command_result.status,
                    command_dependency_report=command_result.report_json(),
                )
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

        installed_path, previous_path = self._activate_candidate(
            candidate_root, manifest
        )
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
        service_command_result: PluginCommandDependencyResult | None = None
        try:
            service_command_result = self._register_service_lifecycle(active_manifest)
        except PluginInstallationError as exc:
            self._rollback_activation(installed_path, previous_path)
            return self._failure(
                manifest,
                package,
                "service_registration_failed",
                str(exc),
                configuration_status="success",
                dependency_status=dependency_result.status,
                database_status=database_result.status,
            )
        # Materialise the validated archive using the package-directory BOM.
        # Archive plugin/ contents become plugins/<plugin_id>/ and archive
        # resources/ remains plugins/<plugin_id>/resources/.
        try:
            materialise_repository_plugin(
                package,
                self.project_root / "plugins",
            )
        except Exception as exc:
            self._rollback_activation(installed_path, previous_path)
            return self._failure(
                manifest,
                package,
                "repository_install_failed",
                str(exc),
                configuration_status="success",
                dependency_status=dependency_result.status,
                database_status=database_result.status,
            )

        final_command_result = service_command_result or command_result
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
            command_prerequisite_status=final_command_result.status,
            command_dependency_report=final_command_result.report_json(),
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
            warnings=final_command_result.warnings,
        )

    def _installation_snapshot_path(
        self, manifest: PluginManifest, package: PluginPackage
    ) -> Path:
        """Return the host-managed snapshot for one validated package."""
        if not re.fullmatch(r"[a-z][a-z0-9_]*", manifest.plugin_id) or not re.fullmatch(
            r"[a-fA-F0-9]{64}", package.package_hash
        ):
            raise PluginInstallationError("Invalid package snapshot identity.")
        return (
            self.managed_root / "snapshots" / manifest.plugin_id / package.package_hash
        )

    def _persist_install_snapshot(
        self, candidate_root: Path, manifest: PluginManifest, package: PluginPackage
    ) -> Path:
        """Keep validated package facts available after any installation failure.

        The registry can point at this disabled snapshot before external work.
        A retry never silently adopts a changed snapshot with the same hash.
        """
        snapshot = self._installation_snapshot_path(manifest, package)
        for path in (snapshot, *snapshot.parents):
            if path.is_symlink():
                raise PluginInstallationError(
                    "Package snapshot paths cannot be symlinks."
                )
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        if not snapshot.exists():
            with tempfile.TemporaryDirectory(
                prefix=".snapshot-", dir=snapshot.parent
            ) as temporary:
                incoming = Path(temporary) / "package"
                shutil.copytree(candidate_root, incoming)
                incoming.rename(snapshot)
        expected = self._snapshot_fingerprints(candidate_root)
        if self._snapshot_fingerprints(snapshot) != expected:
            raise PluginInstallationError(
                "Stored package snapshot differs from the validated package."
            )
        return snapshot

    @staticmethod
    def _snapshot_fingerprints(root: Path) -> dict[str, str]:
        """Compare snapshot content without following links or special files."""
        result: dict[str, str] = {}
        for path in root.rglob("*"):
            if path.is_symlink() or not (path.is_dir() or path.is_file()):
                raise PluginInstallationError(
                    "Package snapshot contains an unsafe file."
                )
            if path.is_file():
                with path.open("rb") as stream:
                    result[path.relative_to(root).as_posix()] = hashlib.file_digest(
                        stream, "sha256"
                    ).hexdigest()
        return result

    def _initialise_config(
        self, package: PluginPackage, manifest: PluginManifest
    ) -> Path:
        """Create external mutable configuration once without overwriting it."""
        plugin_config_dir = self.config_root / manifest.plugin_id
        plugin_config_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        config_path = plugin_config_dir / "plugin.ini"
        if config_path.exists():
            return config_path
        template = package.plugin_dir / "plugin.ini.example"
        if template.is_file():
            shutil.copy2(template, config_path)
            config_path.chmod(0o600)
        return config_path

    @staticmethod
    def _stage_candidate_package(package: PluginPackage, candidate_root: Path) -> None:
        """Stage one validated package in canonical managed-install layout."""
        candidate_root.mkdir(parents=True, exist_ok=True)
        shutil.copy2(package.manifest.manifest_path, candidate_root / "manifest.json")
        claimed_directories = claimed_source_directories()

        for spec in PLUGIN_DIRECTORY_BOM:
            source_root = _candidate_package_directory_source(package, spec)
            if not source_root.exists():
                continue
            destination_root = candidate_root / spec.package_name
            destination_root.mkdir(parents=True, exist_ok=True)
            for source in sorted(source_root.rglob("*")):
                if not source.is_file():
                    continue
                relative = source.relative_to(source_root)
                if package.source_type != "tarball":
                    source_relative = source.relative_to(package.plugin_dir)
                    if is_ignored_source_file(source_relative):
                        continue
                    if spec.catch_all:
                        if (
                            source_relative.parts
                            and source_relative.parts[0] in claimed_directories
                        ):
                            continue
                        if source_relative.as_posix() in PLUGIN_ROOT_FILE_BOM:
                            continue
                target = destination_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

        for file_name in PLUGIN_ROOT_FILE_BOM:
            source_file = (
                package.package_root / file_name
                if package.source_type == "tarball"
                else package.plugin_dir / file_name
            )
            if source_file.is_file():
                shutil.copy2(source_file, candidate_root / file_name)

    @staticmethod
    def _missing_required_secrets(manifest: PluginManifest) -> tuple[str, ...]:
        """Return required secret keys absent from the encrypted PAT vault."""
        if manifest.secrets is None:
            return ()
        store = PluginPatVaultStore(manifests=(manifest,))
        return tuple(
            secret.key
            for secret in manifest.secrets.keys
            if secret.required
            and not store.check_secret(manifest.plugin_id, secret.key)
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
        if manifest.interceptor_entry_point:
            interceptor_class = load_plugin_interceptor_class(manifest)
            interceptor = instantiate_plugin_interceptor(
                interceptor_class,
                manifest=manifest,
            )
            interceptor.prepare()
        for service_runtime in manifest.service_runtimes:
            service_class = load_plugin_service_class(manifest, service_runtime)
            required_method = (
                "tick" if service_runtime.execution_model == "scheduled" else "run"
            )
            if not callable(getattr(service_class, required_method, None)):
                raise PluginInstallationError(
                    f"Plugin service '{manifest.plugin_id}' does not expose "
                    f"{required_method}()."
                )
            health_check = service_runtime.health_check
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
                self._record_apex_app(
                    self._apex_app_values(
                        manifest,
                        app,
                        package,
                        install_status="pending",
                        install_log=None,
                    )
                )
                try:
                    apex_installer = self._apex_app_installer
                    if self._default_apex_app_installer:
                        apex_installer = self._removal_apex_installer(
                            self._database_deployer.administrative_runner_for(manifest)
                        )
                    result = apex_installer.install(manifest, app)
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

    def _register_service_lifecycle(
        self,
        manifest: PluginManifest,
    ) -> PluginCommandDependencyResult | None:
        """Register service descriptors and capture their fresh command probe."""
        if manifest.runtime_mode not in {"service", "hybrid"}:
            return None

        service_manager = self._service_manager or PluginServiceManager(
            logger=self._logger
        )
        command_result: PluginCommandDependencyResult | None = None

        def capture_command_status(
            plugin_id: str,
            result: PluginCommandDependencyResult,
        ) -> None:
            """Defer the service probe write until final registry persistence."""
            nonlocal command_result
            if plugin_id != manifest.plugin_id:
                raise PluginInstallationError(
                    "Service registration returned command status for "
                    f"unexpected plugin '{plugin_id}'."
                )
            command_result = result

        try:
            service_manager.register_manifests(
                [manifest],
                command_status_recorder=capture_command_status,
            )
        except Exception as exc:
            raise PluginInstallationError(
                f"Unable to register plugin service lifecycle rows: {exc}"
            ) from exc
        return command_result

    def _activate_candidate(
        self,
        candidate_root: Path,
        manifest: PluginManifest,
    ) -> tuple[Path, Path | None]:
        """Activate a candidate while retaining any prior version for rollback."""
        destination = (
            self.managed_root / "installed" / manifest.plugin_id / manifest.version
        )
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
        command_prerequisite_status: str = "not_run",
        command_dependency_report: str | None = None,
    ) -> PluginInstallResult:
        """Record a failed installation without activating the candidate."""
        previous = self._registry.get(manifest.plugin_id) if self._registry else None
        active_prior = bool(
            previous
            and str(previous.get("enabled") or "").upper() == "Y"
            and previous.get("install_status") == "success"
            and previous.get("installed_path")
        )
        prior_installed_path = (
            Path(str(previous.get("installed_path")))
            if active_prior and previous is not None
            else None
        )
        if not active_prior:
            self._record(
                self._registry_values(
                    manifest,
                    package,
                    self._installation_snapshot_path(manifest, package),
                    self.config_root / manifest.plugin_id / "plugin.ini",
                    install_status=status,
                    configuration_status=configuration_status,
                    dependency_status=dependency_status,
                    database_status=database_status,
                    command_prerequisite_status=command_prerequisite_status,
                    command_dependency_report=command_dependency_report,
                    readiness_status=(
                        "failed" if status == "readiness_failed" else "not_run"
                    ),
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
            installed_path=prior_installed_path,
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
        command_prerequisite_status: str = "not_applicable",
        command_dependency_report: str | None = None,
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
            "ui_icon_class": (
                manifest.ui.icon_class if manifest.ui is not None else None
            ),
            "ui_accent_class": (
                manifest.ui.accent_class if manifest.ui is not None else None
            ),
            "dependency_declarations": json.dumps(manifest.python_dependencies),
            "dependency_fingerprint": dependency_fingerprint(
                manifest.python_dependencies
            ),
            "command_dependency_declarations": json.dumps(
                [
                    {
                        "command": dependency.command,
                        "version_specifier": dependency.version_specifier,
                        "required": dependency.required,
                        "purpose": dependency.purpose,
                        "install_hint": dependency.install_hint,
                    }
                    for dependency in manifest.command_dependencies
                ]
            ),
            "command_dependency_fingerprint": command_dependency_fingerprint(
                manifest.command_dependencies
            ),
            "command_prerequisite_status": command_prerequisite_status,
            "command_dependency_report": command_dependency_report,
            "install_status": install_status,
            "configuration_status": configuration_status,
            "dependency_status": dependency_status,
            "database_status": database_status,
            "readiness_status": readiness_status,
            "enabled": enabled,
            "last_error_code": install_status if not enabled else None,
            "last_error_message": _clamp_registry_text(last_error_message, 2000),
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
            "icon": _effective_apex_app_icon(manifest, app),
            "card_title": app.card_title,
            "card_subtitle": app.card_subtitle,
            "install_status": install_status,
            "install_log": install_log,
            "last_error_message": _clamp_registry_text(last_error_message, 4000),
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


def _effective_apex_app_icon(
    manifest: PluginManifest, app: PluginApexApp
) -> str | None:
    """Return the app icon resolved from app and plugin manifest metadata."""
    if app.icon_class:
        return app.icon_class
    if app.icon:
        return app.icon
    if manifest.ui is not None:
        return manifest.ui.icon_class
    return None


def _candidate_package_directory_source(package: PluginPackage, spec) -> Path:
    """Resolve one BOM source directory for managed candidate staging."""
    if package.source_type == "tarball":
        return package.package_root / spec.package_name
    return source_root_for_spec(package.plugin_dir, spec)


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


def _clamp_registry_text(value: str | None, limit: int) -> str | None:
    """Return text that fits the target registry column."""
    if value is None or len(value) <= limit:
        return value
    suffix = "... [truncated]"
    return value[: max(0, limit - len(suffix))] + suffix


def _command_dependency_failure_message(
    result: PluginCommandDependencyResult,
) -> str:
    """Return a bounded summary for failed required command prerequisites."""
    failures = [
        probe.reason
        for probe in result.probes
        if probe.required and not probe.available
    ]
    return (
        _clamp_registry_text(
            "Required command prerequisite failed: " + "; ".join(failures),
            2000,
        )
        or "Required command prerequisite failed."
    )
