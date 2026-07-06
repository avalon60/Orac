"""Tests for Orac plugin packaging and dependency installation."""
# Author: Clive Bostock
# Date: 07-Jun-2026
# Description: Verifies safe plugin archives, dependencies, and installation gates.

from __future__ import annotations

from dataclasses import dataclass
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from model.plugin_dependencies import PluginDependencyError
from model.plugin_dependencies import PluginDependencyInstaller
from model.plugin_dependencies import normalise_requirements
from model.plugin_dependencies import validate_requirements_mirror
from model.plugin_apex_installation import PluginApexAppInstallError
from model.plugin_apex_installation import PluginApexAppInstallResult
from model.plugin_apex_installation import DockerPluginApexAppInstaller
from model.plugin_installer import PluginInstallationError
from model.plugin_installer import PluginInstaller
from model.plugin_installer import _clamp_registry_text
from model.plugin_package import PluginPackageBuilder
from model.plugin_package import PluginPackageError
from model.plugin_package import PluginPackageReader
from model.plugin_routing.discovery import PluginDiscovery


@dataclass(frozen=True)
class _DatabaseResult:
    eligible: bool = True
    status: str = "not_required"
    message: str = "No database payload required."


class _DatabaseDeployer:
    def __init__(self, result: _DatabaseResult | None = None) -> None:
        self.result = result or _DatabaseResult()
        self.calls: list[str] = []

    def deploy_if_needed(self, manifest):
        self.calls.append(manifest.plugin_id)
        return self.result


class _DependencyInstaller:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def install(self, requirements):
        self.calls.append(tuple(requirements))
        return type(
            "DependencyResult",
            (),
            {"status": "success" if requirements else "not_required"},
        )()


class _Registry:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    def record(self, values):
        self.rows[values["plugin_id"]] = dict(values)

    def get(self, plugin_id):
        return self.rows.get(plugin_id)

    def list_all(self):
        return list(self.rows.values())


class _FailingRecordRegistry(_Registry):
    def record(self, values):
        raise RuntimeError("mock registry write failure")


class _ApexAppRegistry:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def record(self, values):
        self.rows.append(dict(values))


class _ApexAppInstaller:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[str, str]] = []

    def install(self, manifest, app):
        self.calls.append((manifest.plugin_id, app.alias))
        if self.fail:
            raise PluginApexAppInstallError("mock APEX import failure")
        return PluginApexAppInstallResult(
            plugin_id=manifest.plugin_id,
            plugin_version=manifest.version,
            app_alias=app.alias,
            workspace=app.workspace,
            parsing_schema=app.parsing_schema,
            app_export=app.app_export,
            declared_application_id=app.application_id,
            installed_app_id=2042,
            install_status="installed",
            install_log="ORAC_PLUGIN_APEX_APP_ID=2042",
        )


class PluginDependencyTests(unittest.TestCase):
    """Validate manifest requirements and safe pip invocation."""

    def test_normalises_supported_requirements(self) -> None:
        self.assertEqual(
            normalise_requirements(
                ["requests>=2.32,<3", 'httpx[http2]>=0.27; python_version >= "3.11"']
            ),
            (
                'httpx[http2]>=0.27; python_version >= "3.11"',
                "requests<3,>=2.32",
            ),
        )

    def test_rejects_direct_reference_and_pip_option(self) -> None:
        for value in (
            ["package @ https://example.com/package.whl"],
            ["--extra-index-url=https://example.com"],
            ["../local-package"],
        ):
            with self.subTest(value=value):
                with self.assertRaises(PluginDependencyError):
                    normalise_requirements(value)

    def test_dependency_installer_uses_argument_lists_without_shell(self) -> None:
        calls: list[tuple[list[str], dict]] = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0, "", "")

        installer = PluginDependencyInstaller(runner=runner, interpreter="python-test")
        installer.install(["requests>=2.32,<3"])

        self.assertEqual(calls[0][0][:4], ["python-test", "-m", "pip", "install"])
        self.assertEqual(calls[1][0], ["python-test", "-m", "pip", "check"])
        self.assertNotIn("shell", calls[0][1])

    def test_dependency_failure_redacts_package_index_credentials(self) -> None:
        def runner(command, **_kwargs):
            return subprocess.CompletedProcess(
                command,
                1,
                "",
                "Looking in indexes: https://user:secret@example.test/simple",
            )

        installer = PluginDependencyInstaller(runner=runner, interpreter="python-test")
        with self.assertRaises(PluginDependencyError) as raised:
            installer.install(["requests>=2.32,<3"])

        self.assertNotIn("secret", str(raised.exception))
        self.assertIn("https://***@example.test/simple", str(raised.exception))

    def test_requirements_mirror_must_match_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "requirements.txt"
            path.write_text("requests>=2.32,<3\n", encoding="utf-8")
            validate_requirements_mirror(path, ("requests<3,>=2.32",))
            path.write_text("httpx>=0.27\n", encoding="utf-8")
            with self.assertRaises(PluginDependencyError):
                validate_requirements_mirror(path, ("requests<3,>=2.32",))


