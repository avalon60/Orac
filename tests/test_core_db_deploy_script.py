"""Tests for the core SQLcl Liquibase deployment wrapper."""
# Author: Clive Bostock
# Date: 21-Jun-2026
# Description: Verifies core Liquibase command construction and error handling.

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = (
    PROJECT_ROOT
    / "resources"
    / "docker"
    / "oracle"
    / "bin"
    / "deploy-orac-db.sh"
)


def _write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _write_mock_environment(root: Path) -> dict[str, str]:
    orac_home = root / "orac"
    sqlcl_home = root / "sqlcl"
    liquibase_home = root / "liquibase"
    log_root = root / "logs"

    _write_executable(
        sqlcl_home / "bin" / "sql",
        """#!/usr/bin/env bash
cat > "${CAPTURE_SQL}"
printf '%s\n' "${SQLCL_OUTPUT:-Operation completed successfully.}"
exit "${SQLCL_EXIT:-0}"
""",
    )
    (liquibase_home / "changelogs" / "core").mkdir(parents=True)
    (liquibase_home / "liquibase-core.properties").write_text(
        "\n".join(
            [
                "changeLogFile=changelogs/core/oracController.xml",
                "liquibase.command.contextFilter=core,prod",
                "liquibase.command.labelFilter=core",
                "searchPath=/old/path",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (liquibase_home / "changelogs" / "core" / "oracController.xml").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?><databaseChangeLog/>\n",
        encoding="utf-8",
    )

    env = dict(os.environ)
    env.update(
        {
            "ORAC_HOME": str(orac_home),
            "ORACLE_PDB": "FREEPDB1",
            "ORACLE_PWD": "secret",
            "SQLCL_HOME": str(sqlcl_home),
            "LIQUIBASE_HOME": str(liquibase_home),
            "LOG_ROOT": str(log_root),
            "CAPTURE_SQL": str(root / "sqlcl-input.sql"),
        }
    )
    return env


def _run_script(
    env: dict[str, str],
    *args: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT_PATH), *args],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


class CoreDbDeployScriptTests(unittest.TestCase):
    """Tests core Liquibase deployment wrapper behaviour."""

    def test_uses_non_sys_connection_and_runtime_properties(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            env = _write_mock_environment(root)

            result = _run_script(
                env,
                "--validate",
                "--contexts",
                "core,test",
                "--labels",
                "core",
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            sql_input = (root / "sqlcl-input.sql").read_text(encoding="utf-8")
            self.assertIn('connect SYSTEM/"secret"@//127.0.0.1:1521/FREEPDB1', sql_input)
            self.assertNotIn(" as sysdba", sql_input.lower())
            self.assertNotIn("-contexts", sql_input)
            self.assertNotIn("-labels", sql_input)
            self.assertIn("-search-path", sql_input)

            runtime_properties = next((root / "logs").glob("*/liquibase-core-runtime.properties"))
            runtime_text = runtime_properties.read_text(encoding="utf-8")
            self.assertIn("liquibase.command.contextFilter=core,test", runtime_text)
            self.assertIn("liquibase.command.labelFilter=core", runtime_text)
            self.assertIn(f"searchPath={root / 'liquibase'}", runtime_text)
            self.assertNotIn("searchPath=/old/path", runtime_text)

    def test_sqlcl_liquibase_error_text_fails_even_with_zero_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            env = _write_mock_environment(root)
            env["SQLCL_OUTPUT"] = "ERROR: Exception Details\nProcessing has failed"

            result = _run_script(env, "--update")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("reported an error", result.stderr + result.stdout)

    def test_rejects_sys_liquibase_user(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            env = _write_mock_environment(root)
            env["LIQUIBASE_DB_USER"] = "SYS"

            result = _run_script(env, "--validate")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("cannot run as SYS", result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
