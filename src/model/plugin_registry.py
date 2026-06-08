"""Persist and resolve active Orac plugin installation registry records."""
# Author: Clive Bostock
# Date: 07-Jun-2026
# Description: Mediates plugin registry access through approved Oracle APIs.

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from model.plugin_routing.discovery import PluginDiscovery
from model.plugin_routing.models import PluginManifest


class PluginRegistryError(RuntimeError):
    """Raised when plugin registry access cannot complete safely."""


class PluginRegistryStore:
    """Read and update plugin registry state through ORAC_CODE surfaces."""

    _SELECT_COLUMNS = (
        "plugin_id, plugin_name, plugin_version, runtime_mode, manifest_hash, "
        "package_hash, install_source_type, install_source_ref, installed_path, "
        "config_path, dependency_fingerprint, install_status, configuration_status, "
        "dependency_status, database_status, readiness_status, enabled, "
        "last_error_code, last_error_message, row_version"
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
                        "capabilities_summary": values.get("capabilities_summary"),
                        "entitlements_summary": values.get("entitlements_summary"),
                        "database_schemas_summary": values.get(
                            "database_schemas_summary"
                        ),
                        "dependency_declarations": values.get(
                            "dependency_declarations"
                        ),
                        "dependency_fingerprint": values["dependency_fingerprint"],
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

    def list_enabled(self) -> list[dict[str, Any]]:
        """Return registry rows that passed every runtime eligibility gate."""
        return self._query(
            f"select {self._SELECT_COLUMNS} "
            "from orac_code.plugin_registry_v "
            "where enabled = 'Y' "
            "and install_status = 'success' "
            "and configuration_status in ('success', 'not_required') "
            "and dependency_status in ('success', 'not_required') "
            "and database_status in "
            "('deployed', 'already_deployed', 'not_required', 'optional_missing') "
            "and readiness_status = 'success' order by plugin_id",
            {},
        )

    def enabled_manifests(self) -> list[PluginManifest]:
        """Load validated manifests for active installed plugin versions."""
        manifests: list[PluginManifest] = []
        for row in self.list_enabled():
            installed_path = Path(str(row["installed_path"] or ""))
            manifest_path = installed_path / "manifest.json"
            plugin_dir = installed_path / "plugin"
            if not manifest_path.is_file() or not plugin_dir.is_dir():
                raise PluginRegistryError(
                    f"Registered plugin files are missing for '{row['plugin_id']}'."
                )
            manifest = PluginDiscovery(installed_path).load_manifest(
                manifest_path,
                plugin_dir=plugin_dir,
                enforce_filename=False,
            )
            if manifest.manifest_hash != row["manifest_hash"]:
                raise PluginRegistryError(
                    f"Registered manifest hash mismatch for '{manifest.plugin_id}'."
                )
            manifests.append(
                replace(
                    manifest,
                    config_path=(
                        Path(str(row["config_path"]))
                        if row.get("config_path")
                        else None
                    ),
                )
            )
        return manifests

    def _query(self, sql: str, binds: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute a read against the approved ORAC_CODE registry view."""
        session = self._connect()
        try:
            with session.cursor() as cursor:
                cursor.execute(sql, binds)
                columns = [description[0].lower() for description in cursor.description]
                return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        except Exception as exc:
            raise PluginRegistryError(f"Unable to read plugin registry: {exc}") from exc
        finally:
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


_UPSERT_BLOCK = """
declare
  l_capabilities_summary     json;
  l_entitlements_summary     json;
  l_database_schemas_summary json;
  l_dependency_declarations  json;
begin
  if :capabilities_summary is not null then
    l_capabilities_summary := json(:capabilities_summary);
  end if;
  if :entitlements_summary is not null then
    l_entitlements_summary := json(:entitlements_summary);
  end if;
  if :database_schemas_summary is not null then
    l_database_schemas_summary := json(:database_schemas_summary);
  end if;
  if :dependency_declarations is not null then
    l_dependency_declarations := json(:dependency_declarations);
  end if;

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
    p_capabilities_summary     => l_capabilities_summary,
    p_entitlements_summary     => l_entitlements_summary,
    p_database_schemas_summary => l_database_schemas_summary,
    p_dependency_declarations  => l_dependency_declarations,
    p_dependency_fingerprint   => :dependency_fingerprint,
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
