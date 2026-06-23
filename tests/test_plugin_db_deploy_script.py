"""Tests for the plugin database container deployment script."""
# Author: Clive Bostock
# Date: 2026-06-03
# Description: Verifies plugin database deployment shell validation paths.

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_ROOT / "resources" / "docker" / "oracle" / "bin" / "deploy-plugin-db.sh"
LIQUIBASE_SCRIPT_PATH = (
    PROJECT_ROOT
    / "resources"
    / "docker"
    / "oracle"
    / "bin"
    / "deploy-plugin-liquibase-db.sh"
)


def _script_env(staging_root: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["PLUGIN_STAGING_ROOT"] = str(staging_root)
    return env


def _write_archive(path: Path, *, include_manifest: bool = True, include_schema: bool = True) -> None:
    manifest = {
        "plugin_id": "alpha",
        "plugin_version": "1.0.0",
        "schema_version": 2,
        "database": {
            "schemas": [
                {
                    "schema_name": "orac_alpha",
                    "purpose": "Test schema.",
                    "managed_by": "orac",
                    "minimum_version": "1.0.0",
                }
            ]
        },
        "payload_checksum": "a" * 64,
    }
    with tarfile.open(path, "w:gz") as archive:
        if include_manifest:
            _add_bytes(archive, "manifest.json", json.dumps(manifest).encode("utf-8"))
        _add_bytes(archive, "plugin.json", b'{"plugin_id":"alpha"}\n')
        if include_schema:
            _add_bytes(archive, "db/schema/table/example.sql", b"create table orac_alpha.example_table (id number);\n")


def _write_successful_core_deploy_script(path: Path) -> None:
    path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)


