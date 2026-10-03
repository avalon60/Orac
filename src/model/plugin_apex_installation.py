"""Install plugin-supplied APEX application exports."""

# Author: Clive Bostock
# Date: 2026-06-20
# Description: Provides the controlled installer boundary for plugin APEX apps.

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable, Protocol

from model.plugin_routing.models import PluginApexApp, PluginManifest


class PluginApexAppInstallError(RuntimeError):
    """Raised when a plugin APEX application import cannot complete safely."""


@dataclass(frozen=True)
class PluginApexAppInstallResult:
    """Summarise one plugin APEX application import attempt."""

    plugin_id: str
    plugin_version: str
    app_alias: str
    workspace: str
    parsing_schema: str
    app_export: str
    declared_application_id: int | None
    installed_app_id: int | None
    install_status: str
    install_log: str
    last_error_message: str | None = None


class PluginApexAppInstaller(Protocol):
    """Side-effect boundary used by PluginInstaller for APEX app imports."""

    def install(
        self,
        manifest: PluginManifest,
        app: PluginApexApp,
    ) -> PluginApexAppInstallResult:
        """Import one required plugin APEX application."""

    def removal_inventory(
        self,
        manifest: PluginManifest,
        *,
        plugin_registry_id: int,
        database_identity: str,
        removal_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Inspect declared APEX apps and verify privileged ownership receipts."""

    def remove(
        self,
        manifest: PluginManifest,
        *,
        plugin_registry_id: int,
        database_identity: str,
        removal_id: str,
    ) -> None:
        """Disable and remove receipted applications for an authorized operation."""


class DockerPluginApexAppInstaller:
    """Import plugin APEX exports inside the Oracle container using sqlplus."""

    _APP_ID_MARKER = re.compile(r"ORAC_PLUGIN_APEX_APP_ID=(\d+)")

    def __init__(
        self,
        *,
        container_name: str = "orac-db",
        project_root: Path | None = None,
        command_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        oracle_pdb: str = "FREEPDB1",
        logger: Any | None = None,
    ) -> None:
        """Initialise the Docker-backed APEX importer."""
        from lib.fsutils import project_home

        self._container_name = container_name
        self._project_root = Path(project_root or project_home()).resolve()
        self._command_runner = command_runner or subprocess.run
        self._logger = logger
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", oracle_pdb):
            raise PluginApexAppInstallError("Invalid host Oracle PDB.")
        self._oracle_pdb = oracle_pdb.upper()

    def install(
        self,
        manifest: PluginManifest,
        app: PluginApexApp,
    ) -> PluginApexAppInstallResult:
        """Import a plugin APEX app export and return the installed app id."""
        export_path = (manifest.plugin_dir / app.app_export).resolve()
        if not export_path.is_file():
            raise PluginApexAppInstallError(
                f"Plugin APEX app '{app.alias}' declares missing export: {app.app_export}"
            )
        if not export_path.is_relative_to(manifest.plugin_dir.resolve()):
            raise PluginApexAppInstallError(
                f"Plugin APEX app '{app.alias}' export is outside the plugin package."
            )

        self._sync_helper_script()
        container_export = (
            f"/home/oracle/orac/plugin_staging/{_safe_path_part(manifest.plugin_id)}/"
            f"{_safe_path_part(manifest.version)}/apex/{_safe_path_part(export_path.name)}"
        )
        self._run(
            [
                "docker",
                "exec",
                "--user",
                "0",
                self._container_name,
                "install",
                "-d",
                "-o",
                "54321",
                "-g",
                "54321",
                "-m",
                "750",
                Path(container_export).parent.as_posix(),
            ],
            "prepare APEX export staging directory",
        )
        self._run(
            [
                "docker",
                "cp",
                str(export_path),
                f"{self._container_name}:{container_export}",
            ],
            "copy plugin APEX export",
        )

        command = [
            "docker",
            "exec",
            self._container_name,
            "env",
            f"ORACLE_PDB={self._oracle_pdb}",
            "/home/oracle/orac/bin/install-plugin-apex-app.sh",
            "--plugin-id",
            manifest.plugin_id,
            "--plugin-version",
            manifest.version,
            "--app-alias",
            app.alias,
            "--workspace",
            app.workspace,
            "--parsing-schema",
            app.parsing_schema,
            "--export",
            container_export,
            "--entry-page-id",
            str(app.entry_page_id),
        ]
        if app.application_id is not None:
            command.extend(["--application-id", str(app.application_id)])
        if app.replace_existing:
            command.append("--replace-existing")

        result = self._run(command, f"import plugin APEX app {app.alias}")
        output = _combined_output(result)
        marker = self._APP_ID_MARKER.search(output)
        if marker is None:
            raise PluginApexAppInstallError(
                f"Plugin APEX app '{app.alias}' import did not report an installed application id."
            )
        return PluginApexAppInstallResult(
            plugin_id=manifest.plugin_id,
            plugin_version=manifest.version,
            app_alias=app.alias,
            workspace=app.workspace,
            parsing_schema=app.parsing_schema,
            app_export=app.app_export,
            declared_application_id=app.application_id,
            installed_app_id=int(marker.group(1)),
            install_status="installed",
            install_log=output,
        )

    def removal_inventory(
        self,
        manifest: PluginManifest,
        *,
        plugin_registry_id: int,
        database_identity: str,
        removal_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Inspect declared APEX apps and verify privileged ownership receipts."""
        output = self._maintenance(
            manifest,
            plugin_registry_id=plugin_registry_id,
            database_identity=database_identity,
            removal_id=removal_id,
            remove=False,
        )
        prefix = "ORAC_PLUGIN_APEX_INVENTORY:"
        records = [
            line[len(prefix) :]
            for line in output.splitlines()
            if line.startswith(prefix)
        ]
        if len(records) != 1:
            raise PluginApexAppInstallError("APEX inventory was not confirmed.")
        try:
            inventory = json.loads(records[0])
        except ValueError as exc:
            raise PluginApexAppInstallError("APEX inventory was invalid.") from exc
        if not isinstance(inventory, list) or len(inventory) != len(manifest.apex_apps):
            raise PluginApexAppInstallError(
                "APEX inventory did not match declarations."
            )
        return inventory

    def remove(
        self,
        manifest: PluginManifest,
        *,
        plugin_registry_id: int,
        database_identity: str,
        removal_id: str,
    ) -> None:
        """Disable and remove receipted applications for an authorized operation."""
        output = self._maintenance(
            manifest,
            plugin_registry_id=plugin_registry_id,
            database_identity=database_identity,
            removal_id=removal_id,
            remove=True,
        )
        if "ORAC_PLUGIN_APEX_REMOVAL_OK" not in output.splitlines():
            raise PluginApexAppInstallError("APEX removal was not confirmed.")

    def _maintenance(
        self,
        manifest: PluginManifest,
        *,
        plugin_registry_id: int,
        database_identity: str,
        removal_id: str | None,
        remove: bool,
    ) -> str:
        """Use the existing administrative container boundary for APEX cleanup."""
        sql = _apex_removal_sql(
            manifest,
            oracle_pdb=self._oracle_pdb,
            plugin_registry_id=plugin_registry_id,
            database_identity=database_identity,
            removal_id=removal_id,
            remove=remove,
        )
        return _combined_output(
            self._run(
                [
                    "docker",
                    "exec",
                    self._container_name,
                    "bash",
                    "-lc",
                    "sqlplus -L -s / as sysdba <<'SQL'\n" + sql + "\nSQL",
                ],
                "verify and clean up plugin APEX applications",
            )
        )

    def _sync_helper_script(self) -> None:
        """Copy the repo helper script into the Oracle container."""
        source = (
            self._project_root
            / "resources"
            / "docker"
            / "oracle"
            / "bin"
            / "install-plugin-apex-app.sh"
        )
        if not source.is_file():
            raise PluginApexAppInstallError(f"Missing helper script: {source}")
        target = (
            f"{self._container_name}:/home/oracle/orac/bin/install-plugin-apex-app.sh"
        )
        self._run(["docker", "cp", str(source), target], "copy plugin APEX helper")
        self._run(
            [
                "docker",
                "exec",
                "--user",
                "0",
                self._container_name,
                "chmod",
                "755",
                "/home/oracle/orac/bin/install-plugin-apex-app.sh",
            ],
            "mark plugin APEX helper executable",
        )

    def _run(
        self,
        command: list[str],
        action: str,
    ) -> subprocess.CompletedProcess[str]:
        """Run one subprocess command and raise with captured output on failure."""
        try:
            result = self._command_runner(
                command, text=True, capture_output=True, timeout=180
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PluginApexAppInstallError(
                f"Unable to {action}; inspect actual APEX state before retry."
            ) from exc
        if result.returncode != 0:
            output = _combined_output(result).strip()
            message = f"Unable to {action}: {output or result.returncode}"
            raise PluginApexAppInstallError(message)
        return result


def _apex_removal_sql(
    manifest: PluginManifest,
    *,
    oracle_pdb: str,
    plugin_registry_id: int,
    database_identity: str,
    removal_id: str | None,
    remove: bool,
) -> str:
    """Build receipt checks and optional application-only cleanup.

    Shared workspace and parsing schema are never deleted. Active gateway
    requests and application automations block cleanup instead of being killed.
    """
    from model.plugin_database_deployment import _sql_literal, _schema_identifier

    if (
        not re.fullmatch(r"[a-z][a-z0-9_]*", manifest.plugin_id)
        or type(plugin_registry_id) is not int
        or plugin_registry_id <= 0
        or not database_identity
        or len(database_identity) > 256
        or "\n" in database_identity
        or "\r" in database_identity
        or (removal_id is not None and not re.fullmatch(r"[a-fA-F0-9]{32}", removal_id))
        or (remove and not removal_id)
    ):
        raise PluginApexAppInstallError("Invalid APEX removal authorization.")
    pdb = _schema_identifier(oracle_pdb)
    database = _sql_literal(database_identity)
    plugin = _sql_literal(manifest.plugin_id)
    operation = _sql_literal(removal_id) if removal_id else "null"
    blocks: list[str] = []
    for app in manifest.apex_apps:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", app.alias):
            raise PluginApexAppInstallError("Invalid APEX app alias.")
        alias = _sql_literal(app.alias.upper())
        workspace = _sql_literal(_schema_identifier(app.workspace))
        parser = _sql_literal(_schema_identifier(app.parsing_schema))
        cleanup = (
            f"""
    select count(*) into l_count from json_table(l_inventory, '$.apex[*]'
      columns (app_alias varchar2(128) path '$.app_alias',
               receipt clob format json path '$.receipt')) authorized
     where authorized.app_alias = {alias}
       and json_equal(authorized.receipt, l_receipt);
    if l_count <> 1 then
      raise_application_error(-20079, 'APEX receipt differs from authorized inventory.');
    end if;
    if l_actual_id is not null then
      apex_util.set_application_status(
        p_application_id => l_actual_id, p_application_status => 'UNAVAILABLE',
        p_unavailable_value => 'This plugin is being removed.');
      commit;
      select count(*) into l_count from gv$session
       where status = 'ACTIVE'
         and (username in ({parser}, 'ORDS_PUBLIC_USER', 'APEX_PUBLIC_USER')
              or username like 'APEX\\_%' escape '\\' or module like 'APEX%');
      if l_count <> 0 then
        raise_application_error(-20079, 'Active APEX requests block removal; retry after maintenance quiescence.');
      end if;
      -- Recheck after disabling: never act on a replacement at the same ID.
      if nvl(apex_app_setting.get_value('ORAC_INSTALL_RECEIPT'), '!') <>
         json_value(l_receipt, '$.marker') then
        raise_application_error(-20079, 'APEX installation marker changed.');
      end if;
      apex_application_install.remove_application(p_application_id => l_actual_id);
      commit;
      select count(*) into l_count from apex_applications
       where application_id = l_actual_id;
      if l_count <> 0 then
        raise_application_error(-20079, 'APEX application removal was not verified.');
      end if;
    end if;
"""
            if remove
            else ""
        )
        blocks.append(f"""
declare
  l_receipt json;
  l_receipt_clob clob;
  l_expected_id number;
  l_install_status varchar2(64);
  l_actual_id number;
  l_workspace_id number;
  l_count number;
  l_item json_object_t := json_object_t();
begin
  begin
    select installation_receipt, installed_app_id, install_status into l_receipt, l_expected_id, l_install_status
      from orac_api.plugin_apex_apps_v
     where plugin_id = {plugin} and upper(app_alias) = {alias}
       and upper(workspace) = {workspace} and upper(parsing_schema) = {parser};
  exception when no_data_found then null;
  end;
  select workspace_id into l_workspace_id from apex_workspaces where workspace = {workspace};
  apex_util.set_security_group_id(l_workspace_id);
  begin
    select application_id into l_actual_id from apex_applications
     where (workspace = {workspace} and alias = {alias}) or application_id = l_expected_id;
  exception when no_data_found then null;
  end;
  if l_receipt is null then
    if l_expected_id is not null or (l_actual_id is not null and {1 if app.install_required else 0} = 1) then
      raise_application_error(-20079, 'APEX application ownership is not proven.');
    end if;
  else
    select count(*) into l_count from dual
     where json_value(l_receipt, '$.plugin_registry_id' returning number) = {plugin_registry_id}
       and json_value(l_receipt, '$.database_identity') = {database}
       and json_value(l_receipt, '$.workspace_id' returning number) = l_workspace_id
       and json_value(l_receipt, '$.application_id' returning number) = l_expected_id
       and regexp_like(json_value(l_receipt, '$.marker'), '^[A-Fa-f0-9]{{32}}$');
    if l_count <> 1 or l_expected_id in (1042, 1043, 10042) then
      raise_application_error(-20079, 'APEX receipt target is inconsistent or protected.');
    end if;
    if l_actual_id is null then
      if {operation} is null then
        raise_application_error(-20079, 'Missing APEX application requires removal recovery.');
      end if;
    else
      select count(*) into l_count from apex_applications
       where application_id = l_expected_id and application_id = l_actual_id
         and workspace = {workspace} and alias = {alias} and owner = {parser};
      if l_count <> 1 then
        raise_application_error(-20079, 'APEX application identity changed.');
      end if;
      apex_application.g_flow_id := l_actual_id;
      if nvl(apex_app_setting.get_value('ORAC_INSTALL_RECEIPT'), '!') <>
         json_value(l_receipt, '$.marker') then
        raise_application_error(-20079, 'APEX application marker does not match receipt.');
      end if;
      select count(*) into l_count from apex_appl_automations where application_id = l_actual_id;
      if l_count <> 0 then
        raise_application_error(-20079, 'Unmanaged APEX automations block removal.');
      end if;
    end if;
    {cleanup}
  end if;
  l_item.put('app_alias', {alias});
  l_item.put('workspace', {workspace});
  l_item.put('parsing_schema', {parser});
  l_item.put('application_id', l_expected_id);
  l_item.put('install_status', l_install_status);
  l_item.put('present', case when l_actual_id is null then 0 else 1 end);
  if l_receipt is null then
    l_item.put_null('receipt');
  else
    select json_serialize(l_receipt returning clob) into l_receipt_clob from dual;
    l_item.put('receipt', json_element_t.parse(l_receipt_clob));
  end if;
  l_apps.append(l_item);
end;
""")
    aliases = (
        ", ".join(_sql_literal(app.alias.upper()) for app in manifest.apex_apps)
        or "null"
    )
    return f"""whenever sqlerror exit failure rollback
whenever oserror exit failure rollback
set define off echo off feedback off serveroutput on size unlimited linesize 32767
alter session set container = {pdb};
set serveroutput on size unlimited
declare
  l_database_identity varchar2(256);
  l_inventory json;
  l_count number;
  l_apps json_array_t := json_array_t();
begin
  if sys_context('userenv', 'session_user') <> 'SYS' then
    raise_application_error(-20078, 'Privileged host APEX cleanup is required.');
  end if;
  select to_char(dbid) || ':' || rawtohex(guid) || ':' || name
    into l_database_identity from v$pdbs
   where con_id = to_number(sys_context('userenv', 'con_id'))
     and name = '{pdb}' and open_mode = 'READ WRITE';
  if l_database_identity <> {database} then
    raise_application_error(-20079, 'APEX database identity changed.');
  end if;
  select count(*) into l_count from orac_code.plugin_registry_v
   where plugin_id = {plugin} and plugin_registry_id = {plugin_registry_id}
     and (removal_id = {operation} or removal_id is null and {operation} is null);
  if l_count <> 1 then
    raise_application_error(-20079, 'APEX registration or removal fence changed.');
  end if;
  select count(*) into l_count from orac_api.plugin_apex_apps_v
   where plugin_id = {plugin} and {f'upper(app_alias) not in ({aliases})' if manifest.apex_apps else '1 = 1'};
  if l_count <> 0 then
    raise_application_error(-20079, 'Registered APEX inventory differs from the manifest.');
  end if;
  if {operation} is not null then
    select resource_inventory into l_inventory from orac_api.plugin_removals_v
     where removal_id = {operation} and plugin_registry_id = {plugin_registry_id}
       and database_identity = {database} and completed_on is null;
  end if;
  {chr(10).join(blocks)}
  dbms_output.put_line('ORAC_PLUGIN_APEX_INVENTORY:' || l_apps.to_string());
end;
/
{"prompt ORAC_PLUGIN_APEX_REMOVAL_OK" if remove else ""}
exit success
"""


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    """Return stdout and stderr without dropping importer diagnostics."""
    return "\n".join(part for part in (result.stdout, result.stderr) if part)


def _safe_path_part(value: str) -> str:
    """Return a conservative filesystem path segment for container staging."""
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    if not cleaned:
        raise PluginApexAppInstallError("Unable to derive safe APEX staging path")
    return cleaned