class PluginPackageTests(unittest.TestCase):
    """Verify deterministic package shape and safe extraction."""

    def test_home_assistant_package_has_expected_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = PluginPackageBuilder().package(
                PROJECT_ROOT / "plugins" / "home_assistant",
                Path(temp_dir),
            )
            with tarfile.open(archive, "r:gz") as package:
                names = set(package.getnames())
            self.assertIn("manifest.json", names)
            self.assertIn("plugin/plugin.py", names)
            self.assertIn("plugin/apex/f10010.sql", names)
            self.assertIn("plugin/plugin.ini.example", names)
            self.assertIn("requirements.txt", names)
            self.assertNotIn("plugin/plugin.ini", names)

    def test_package_output_is_deterministic(self) -> None:
        with (
            tempfile.TemporaryDirectory() as first_dir,
            tempfile.TemporaryDirectory() as second_dir,
        ):
            first = PluginPackageBuilder().package(
                PROJECT_ROOT / "plugins" / "home_assistant",
                Path(first_dir),
            )
            second = PluginPackageBuilder().package(
                PROJECT_ROOT / "plugins" / "home_assistant",
                Path(second_dir),
            )
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_apex_helper_chmod_runs_as_container_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            helper = root / "resources" / "docker" / "oracle" / "bin"
            helper.mkdir(parents=True)
            (helper / "install-plugin-apex-app.sh").write_text(
                "#!/usr/bin/env bash\n",
                encoding="utf-8",
            )
            commands: list[list[str]] = []

            def runner(command, **_kwargs):
                commands.append(command)
                return subprocess.CompletedProcess(command, 0, "", "")

            installer = DockerPluginApexAppInstaller(
                project_root=root,
                command_runner=runner,
            )

            installer._sync_helper_script()

            self.assertEqual(
                commands[1][:5], ["docker", "exec", "--user", "0", "orac-db"]
            )
            self.assertIn("chmod", commands[1])

    def test_apex_helper_reuses_existing_app_without_replacement(self) -> None:
        helper = (
            PROJECT_ROOT
            / "resources"
            / "docker"
            / "oracle"
            / "bin"
            / "install-plugin-apex-app.sh"
        ).read_text(encoding="utf-8")

        reuse_index = helper.index("reusing application")
        import_index = helper.index("@${EXPORT_FILE}")

        self.assertIn('if [[ -n "${EXISTING_APP_ID}"', helper)
        self.assertIn('"${REPLACE_EXISTING}" != "Y"', helper)
        self.assertIn("ORAC_PLUGIN_APEX_APP_ID=${EXISTING_APP_ID}", helper)
        self.assertIn("exit 0", helper[reuse_index:import_index])
        self.assertIn("--replace-existing", helper)
        self.assertLess(reuse_index, import_index)

    def test_reader_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = Path(temp_dir) / "unsafe.tar.gz"
            with tarfile.open(archive, "w:gz") as package:
                info = tarfile.TarInfo("../escape")
                info.size = 1
                package.addfile(info, io.BytesIO(b"x"))
            with self.assertRaises(PluginPackageError):
                PluginPackageReader().extract(archive, Path(temp_dir) / "stage")

    def test_reader_rejects_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = Path(temp_dir) / "unsafe.tar.gz"
            with tarfile.open(archive, "w:gz") as package:
                info = tarfile.TarInfo("/absolute/path")
                info.size = 1
                package.addfile(info, io.BytesIO(b"x"))
            with self.assertRaises(PluginPackageError):
                PluginPackageReader().extract(archive, Path(temp_dir) / "stage")

    def test_reader_rejects_links(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = Path(temp_dir) / "unsafe.tar.gz"
            with tarfile.open(archive, "w:gz") as package:
                info = tarfile.TarInfo("plugin/link")
                info.type = tarfile.SYMTYPE
                info.linkname = "/etc/passwd"
                package.addfile(info)
            with self.assertRaises(PluginPackageError):
                PluginPackageReader().extract(archive, Path(temp_dir) / "stage")

    def test_reader_rejects_hardlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = Path(temp_dir) / "unsafe.tar.gz"
            with tarfile.open(archive, "w:gz") as package:
                info = tarfile.TarInfo("plugin/link")
                info.type = tarfile.LNKTYPE
                info.linkname = "plugin/plugin.py"
                package.addfile(info)
            with self.assertRaises(PluginPackageError):
                PluginPackageReader().extract(archive, Path(temp_dir) / "stage")

    def test_reader_rejects_malformed_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = Path(temp_dir) / "malformed.tar.gz"
            archive.write_bytes(b"not a tar archive")
            with self.assertRaises(PluginPackageError):
                PluginPackageReader().extract(archive, Path(temp_dir) / "stage")


class PluginInstallerTests(unittest.TestCase):
    """Verify installer sequencing, config handling, and activation."""

    def test_tarball_install_uses_versioned_generic_plugin_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = _write_source_plugin(root, "alpha")
            archive = PluginPackageBuilder().package(source, root / "dist")
            result = PluginInstaller(
                project_root=root,
                managed_root=root / "var" / "plugins",
                config_root=root / "config",
                dependency_installer=_DependencyInstaller(),
                database_deployer=_DatabaseDeployer(),
                registry=_Registry(),
            ).install_archive(archive)

            self.assertTrue(result.enabled)
            self.assertEqual(
                result.installed_path,
                root / "var" / "plugins" / "installed" / "alpha" / "1.0.0",
            )
            self.assertTrue((result.installed_path / "plugin" / "plugin.py").is_file())

    def test_source_install_activates_only_after_all_gates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = _write_source_plugin(root, "alpha")
            dependencies = _DependencyInstaller()
            database = _DatabaseDeployer()
            registry = _Registry()
            installer = PluginInstaller(
                project_root=root,
                managed_root=root / "var" / "plugins",
                config_root=root / "config",
                dependency_installer=dependencies,
                database_deployer=database,
                registry=registry,
            )

            result = installer.install_source(source)

            self.assertTrue(result.enabled)
            self.assertTrue((result.installed_path / "manifest.json").is_file())
            self.assertTrue((result.installed_path / "plugin" / "plugin.py").is_file())
            self.assertEqual(dependencies.calls, [()])
            self.assertEqual(database.calls, ["alpha"])
            self.assertTrue(registry.rows["alpha"]["enabled"])

    def test_existing_external_config_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = _write_source_plugin(root, "alpha", required_config=True)
            config_path = root / "config" / "alpha" / "plugin.ini"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("[alpha]\nhost = retained\n", encoding="utf-8")
            installer = PluginInstaller(
                project_root=root,
                managed_root=root / "var" / "plugins",
                config_root=root / "config",
                dependency_installer=_DependencyInstaller(),
                database_deployer=_DatabaseDeployer(),
                registry=_Registry(),
            )
            result = installer.install_source(source)
            self.assertTrue(result.enabled)
            self.assertIn("retained", config_path.read_text(encoding="utf-8"))

    def test_uninitialised_config_stops_before_dependencies_and_database(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = _write_source_plugin(root, "alpha", required_config=True)
            (source / "plugin.ini.example").write_text(
                "[alpha]\nhost = %host%\n",
                encoding="utf-8",
            )
            dependencies = _DependencyInstaller()
            database = _DatabaseDeployer()
            result = PluginInstaller(
                project_root=root,
                managed_root=root / "var" / "plugins",
                config_root=root / "config",
                dependency_installer=dependencies,
                database_deployer=database,
                registry=_Registry(),
            ).install_source(source)
            self.assertFalse(result.enabled)
            self.assertEqual(result.status, "configuration_failed")
            self.assertEqual(dependencies.calls, [])
            self.assertEqual(database.calls, [])

    def test_database_failure_keeps_plugin_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = _write_source_plugin(root, "alpha")
            registry = _Registry()
            result = PluginInstaller(
                project_root=root,
                managed_root=root / "var" / "plugins",
                config_root=root / "config",
                dependency_installer=_DependencyInstaller(),
                database_deployer=_DatabaseDeployer(
                    _DatabaseResult(
                        eligible=False,
                        status="deployment_failed",
                        message="mock deployment failure",
                    )
                ),
                registry=registry,
            ).install_source(source)

            self.assertFalse(result.enabled)
            self.assertEqual(result.status, "database_failed")
            self.assertFalse(registry.rows["alpha"]["enabled"])

    def test_registry_failure_rolls_back_candidate_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = _write_source_plugin(root, "alpha")
            destination = root / "var" / "plugins" / "installed" / "alpha" / "1.0.0"
            (destination / "plugin").mkdir(parents=True)
            (destination / "plugin" / "previous.txt").write_text(
                "retained",
                encoding="utf-8",
            )
            installer = PluginInstaller(
                project_root=root,
                managed_root=root / "var" / "plugins",
                config_root=root / "config",
                dependency_installer=_DependencyInstaller(),
                database_deployer=_DatabaseDeployer(),
                registry=_FailingRecordRegistry(),
            )

            with self.assertRaises(PluginInstallationError):
                installer.install_source(source)

            self.assertEqual(
                (destination / "plugin" / "previous.txt").read_text(encoding="utf-8"),
                "retained",
            )

    def test_registry_error_text_is_clamped_to_column_limit(self) -> None:
        message = "x" * 2100

        clamped = _clamp_registry_text(message, 2000)

        assert clamped is not None
        self.assertEqual(len(clamped), 2000)
        self.assertTrue(clamped.endswith("... [truncated]"))

    def test_list_plugins_combines_installed_and_unpacked_plugins(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_source_plugin(root, "alpha")
            _write_source_plugin(root, "beta")
            registry = _Registry()
            registry.rows["alpha"] = {
                "plugin_id": "alpha",
                "plugin_name": "Alpha Installed",
                "plugin_version": "1.0.0",
                "install_status": "success",
                "readiness_status": "success",
                "enabled": "Y",
                "installed_path": "var/plugins/installed/alpha/1.0.0",
            }
            registry.rows["gamma"] = {
                "plugin_id": "gamma",
                "plugin_name": "Gamma",
                "plugin_version": "2.0.0",
                "install_status": "success",
                "readiness_status": "success",
                "enabled": "N",
                "installed_path": "var/plugins/installed/gamma/2.0.0",
            }

            entries = PluginInstaller(
                project_root=root,
                managed_root=root / "var" / "plugins",
                config_root=root / "config",
                dependency_installer=_DependencyInstaller(),
                database_deployer=_DatabaseDeployer(),
                registry=registry,
            ).list_plugins()

            by_id = {entry["plugin_id"]: entry for entry in entries}
            self.assertTrue(by_id["alpha"]["installed"])
            self.assertTrue(by_id["alpha"]["unpacked"])
            self.assertFalse(by_id["beta"]["installed"])
            self.assertTrue(by_id["beta"]["unpacked"])
            self.assertTrue(by_id["gamma"]["installed"])
            self.assertFalse(by_id["gamma"]["unpacked"])

    def test_install_required_apex_surface_requires_export_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = _write_source_plugin(
                root,
                "alpha",
                extra_manifest={
                    "ui": {
                        "surfaces": [
                            {
                                "id": "alpha.admin_status",
                                "type": "admin_status",
                                "label": "Alpha Status",
                                "target": "apex",
                                "audience": "admin",
                                "enabled": True,
                                "apex": {
                                    "app_alias": "ALPHA_STATUS",
                                    "app_export": "apex/alpha_status.sql",
                                    "entry_page_id": 1,
                                    "install_required": True,
                                },
                            }
                        ]
                    }
                },
            )
            result = PluginInstaller(
                project_root=root,
                managed_root=root / "var" / "plugins",
                config_root=root / "config",
                dependency_installer=_DependencyInstaller(),
                database_deployer=_DatabaseDeployer(),
                registry=_Registry(),
            ).install_source(source)

            self.assertFalse(result.enabled)
            self.assertEqual(result.status, "readiness_failed")
            self.assertIn("missing APEX export", result.message)

    def test_required_apex_app_is_imported_and_registered(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = _write_source_plugin(
                root,
                "alpha",
                extra_manifest={
                    "apex_apps": [
                        {
                            "app_alias": "ALPHA_STATUS",
                            "label": "Alpha Status",
                            "app_export": "apex/alpha_status.sql",
                            "application_id": 1043,
                            "entry_page_id": 1,
                            "install_required": True,
                            "required_roles": ["ORAC_ADMIN"],
                            "replace_existing": True,
                        }
                    ]
                },
            )
            (source / "apex").mkdir()
            (source / "apex" / "alpha_status.sql").write_text(
                "-- export\n", encoding="utf-8"
            )
            apex_installer = _ApexAppInstaller()
            apex_registry = _ApexAppRegistry()

            result = PluginInstaller(
                project_root=root,
                managed_root=root / "var" / "plugins",
                config_root=root / "config",
                dependency_installer=_DependencyInstaller(),
                database_deployer=_DatabaseDeployer(),
                registry=_Registry(),
                apex_app_installer=apex_installer,
                apex_app_registry=apex_registry,
            ).install_source(source)

            self.assertTrue(result.enabled)
            self.assertEqual(apex_installer.calls, [("alpha", "ALPHA_STATUS")])
            self.assertEqual(apex_registry.rows[0]["install_status"], "installed")
            self.assertEqual(apex_registry.rows[0]["installed_app_id"], 2042)
            self.assertEqual(apex_registry.rows[0]["declared_application_id"], 1043)
            self.assertEqual(apex_registry.rows[0]["required_roles"], '["ORAC_ADMIN"]')

    def test_required_apex_app_failure_blocks_plugin_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = _write_source_plugin(
                root,
                "alpha",
                extra_manifest={
                    "apex_apps": [
                        {
                            "app_alias": "ALPHA_STATUS",
                            "label": "Alpha Status",
                            "app_export": "apex/alpha_status.sql",
                            "install_required": True,
                        }
                    ]
                },
            )
            (source / "apex").mkdir()
            (source / "apex" / "alpha_status.sql").write_text(
                "-- export\n", encoding="utf-8"
            )
            registry = _Registry()
            apex_registry = _ApexAppRegistry()

            result = PluginInstaller(
                project_root=root,
                managed_root=root / "var" / "plugins",
                config_root=root / "config",
                dependency_installer=_DependencyInstaller(),
                database_deployer=_DatabaseDeployer(),
                registry=registry,
                apex_app_installer=_ApexAppInstaller(fail=True),
                apex_app_registry=apex_registry,
            ).install_source(source)

            self.assertFalse(result.enabled)
            self.assertEqual(result.status, "apex_failed")
            self.assertFalse(registry.rows["alpha"]["enabled"])
            self.assertEqual(apex_registry.rows[0]["install_status"], "failed")
            self.assertIn(
                "mock APEX import failure", apex_registry.rows[0]["last_error_message"]
            )

    def test_optional_apex_app_is_registered_without_import(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = _write_source_plugin(
                root,
                "alpha",
                extra_manifest={
                    "apex_apps": [
                        {
                            "app_alias": "ALPHA_STATUS",
                            "label": "Alpha Status",
                            "app_export": "apex/alpha_status.sql",
                            "install_required": False,
                        }
                    ]
                },
            )
            apex_installer = _ApexAppInstaller()
            apex_registry = _ApexAppRegistry()

            result = PluginInstaller(
                project_root=root,
                managed_root=root / "var" / "plugins",
                config_root=root / "config",
                dependency_installer=_DependencyInstaller(),
                database_deployer=_DatabaseDeployer(),
                registry=_Registry(),
                apex_app_installer=apex_installer,
                apex_app_registry=apex_registry,
            ).install_source(source)

            self.assertTrue(result.enabled)
            self.assertEqual(apex_installer.calls, [])
            self.assertEqual(apex_registry.rows[0]["install_status"], "metadata_only")
            self.assertIsNone(apex_registry.rows[0]["installed_app_id"])

    def test_required_apex_app_requires_export_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = _write_source_plugin(
                root,
                "alpha",
                extra_manifest={
                    "apex_apps": [
                        {
                            "app_alias": "ALPHA_STATUS",
                            "label": "Alpha Status",
                            "app_export": "apex/missing.sql",
                            "install_required": True,
                        }
                    ]
                },
            )

            result = PluginInstaller(
                project_root=root,
                managed_root=root / "var" / "plugins",
                config_root=root / "config",
                dependency_installer=_DependencyInstaller(),
                database_deployer=_DatabaseDeployer(),
                registry=_Registry(),
                apex_app_installer=_ApexAppInstaller(),
                apex_app_registry=_ApexAppRegistry(),
            ).install_source(source)

            self.assertFalse(result.enabled)
            self.assertEqual(result.status, "readiness_failed")
            self.assertIn(
                "Plugin APEX app 'ALPHA_STATUS' declares missing export", result.message
            )


class ExistingPluginDependencyTests(unittest.TestCase):
    """Keep bundled plugin dependency declarations aligned with imports."""

    def test_existing_plugin_dependency_declarations(self) -> None:
        manifests, errors = PluginDiscovery(PROJECT_ROOT / "plugins").discover()
        self.assertEqual(errors, [])
        by_id = {manifest.plugin_id: manifest for manifest in manifests}
        self.assertEqual(
            by_id["home_assistant"].python_dependencies, ("requests<3,>=2.32",)
        )
        self.assertEqual(by_id["weather"].python_dependencies, ("requests<3,>=2.32",))
        self.assertEqual(by_id["media_control"].python_dependencies, ())

    def test_weather_source_passes_installed_package_import_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = PluginInstaller(
                project_root=PROJECT_ROOT,
                managed_root=root / "var" / "plugins",
                config_root=root / "config",
                dependency_installer=_DependencyInstaller(),
                database_deployer=_DatabaseDeployer(),
                registry=_Registry(),
            ).install_source(PROJECT_ROOT / "plugins" / "weather")

            self.assertTrue(result.enabled)
            self.assertTrue(
                (result.installed_path / "plugin" / "provider.py").is_file()
            )


def _write_source_plugin(
    root: Path,
    plugin_id: str,
    *,
    required_config: bool = False,
    extra_manifest: dict | None = None,
) -> Path:
    """Create a minimal source plugin fixture."""
    plugins = root / "plugins"
    plugin_dir = plugins / plugin_id
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.py").write_text(
        "class AlphaPlugin:\n    def execute(self):\n        return None\n",
        encoding="utf-8",
    )
    required = (
        [{"section": plugin_id, "key": "host", "type": "string", "description": "Host"}]
        if required_config
        else []
    )
    manifest = {
        "schema_version": 2,
        "plugin_id": plugin_id,
        "name": "Alpha",
        "description": "Test plugin",
        "version": "1.0.0",
        "enabled": True,
        "capabilities": ["alpha.read"],
        "entitlements": [],
        "entry_point": "plugin:AlphaPlugin",
        "runtime": {"mode": "on_demand"},
        "configuration": {"required": required, "optional": []},
        "database": {"required": False, "schemas": []},
        "python_dependencies": [],
    }
    if extra_manifest:
        manifest.update(extra_manifest)
    (plugins / f"{plugin_id}.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    return plugin_dir


if __name__ == "__main__":
    unittest.main()
