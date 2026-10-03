"""Persist and resolve active Orac plugin installation registry records."""

# Author: Clive Bostock
# Date: 07-Jun-2026
# Description: Mediates plugin registry access through approved Oracle APIs.

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import oracledb
from orac_core.plugin_registry_policy import plugin_registry_row_runtime_eligible

if TYPE_CHECKING:
    from model.plugin_routing.models import PluginManifest


class PluginRegistryError(RuntimeError):
    """Raised when plugin registry access cannot complete safely."""


@dataclass(frozen=True)
class PluginRegistryArtifactStatus:
    """Describes whether a registry row points at a usable installed artifact."""

    plugin_id: str
    installed_path: str | None
    code: str
    ok: bool
    message: str | None = None
    manifest: PluginManifest | None = None


@dataclass(frozen=True)
class PluginRegistryManifestLoadResult:
    """Contains loadable enabled manifests and per-plugin registry issues."""

    manifests: tuple[PluginManifest, ...]
    issues: tuple[PluginRegistryArtifactStatus, ...]


class PluginRegistryStore:
    """Read and update plugin registry state through ORAC_CODE surfaces."""

    _SELECT_COLUMNS = (
        "plugin_id, plugin_name, plugin_version, runtime_mode, manifest_hash, "
        "package_hash, install_source_type, install_source_ref, installed_path, "
        "config_path, dependency_fingerprint, command_dependency_declarations, "
        "install_status, configuration_status, "
        "dependency_status, command_dependency_fingerprint, "
        "command_prerequisite_status, command_dependency_report, "
        "database_status, readiness_status, enabled, "
        "ui_icon_class, ui_accent_class, last_error_code, last_error_message, "
        "row_version, plugin_registry_id, knowledge_scope_id, "
        "database_schemas_summary, removal_id"
    )

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any] | None = None,
        logger: Any | None = None,
    ) -> None:
        """Initialise the registry store with an optional test session factory."""
        self._session_factory = session_factory or _default_session
        self._logger = logger

    def record(self, values: dict[str, Any]) -> None:
        """Upsert one current plugin installation record."""
        session = self._connect()
        try:
            with session.cursor() as cursor:
                cursor.setinputsizes(
                    capabilities_summary=oracledb.DB_TYPE_JSON,
                    entitlements_summary=oracledb.DB_TYPE_JSON,
                    database_schemas_summary=oracledb.DB_TYPE_JSON,
                    dependency_declarations=oracledb.DB_TYPE_JSON,
                    command_dependency_declarations=oracledb.DB_TYPE_JSON,
                    command_dependency_report=oracledb.DB_TYPE_JSON,
                )
                cursor.execute(
                    _UPSERT_BLOCK,
                    {
                        "plugin_id": values["plugin_id"],
                        "plugin_name": values["plugin_name"],
                        "plugin_version": values["plugin_version"],
                        "runtime_mode": values["runtime_mode"],
                        "manifest_hash": values["manifest_hash"],
                        "package_hash": values["package_hash"],
                        "install_source_type": values["install_source_type"],
                        "install_source_ref": values["install_source_ref"],
                        "installed_path": values.get("installed_path"),
                        "config_path": values.get("config_path"),
                        "capabilities_summary": _json_bind_value(
                            values.get("capabilities_summary")
                        ),
                        "entitlements_summary": _json_bind_value(
                            values.get("entitlements_summary")
                        ),
                        "database_schemas_summary": _json_bind_value(
                            values.get("database_schemas_summary")
                        ),
                        "ui_icon_class": values.get("ui_icon_class"),
                        "ui_accent_class": values.get("ui_accent_class"),
                        "dependency_declarations": _json_bind_value(
                            values.get("dependency_declarations")
                        ),
                        "dependency_fingerprint": values["dependency_fingerprint"],
                        "command_dependency_declarations": _json_bind_value(
                            values.get("command_dependency_declarations")
                        ),
                        "command_dependency_fingerprint": values.get(
                            "command_dependency_fingerprint", "0" * 64
                        ),
                        "command_prerequisite_status": values.get(
                            "command_prerequisite_status", "not_applicable"
                        ),
                        "command_dependency_report": _json_bind_value(
                            values.get("command_dependency_report")
                        ),
                        "install_status": values["install_status"],
                        "configuration_status": values["configuration_status"],
                        "dependency_status": values["dependency_status"],
                        "database_status": values["database_status"],
                        "readiness_status": values["readiness_status"],
                        "enabled": "Y" if values.get("enabled") else "N",
                        "last_error_code": values.get("last_error_code"),
                        "last_error_message": values.get("last_error_message"),
                    },
                )
            session.commit()
        except Exception as exc:
            raise PluginRegistryError(
                f"Unable to record plugin registry state: {exc}"
            ) from exc
        finally:
            _close_quietly(session)

    def get(self, plugin_id: str) -> dict[str, Any] | None:
        """Return one current registry record."""
        rows = self._query(
            f"select {self._SELECT_COLUMNS} "
            "from orac_code.plugin_registry_v where plugin_id = :plugin_id",
            {"plugin_id": plugin_id},
        )
        return rows[0] if rows else None

    def record_command_status(
        self,
        plugin_id: str,
        status: str,
        report_json: str,
    ) -> None:
        """Persist a fresh install, check, service, or conversion probe result."""
        session = self._connect()
        try:
            with session.cursor() as cursor:
                cursor.setinputsizes(
                    command_dependency_report=oracledb.DB_TYPE_JSON,
                )
                cursor.execute(
                    """
                    begin
                      orac_code.plugin_registry_api
                        .update_command_prerequisite_status(
                          :plugin_id,
                          :command_prerequisite_status,
                          :command_dependency_report
                        );
                    end;
                    """,
                    {
                        "plugin_id": plugin_id,
                        "command_prerequisite_status": status,
                        "command_dependency_report": _json_bind_value(report_json),
                    },
                )
            session.commit()
        except Exception as exc:
            raise PluginRegistryError(
                f"Unable to record command prerequisite status: {exc}"
            ) from exc
        finally:
            _close_quietly(session)

    def list_all(self) -> list[dict[str, Any]]:
        """Return all current plugin registry records."""
        return self._query(
            f"select {self._SELECT_COLUMNS} "
            "from orac_code.plugin_registry_v order by plugin_id",
            {},
        )

    def set_enabled(self, plugin_id: str, *, enabled: bool) -> None:
        """Change enablement without recreating an absent installation."""
        self._mutate(
            "begin orac_code.plugin_registry_api.set_enabled(:plugin_id, :enabled); end;",
            {"plugin_id": plugin_id, "enabled": "Y" if enabled else "N"},
        )

    def removal_history(self, plugin_id: str) -> list[dict[str, Any]]:
        """Read inert removal history, including an incomplete operation."""
        return self._query(
            "select removal_id, plugin_id, plugin_registry_id, knowledge_scope_id, "
            "plugin_version, manifest_hash, schema_disposition, database_identity, "
            "resource_inventory, checkpoints, external_complete_yn, files_complete_yn, "
            "confirmed_by, completed_on, last_error_code, last_error_message, created_on "
            "from orac_code.plugin_removals_v where plugin_id = :plugin_id "
            "order by created_on desc, removal_id",
            {"plugin_id": plugin_id},
        )

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
        self._mutate(
            "begin orac_code.plugin_registry_api.begin_removal("
            ":plugin_id, :registry_id, :removal_id, :disposition, "
            ":database_identity, :inventory, :confirmed_by); end;",
            {
                "plugin_id": plugin_id,
                "registry_id": registry_id,
                "removal_id": removal_id,
                "disposition": "KEEP" if keep_schema else "DROP",
                "database_identity": database_identity,
                "inventory": _bounded_lifecycle_json(inventory),
                "confirmed_by": confirmed_by,
            },
            json_parameters=("inventory",),
        )

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
        self._mutate(
            "begin orac_code.plugin_registry_api.checkpoint_removal("
            ":removal_id, :registry_id, :checkpoints, :external_complete, "
            ":files_complete, :error_code, :error_message); end;",
            {
                "removal_id": removal_id,
                "registry_id": registry_id,
                "checkpoints": _bounded_lifecycle_json(checkpoints),
                "external_complete": "Y" if external_complete else "N",
                "files_complete": "Y" if files_complete else "N",
                "error_code": error_code,
                "error_message": error_message,
            },
            json_parameters=("checkpoints",),
        )

    def finalize_removal(self, *, removal_id: str, registry_id: int) -> None:
        """Commit Core cleanup and registry deletion as one guarded transaction."""
        self._mutate(
            "begin orac_code.plugin_registry_api.finalize_removal(:removal_id, :registry_id); end;",
            {"removal_id": removal_id, "registry_id": registry_id},
        )

    def _mutate(
        self,
        sql: str,
        binds: dict[str, Any],
        *,
        json_parameters: tuple[str, ...] = (),
    ) -> None:
        """Execute one controlled lifecycle transaction without leaking binds."""
        session = self._connect()
        try:
            with session.cursor() as cursor:
                if json_parameters:
                    cursor.setinputsizes(
                        **{name: oracledb.DB_TYPE_JSON for name in json_parameters}
                    )
                cursor.execute(sql, binds)
            session.commit()
        except Exception as exc:
            try:
                session.rollback()
            except Exception:
                # Closing the session is the remaining rollback boundary.
                # Preserve the original failure, including an uncertain commit.
                pass
            raise PluginRegistryError("Plugin lifecycle transaction failed.") from exc
        finally:
            _close_quietly(session)

    def list_enabled(self) -> list[dict[str, Any]]:
        """Return registry rows that passed every runtime eligibility gate."""
        return [
            row
            for row in self._query(
                f"select {self._SELECT_COLUMNS} "
                "from orac_code.plugin_registry_v "
                "where enabled = 'Y' "
                "and install_status = 'success' "
                "and configuration_status in ('success', 'not_required') "
                "and dependency_status in ('success', 'not_required') "
                "and command_prerequisite_status in "
                "('not_applicable', 'success', 'degraded') "
                "and database_status in "
                "('deployed', 'already_deployed', 'not_required', "
                "'optional_missing') "
                "and readiness_status = 'success' order by plugin_id",
                {},
            )
            if plugin_registry_row_runtime_eligible(row)
        ]

    def enabled_manifests(self) -> list[PluginManifest]:
        """Load validated manifests for active installed plugin versions."""
        result = self.load_enabled_manifest_result(strict=True)
        return list(result.manifests)

    def enabled_manifest(self, plugin_id: str) -> PluginManifest | None:
        """Load one enabled plugin manifest without scanning unrelated plugins."""
        row = self.get(plugin_id)
        if row is None or not plugin_registry_row_runtime_eligible(row):
            return None
        status = inspect_registered_plugin_artifact(row)
        if not status.ok:
            raise PluginRegistryError(status.message or status.code)
        return status.manifest

    def load_enabled_manifest_result(
        self,
        *,
        strict: bool = True,
    ) -> PluginRegistryManifestLoadResult:
        """Load enabled manifests, optionally collecting per-plugin artifact drift."""
        manifests: list[PluginManifest] = []
        issues: list[PluginRegistryArtifactStatus] = []
        for row in self.list_enabled():
            status = inspect_registered_plugin_artifact(row)
            if not status.ok:
                if strict:
                    raise PluginRegistryError(status.message or status.code)
                issues.append(status)
                continue
            if status.manifest is not None:
                manifests.append(status.manifest)
        return PluginRegistryManifestLoadResult(
            manifests=tuple(manifests),
            issues=tuple(issues),
        )

    def _query(self, sql: str, binds: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute a read against the approved ORAC_CODE registry view."""
        session = None
        try:
            session = self._connect()
            with session.cursor() as cursor:
                cursor.execute(sql, binds)
                columns = [description[0].lower() for description in cursor.description]
                return [
                    dict(zip(columns, row, strict=True)) for row in cursor.fetchall()
                ]
        except Exception as exc:
            raise PluginRegistryError(f"Unable to read plugin registry: {exc}") from exc
        finally:
            if session is not None:
                _close_quietly(session)

    def _connect(self) -> Any:
        """Return an ORAC runtime database session."""
        return self._session_factory()


def inspect_registered_plugin_artifact(
    row: dict[str, Any],
) -> PluginRegistryArtifactStatus:
    """Inspect the installed plugin artifact referenced by one registry row.

    Args:
        row: Registry row from ``orac_code.plugin_registry_v``.

    Returns:
        A status object. When ``ok`` is true, ``manifest`` contains the loaded
        manifest bound to its installed runtime paths.
    """
    from model.plugin_routing.discovery import PluginDiscovery
    from model.plugin_routing.discovery import PluginManifestError

    plugin_id = str(row.get("plugin_id") or "").strip()
    installed_path_text = str(row.get("installed_path") or "").strip()
    if not installed_path_text:
        return PluginRegistryArtifactStatus(
            plugin_id=plugin_id,
            installed_path=None,
            code="missing_installed_path",
            ok=False,
            message=f"Registered plugin installed_path is missing for '{plugin_id}'.",
        )

    installed_path = Path(installed_path_text)
    manifest_path = installed_path / "manifest.json"
    plugin_dir = installed_path / "plugin"
    if not manifest_path.is_file() or not plugin_dir.is_dir():
        return PluginRegistryArtifactStatus(
            plugin_id=plugin_id,
            installed_path=installed_path_text,
            code="missing_installed_files",
            ok=False,
            message=f"Registered plugin files are missing for '{plugin_id}'.",
        )

    try:
        manifest = PluginDiscovery(installed_path).load_manifest(
            manifest_path,
            plugin_dir=plugin_dir,
            enforce_filename=False,
        )
    except PluginManifestError as exc:
        return PluginRegistryArtifactStatus(
            plugin_id=plugin_id,
            installed_path=installed_path_text,
            code="invalid_manifest",
            ok=False,
            message=f"Registered plugin manifest is invalid for '{plugin_id}': {exc}",
        )

    expected_hash = str(row.get("manifest_hash") or "").strip()
    if expected_hash and manifest.manifest_hash != expected_hash:
        return PluginRegistryArtifactStatus(
            plugin_id=plugin_id,
            installed_path=installed_path_text,
            code="manifest_hash_mismatch",
            ok=False,
            message=f"Registered manifest hash mismatch for '{manifest.plugin_id}'.",
        )

    return PluginRegistryArtifactStatus(
        plugin_id=plugin_id,
        installed_path=installed_path_text,
        code="present",
        ok=True,
        manifest=replace(
            manifest,
            config_path=(
                Path(str(row["config_path"])) if row.get("config_path") else None
            ),
        ),
    )


class PluginApexAppRegistryStore:
    """Read and update plugin APEX app registry state through ORAC_CODE surfaces."""

    _MENU_SELECT_COLUMNS = (
        "plugin_id, plugin_version, app_alias, workspace, installed_app_id, "
        "entry_page_id, label, description, required_roles, icon, card_title, "
        "card_subtitle"
    )

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any] | None = None,
        logger: Any | None = None,
    ) -> None:
        """Initialise the APEX app registry store with an optional session factory."""
        self._session_factory = session_factory or _default_session
        self._logger = logger

    def record(self, values: dict[str, Any]) -> None:
        """Upsert one plugin APEX app registry record."""
        session = self._connect()
        try:
            with session.cursor() as cursor:
                cursor.setinputsizes(required_roles=oracledb.DB_TYPE_JSON)
                cursor.execute(
                    _APEX_APP_UPSERT_BLOCK,
                    {
                        "plugin_id": values["plugin_id"],
                        "plugin_version": values["plugin_version"],
                        "app_alias": values["app_alias"],
                        "workspace": values["workspace"],
                        "parsing_schema": values["parsing_schema"],
                        "app_export": values["app_export"],
                        "declared_application_id": values.get(
                            "declared_application_id"
                        ),
                        "installed_app_id": values.get("installed_app_id"),
                        "entry_page_id": values["entry_page_id"],
                        "label": values["label"],
                        "description": values.get("description"),
                        "required_roles": _json_bind_value(
                            values.get("required_roles")
                        ),
                        "icon": values.get("icon"),
                        "card_title": values.get("card_title"),
                        "card_subtitle": values.get("card_subtitle"),
                        "install_status": values["install_status"],
                        "install_log": values.get("install_log"),
                        "last_error_message": values.get("last_error_message"),
                        "enabled": "Y" if values.get("enabled") else "N",
                    },
                )
            session.commit()
        except Exception as exc:
            raise PluginRegistryError(
                f"Unable to record plugin APEX app registry state: {exc}"
            ) from exc
        finally:
            _close_quietly(session)

    def list_enabled(self) -> list[dict[str, Any]]:
        """Return launchable plugin APEX applications for menu surfaces."""
        return self._query(
            f"select {self._MENU_SELECT_COLUMNS} "
            "from orac_code.plugin_apex_app_menu_v order by plugin_id, label",
            {},
        )

    def _query(self, sql: str, binds: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute a read against approved ORAC_CODE plugin APEX app views."""
        session = None
        try:
            session = self._connect()
            with session.cursor() as cursor:
                cursor.execute(sql, binds)
                columns = [description[0].lower() for description in cursor.description]
                return [
                    dict(zip(columns, row, strict=True)) for row in cursor.fetchall()
                ]
        except Exception as exc:
            raise PluginRegistryError(
                f"Unable to read plugin APEX app registry: {exc}"
            ) from exc
        finally:
            if session is not None:
                _close_quietly(session)

    def _connect(self) -> Any:
        """Return an ORAC runtime database session."""
        return self._session_factory()


def _default_session() -> Any:
    """Open the saved Orac runtime database connection."""
    from lib.config_mgr import ConfigManager
    from lib.fsutils import project_home
    from lib.session_manager import DBSession
    from lib.user_security import UserSecurity

    config_mgr = ConfigManager(
        config_file_path=project_home() / "resources" / "config" / "orac.ini"
    )
    project_identifier = config_mgr.config_value(
        section="global",
        key="project_identifier",
        default="Orac",
    )
    security = UserSecurity(project_identifier=project_identifier, resource_type="dsn")
    username, password, dsn = security.named_connection_creds(connection_name="orac")
    wallet = security.connection_property(
        connection_name="orac",
        property_key="wallet_zip_path",
        default_value="",
    )
    return DBSession(
        wallet_zip_path=wallet or "",
        verbose=False,
        user=username,
        password=password,
        dsn=dsn,
    )


def _close_quietly(session: Any) -> None:
    """Close a database session without masking the primary operation result."""
    try:
        session.close()
    except Exception:
        pass


def _bounded_lifecycle_json(value: dict[str, Any]) -> dict[str, Any]:
    """Validate bounded journal objects before opening a database session."""
    if not isinstance(value, dict):
        raise PluginRegistryError("Plugin lifecycle metadata must be a JSON object.")
    try:
        encoded = json.dumps(value, allow_nan=False, ensure_ascii=False)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise PluginRegistryError(
            "Plugin lifecycle metadata is not valid JSON."
        ) from exc
    if len(encoded.encode("utf-8")) > 65536:
        raise PluginRegistryError("Plugin lifecycle metadata exceeds 64 KiB.")
    return value


def _json_bind_value(value: Any) -> Any:
    """Return a Python value suitable for an Oracle native JSON bind."""
    if value is None or isinstance(value, (dict, list, bool, int, float)):
        return value
    return json.loads(str(value))


_UPSERT_BLOCK = """
begin
  orac_code.plugin_registry_api.upsert_plugin(
    p_plugin_id                => :plugin_id,
    p_plugin_name              => :plugin_name,
    p_plugin_version           => :plugin_version,
    p_runtime_mode             => :runtime_mode,
    p_manifest_hash            => :manifest_hash,
    p_package_hash             => :package_hash,
    p_install_source_type      => :install_source_type,
    p_install_source_ref       => :install_source_ref,
    p_installed_path           => :installed_path,
    p_config_path              => :config_path,
    p_capabilities_summary     => :capabilities_summary,
    p_entitlements_summary     => :entitlements_summary,
    p_database_schemas_summary => :database_schemas_summary,
    p_ui_icon_class            => :ui_icon_class,
    p_ui_accent_class          => :ui_accent_class,
    p_dependency_declarations  => :dependency_declarations,
    p_dependency_fingerprint   => :dependency_fingerprint,
    p_command_dependency_declarations => :command_dependency_declarations,
    p_command_dependency_fingerprint  => :command_dependency_fingerprint,
    p_command_prerequisite_status     => :command_prerequisite_status,
    p_command_dependency_report       => :command_dependency_report,
    p_install_status           => :install_status,
    p_configuration_status     => :configuration_status,
    p_dependency_status        => :dependency_status,
    p_database_status          => :database_status,
    p_readiness_status         => :readiness_status,
    p_enabled                  => :enabled,
    p_last_error_code          => :last_error_code,
    p_last_error_message       => :last_error_message
  );
end;
"""


_APEX_APP_UPSERT_BLOCK = """
begin
  orac_code.plugin_apex_app_registry_api.upsert_app(
    p_plugin_id               => :plugin_id,
    p_plugin_version          => :plugin_version,
    p_app_alias               => :app_alias,
    p_workspace               => :workspace,
    p_parsing_schema          => :parsing_schema,
    p_app_export              => :app_export,
    p_declared_application_id => :declared_application_id,
    p_installed_app_id        => :installed_app_id,
    p_entry_page_id           => :entry_page_id,
    p_label                   => :label,
    p_description             => :description,
    p_required_roles          => :required_roles,
    p_icon                    => :icon,
    p_card_title              => :card_title,
    p_card_subtitle           => :card_subtitle,
    p_install_status          => :install_status,
    p_install_log             => :install_log,
    p_last_error_message      => :last_error_message,
    p_enabled                 => :enabled
  );
end;
"""