def _write_fake_sqlplus(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env bash
input="$(cat)"
if grep -q "dba_objects" <<<"${input}"; then
  printf '%b' "${SQLPLUS_INVALID_OUTPUT:-}"
fi
exit 0
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _write_static_sqlplus(path: Path, output: str) -> None:
    path.write_text(
        f"""#!/usr/bin/env bash
cat >/dev/null
printf '%b' {output!r}
exit 0
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _write_liquibase_archive(path: Path) -> None:
    manifest = {
        "plugin_id": "alpha",
        "plugin_version": "1.0.0",
        "schema_version": 2,
        "database": {
            "schemas": [
                {
                    "schema_name": "orac_alpha",
                    "purpose": "Test schema.",
                    "managed_by": "orac",
                    "minimum_version": "1.0.0",
                }
            ]
        },
        "payload_checksum": "a" * 64,
    }
    controller = b"""<?xml version="1.0" encoding="UTF-8"?>
<databaseChangeLog
  xmlns="http://www.liquibase.org/xml/ns/dbchangelog"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  logicalFilePath="plugins/alpha/db/liquibase/pluginController.xml"
  xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog https://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-4.30.xsd">
  <include file="../schema/table/example.sql" relativeToChangelogFile="true"/>
</databaseChangeLog>
"""
    sql = b"""--liquibase formatted sql logicalFilePath:plugins/alpha/db/schema/table/example.sql

--changeset alpha:alpha_create_table_example context:plugin labels:plugin,alpha stripComments:false splitStatements:false endDelimiter:/
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'ORAC_ALPHA' and table_name = 'EXAMPLE_TABLE';
create table orac_alpha.example_table (id number);
--rollback drop table orac_alpha.example_table purge;
"""
    with tarfile.open(path, "w:gz") as archive:
        _add_bytes(archive, "manifest.json", json.dumps(manifest).encode("utf-8"))
        _add_bytes(archive, "plugin.json", b'{"plugin_id":"alpha"}\n')
        _add_bytes(
            archive,
            "db/schema/table/example.sql",
            sql,
        )
        _add_bytes(archive, "db/liquibase/pluginController.xml", controller)


def _add_bytes(archive: tarfile.TarFile, name: str, content: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(content)
    archive.addfile(info, fileobj=_BytesReader(content))


class _BytesReader:
    def __init__(self, content: bytes) -> None:
        self._content = content
        self._offset = 0

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._content) - self._offset
        chunk = self._content[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk


class PluginDbDeployScriptTests(unittest.TestCase):
    """Tests script validation without requiring an Oracle container."""

    def _run_deploy_with_invalid_object_output(
        self,
        temp_path: Path,
        invalid_object_output: str,
    ) -> subprocess.CompletedProcess[str]:
        archive_path = temp_path / "alpha-db.tar.gz"
        _write_archive(archive_path)
        core_deploy_script = temp_path / "035-orac-schema_and_apps.sh"
        _write_successful_core_deploy_script(core_deploy_script)
        bin_dir = temp_path / "bin"
        bin_dir.mkdir()
        _write_fake_sqlplus(bin_dir / "sqlplus")

        env = _script_env(temp_path / "staging")
        env["CORE_DEPLOY_SCRIPT"] = str(core_deploy_script)
        env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
        env["SQLPLUS_INVALID_OUTPUT"] = invalid_object_output

        return subprocess.run(
            [
                "bash",
                str(SCRIPT_PATH),
                "--plugin-id",
                "alpha",
                "--archive",
                str(archive_path),
            ],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_dry_run_validates_archive_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = temp_path / "alpha-db.tar.gz"
            _write_archive(archive_path)

            result = subprocess.run(
                [
                    "bash",
                    str(SCRIPT_PATH),
                    "--plugin-id",
                    "alpha",
                    "--archive",
                    str(archive_path),
                    "--dry-run",
                ],
                env=_script_env(temp_path / "staging"),
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("Dry run complete", result.stdout)

    def test_dry_run_unpacks_beside_archive_not_plugin_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            plugin_parent = temp_path / "staging" / "alpha"
            archive_dir = plugin_parent / "1.0.0"
            archive_dir.mkdir(parents=True)
            archive_path = archive_dir / "alpha-db.tar.gz"
            _write_archive(archive_path)
            plugin_parent.chmod(0o500)
            try:
                result = subprocess.run(
                    [
                        "bash",
                        str(SCRIPT_PATH),
                        "--plugin-id",
                        "alpha",
                        "--archive",
                        str(archive_path),
                        "--dry-run",
                    ],
                    env=_script_env(temp_path / "unused-staging-root"),
                    text=True,
                    capture_output=True,
                    check=False,
                )
            finally:
                plugin_parent.chmod(0o700)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue((archive_dir / "work" / "manifest.json").is_file())

    def test_missing_archive_returns_non_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run(
                [
                    "bash",
                    str(SCRIPT_PATH),
                    "--plugin-id",
                    "alpha",
                    "--archive",
                    str(Path(temp_dir) / "missing.tar.gz"),
                    "--dry-run",
                ],
                env=_script_env(Path(temp_dir) / "staging"),
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Archive does not exist", result.stdout)

    def test_missing_manifest_returns_non_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = temp_path / "alpha-db.tar.gz"
            _write_archive(archive_path, include_manifest=False)

            result = subprocess.run(
                [
                    "bash",
                    str(SCRIPT_PATH),
                    "--plugin-id",
                    "alpha",
                    "--archive",
                    str(archive_path),
                    "--dry-run",
                ],
                env=_script_env(temp_path / "staging"),
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("manifest.json is missing", result.stdout)

    def test_missing_schema_returns_non_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = temp_path / "alpha-db.tar.gz"
            _write_archive(archive_path, include_schema=False)

            result = subprocess.run(
                [
                    "bash",
                    str(SCRIPT_PATH),
                    "--plugin-id",
                    "alpha",
                    "--archive",
                    str(archive_path),
                    "--dry-run",
                ],
                env=_script_env(temp_path / "staging"),
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("db/schema is missing", result.stdout)

    def test_session_altered_output_does_not_fail_invalid_object_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self._run_deploy_with_invalid_object_output(
                Path(temp_dir),
                "\nSession altered.\n\n",
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("Plugin database deployment completed", result.stdout)

    def test_blank_invalid_object_output_is_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self._run_deploy_with_invalid_object_output(Path(temp_dir), "")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("Plugin database deployment completed", result.stdout)

    def test_marked_invalid_object_output_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self._run_deploy_with_invalid_object_output(
                Path(temp_dir),
                "\nSession altered.\nINVALID_OBJECT PACKAGE BODY ORAC_ALPHA.BAD_API\n",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("left invalid objects", result.stdout)
            self.assertIn("PACKAGE BODY ORAC_ALPHA.BAD_API", result.stdout)

    def test_liquibase_dry_run_validates_archive_shape_and_invokes_sqlcl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = temp_path / "alpha-db.tar.gz"
            _write_liquibase_archive(archive_path)
            sqlcl_home = temp_path / "sqlcl"
            sql_bin = sqlcl_home / "bin"
            sql_bin.mkdir(parents=True)
            sql_path = sql_bin / "sql"
            sql_path.write_text(
                "#!/usr/bin/env bash\ncat >\"${SQLCL_INPUT_CAPTURE}\"\nexit 0\n",
                encoding="utf-8",
            )
            sql_path.chmod(0o755)
            bin_dir = temp_path / "bin"
            bin_dir.mkdir()
            _write_fake_sqlplus(bin_dir / "sqlplus")
            sqlcl_input = temp_path / "sqlcl-input.sql"
            properties_path = temp_path / "liquibase-plugin.properties"
            properties_path.write_text(
                "changeLogFile=db/liquibase/pluginController.xml\n",
                encoding="utf-8",
            )
            env = _script_env(temp_path / "staging")
            env["SQLCL_HOME"] = str(sqlcl_home)
            env["LIQUIBASE_PROPERTIES_SOURCE"] = str(properties_path)
            env["LOG_ROOT"] = str(temp_path / "logs")
            env["ORACLE_PWD"] = "secret"
            env["SQLCL_INPUT_CAPTURE"] = str(sqlcl_input)
            env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"

            result = subprocess.run(
                [
                    "bash",
                    str(LIQUIBASE_SCRIPT_PATH),
                    "--plugin-id",
                    "alpha",
                    "--archive",
                    str(archive_path),
                    "--schema-name",
                    "orac_alpha",
                    "--default-schema-name",
                    "ORAC_ALPHA",
                    "--liquibase-schema-name",
                    "ORAC_ALPHA",
                    "--dry-run",
                ],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("Plugin Liquibase update-sql completed", result.stdout)
            input_text = sqlcl_input.read_text(encoding="utf-8")
            self.assertIn('connect ORAC_ALPHA/"secret"@//127.0.0.1:1521/FREEPDB1', input_text)
            self.assertNotIn("--default-schema-name", input_text)
            self.assertNotIn("--liquibase-schema-name", input_text)
            generated_properties = (
                temp_path / "work-liquibase-orac_alpha" / "liquibase-plugin.properties"
            ).read_text(encoding="utf-8")
            self.assertIn("defaultSchemaName=ORAC_ALPHA", generated_properties)
            self.assertIn("liquibaseSchemaName=ORAC_ALPHA", generated_properties)
            self.assertIn(
                "liquibase.command.defaultSchemaName=ORAC_ALPHA",
                generated_properties,
            )
            self.assertIn(
                "liquibase.command.liquibaseSchemaName=ORAC_ALPHA",
                generated_properties,
            )

    def test_liquibase_requires_default_schema_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = temp_path / "alpha-db.tar.gz"
            _write_liquibase_archive(archive_path)

            result = subprocess.run(
                [
                    "bash",
                    str(LIQUIBASE_SCRIPT_PATH),
                    "--plugin-id",
                    "alpha",
                    "--archive",
                    str(archive_path),
                    "--schema-name",
                    "orac_alpha",
                    "--liquibase-schema-name",
                    "ORAC_ALPHA",
                    "--dry-run",
                ],
                env=_script_env(temp_path / "staging"),
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--default-schema-name is required", result.stderr)

    def test_liquibase_requires_matching_tracking_schema_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = temp_path / "alpha-db.tar.gz"
            _write_liquibase_archive(archive_path)

            result = subprocess.run(
                [
                    "bash",
                    str(LIQUIBASE_SCRIPT_PATH),
                    "--plugin-id",
                    "alpha",
                    "--archive",
                    str(archive_path),
                    "--schema-name",
                    "orac_alpha",
                    "--default-schema-name",
                    "ORAC_BETA",
                    "--liquibase-schema-name",
                    "ORAC_ALPHA",
                    "--dry-run",
                ],
                env=_script_env(temp_path / "staging"),
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--default-schema-name must match --schema-name", result.stderr)

    def test_liquibase_dry_run_fails_when_sqlcl_logs_connection_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = temp_path / "alpha-db.tar.gz"
            _write_liquibase_archive(archive_path)
            sqlcl_home = temp_path / "sqlcl"
            sql_bin = sqlcl_home / "bin"
            sql_bin.mkdir(parents=True)
            sql_path = sql_bin / "sql"
            sql_path.write_text(
                "#!/usr/bin/env bash\ncat >/dev/null\nprintf 'Connection failed\\nORA-28000: account locked\\n'\nexit 0\n",
                encoding="utf-8",
            )
            sql_path.chmod(0o755)
            bin_dir = temp_path / "bin"
            bin_dir.mkdir()
            _write_fake_sqlplus(bin_dir / "sqlplus")
            properties_path = temp_path / "liquibase-plugin.properties"
            properties_path.write_text(
                "changeLogFile=db/liquibase/pluginController.xml\n",
                encoding="utf-8",
            )
            env = _script_env(temp_path / "staging")
            env["SQLCL_HOME"] = str(sqlcl_home)
            env["LIQUIBASE_PROPERTIES_SOURCE"] = str(properties_path)
            env["LOG_ROOT"] = str(temp_path / "logs")
            env["ORACLE_PWD"] = "secret"
            env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"

            result = subprocess.run(
                [
                    "bash",
                    str(LIQUIBASE_SCRIPT_PATH),
                    "--plugin-id",
                    "alpha",
                    "--archive",
                    str(archive_path),
                    "--schema-name",
                    "ORAC_ALPHA",
                    "--default-schema-name",
                    "ORAC_ALPHA",
                    "--liquibase-schema-name",
                    "ORAC_ALPHA",
                    "--dry-run",
                ],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("reported an error", result.stderr)

    def test_liquibase_update_fails_on_system_changelog_contamination(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = temp_path / "alpha-db.tar.gz"
            _write_liquibase_archive(archive_path)
            sqlcl_home = temp_path / "sqlcl"
            sql_bin = sqlcl_home / "bin"
            sql_bin.mkdir(parents=True)
            sql_path = sql_bin / "sql"
            sql_path.write_text(
                "#!/usr/bin/env bash\ncat >/dev/null\nexit 0\n",
                encoding="utf-8",
            )
            sql_path.chmod(0o755)
            bin_dir = temp_path / "bin"
            bin_dir.mkdir()
            _write_static_sqlplus(
                bin_dir / "sqlplus",
                "CONTAMINATED_CHANGELOG SYSTEM.DATABASECHANGELOG rows=1\n",
            )
            properties_path = temp_path / "liquibase-plugin.properties"
            properties_path.write_text(
                "changeLogFile=db/liquibase/pluginController.xml\n",
                encoding="utf-8",
            )
            env = _script_env(temp_path / "staging")
            env["SQLCL_HOME"] = str(sqlcl_home)
            env["LIQUIBASE_PROPERTIES_SOURCE"] = str(properties_path)
            env["LOG_ROOT"] = str(temp_path / "logs")
            env["ORACLE_PWD"] = "secret"
            env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"

            result = subprocess.run(
                [
                    "bash",
                    str(LIQUIBASE_SCRIPT_PATH),
                    "--plugin-id",
                    "alpha",
                    "--archive",
                    str(archive_path),
                    "--schema-name",
                    "ORAC_ALPHA",
                    "--default-schema-name",
                    "ORAC_ALPHA",
                    "--liquibase-schema-name",
                    "ORAC_ALPHA",
                ],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("guarded repair is required", result.stderr)


if __name__ == "__main__":
    unittest.main()
