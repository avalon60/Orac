"""Install plugin-supplied APEX application exports."""
# Author: Clive Bostock
# Date: 2026-06-20
# Description: Provides the controlled installer boundary for plugin APEX apps.

from __future__ import annotations

from dataclasses import dataclass
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


class DockerPluginApexAppInstaller:
    """Import plugin APEX exports inside the Oracle container using sqlplus."""

    _APP_ID_MARKER = re.compile(r"ORAC_PLUGIN_APEX_APP_ID=(\d+)")

    def __init__(
        self,
        *,
        container_name: str = "orac-db",
        project_root: Path | None = None,
        command_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        logger: Any | None = None,
    ) -> None:
        """Initialise the Docker-backed APEX importer."""
        from lib.fsutils import project_home

        self._container_name = container_name
        self._project_root = Path(project_root or project_home()).resolve()
        self._command_runner = command_runner or subprocess.run
        self._logger = logger

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
                self._container_name,
                "mkdir",
                "-p",
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
        target = f"{self._container_name}:/home/oracle/orac/bin/install-plugin-apex-app.sh"
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
        result = self._command_runner(command, text=True, capture_output=True)
        if result.returncode != 0:
            output = _combined_output(result).strip()
            message = f"Unable to {action}: {output or result.returncode}"
            raise PluginApexAppInstallError(message)
        return result


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    """Return stdout and stderr without dropping importer diagnostics."""
    return "\n".join(part for part in (result.stdout, result.stderr) if part)


def _safe_path_part(value: str) -> str:
    """Return a conservative filesystem path segment for container staging."""
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    if not cleaned:
        raise PluginApexAppInstallError("Unable to derive safe APEX staging path")
    return cleaned
