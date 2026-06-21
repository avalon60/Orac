"""Tests for the first-setup core Liquibase delta stage."""
# Author: Clive Bostock
# Date: 21-Jun-2026
# Description: Verifies the 040 setup script orchestration and failure paths.

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
    / "setup"
    / "040-orac-liquibase-deltas.sh"
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
        "#!/usr/bin/env bash\nprintf 'SQLcl mock 25.2\\n'\n",
    )
    (liquibase_home / "changelogs" / "core").mkdir(parents=True)
    (liquibase_home / "liquibase-core.properties").write_text(
        "changeLogFile=changelogs/core/oracController.xml\n",
        encoding="utf-8",
    )
    (liquibase_home / "changelogs" / "core" / "oracController.xml").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?><databaseChangeLog/>\n",
        encoding="utf-8",
    )
    _write_executable(
        orac_home / "bin" / "deploy-orac-db.sh",
        """#!/usr/bin/env bash
printf '%s|LOG_ROOT=%s\\n' "$*" "${LOG_ROOT:-}" >> "${ORAC_HOME}/deploy-calls.txt"
if [[ "$1" == "--validate" && "${FAIL_VALIDATE:-0}" == "1" ]]; then
  exit 42
fi
if [[ "$1" == "--update" && "${FAIL_UPDATE:-0}" == "1" ]]; then
  exit 43
fi
exit 0
""",
    )

    env = dict(os.environ)
    env.update(
        {
            "ORAC_HOME": str(orac_home),
            "ORACLE_PDB": "FREEPDB1",
            "ORACLE_PWD": "secret",
            "SQLCL_HOME": str(sqlcl_home),
            "LIQUIBASE_HOME": str(liquibase_home),
            "LIQUIBASE_SETUP_LOG_ROOT": str(log_root),
        }
    )
    return env


def _run_script(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT_PATH)],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


class OracLiquibaseSetupScriptTests(unittest.TestCase):
    """Tests first-setup Liquibase delta orchestration."""

    def test_success_calls_validate_before_update_and_logs_under_setup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            env = _write_mock_environment(root)

            result = _run_script(env)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            calls = (root / "orac" / "deploy-calls.txt").read_text(
                encoding="utf-8"
            ).splitlines()
            self.assertEqual(len(calls), 2)
            self.assertIn("--validate --contexts core,prod --labels core", calls[0])
            self.assertIn("--update --contexts core,prod --labels core", calls[1])
            self.assertIn(str(root / "logs"), calls[0])
            self.assertTrue(list((root / "logs").glob("*/040-orac-liquibase-deltas.log")))

    def test_ignores_generic_log_root_from_sourced_setup_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            env = _write_mock_environment(root)
            inherited_log_root = root / "schema" / "_logs"
            env["LOG_ROOT"] = str(inherited_log_root)
            env.pop("LIQUIBASE_SETUP_LOG_ROOT")

            result = _run_script(env)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            calls = (root / "orac" / "deploy-calls.txt").read_text(
                encoding="utf-8"
            ).splitlines()
            expected_root = root / "orac" / "logs" / "liquibase" / "setup"
            self.assertIn(str(expected_root), calls[0])
            self.assertFalse(inherited_log_root.exists())

    def test_validation_failure_prevents_update(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            env = _write_mock_environment(root)
            env["FAIL_VALIDATE"] = "1"

            result = _run_script(env)

            self.assertNotEqual(result.returncode, 0)
            calls = (root / "orac" / "deploy-calls.txt").read_text(
                encoding="utf-8"
            ).splitlines()
            self.assertEqual(len(calls), 1)
            self.assertIn("--validate", calls[0])
            self.assertNotIn("--update", "\n".join(calls))

    def test_missing_sqlcl_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            env = _write_mock_environment(root)
            (root / "sqlcl" / "bin" / "sql").unlink()

            result = _run_script(env)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SQLcl executable is missing", result.stdout)

    def test_missing_controller_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            env = _write_mock_environment(root)
            (root / "liquibase" / "changelogs" / "core" / "oracController.xml").unlink()

            result = _run_script(env)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Liquibase controller is missing", result.stdout)

    def test_missing_deploy_wrapper_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            env = _write_mock_environment(root)
            (root / "orac" / "bin" / "deploy-orac-db.sh").unlink()

            result = _run_script(env)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Core Liquibase deploy wrapper is missing", result.stdout)


if __name__ == "__main__":
    unittest.main()
