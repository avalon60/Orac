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
<databaseChangeLog xmlns="http://www.liquibase.org/xml/ns/dbchangelog">
  <changeSet id="alpha-example" author="clive">
    <sqlFile path="../schema/table/example.sql" relativeToChangelogFile="true"/>
  </changeSet>
</databaseChangeLog>
"""
    with tarfile.open(path, "w:gz") as archive:
        _add_bytes(archive, "manifest.json", json.dumps(manifest).encode("utf-8"))
        _add_bytes(archive, "plugin.json", b'{"plugin_id":"alpha"}\n')
        _add_bytes(
            archive,
            "db/schema/table/example.sql",
            b"create table orac_alpha.example_table (id number);\n",
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
                "#!/usr/bin/env bash\ncat >/dev/null\nexit 0\n",
                encoding="utf-8",
            )
            sql_path.chmod(0o755)
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
                    "--dry-run",
                ],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("Plugin Liquibase update-sql completed", result.stdout)


if __name__ == "__main__":
    unittest.main()
