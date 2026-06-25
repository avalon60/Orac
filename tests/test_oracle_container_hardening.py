"""Tests for Oracle container hardening scripts."""
# Author: Clive Bostock
# Date: 20-Jun-2026
# Description: Verifies static and unit behaviour for ORDS/APEX container hardening.

from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess
import textwrap


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ORACLE_ROOT = PROJECT_ROOT / "resources" / "docker" / "oracle"
CHECK_WRAPPER = ORACLE_ROOT / "bin" / "checkDBStatus-orac.sh"
DOCKERFILE = ORACLE_ROOT / "Dockerfile"
FOUNDATION_SETUP = ORACLE_ROOT / "setup" / "005-orac-db-foundation.sh"
OLD_EXTENDED_STRINGS_SETUP = ORACLE_ROOT / "setup" / "999-extended-strings.sh"
ORDS_SETUP = ORACLE_ROOT / "setup" / "020-setup-ords.sh"
APEX_ROLE_SETUP = ORACLE_ROOT / "setup" / "050-init-app-role.sh"
ORDS_STARTUP = ORACLE_ROOT / "startup" / "010-start-ords.sh"
LISTENER_REPAIR = ORACLE_ROOT / "startup" / "005-repair-listener.sh"
ORDS_POST_INSTALL = ORACLE_ROOT / "setup" / "024-ords-post-install.sql"
DEPLOY_SCRIPT = PROJECT_ROOT / "bin" / "orac-db-deploy.sh"
APEX_DOC = PROJECT_ROOT / "docs" / "apex-administration.md"
INSTALL_DOC = PROJECT_ROOT / "docs" / "installation.md"


def test_check_wrapper_preserves_original_success(tmp_path: Path) -> None:
    result = _run_wrapper(tmp_path, original_status=0, sql_output="")

    assert result.returncode == 0


def test_check_wrapper_preserves_original_non_pdb_seed_failure(tmp_path: Path) -> None:
    result = _run_wrapper(
        tmp_path,
        original_status=3,
        sql_output="OPEN|PRIMARY|READ WRITE",
    )

    assert result.returncode == 3


def test_check_wrapper_allows_freepdb1_read_write_when_original_status_is_5(
    tmp_path: Path,
) -> None:
    result = _run_wrapper(
        tmp_path,
        original_status=5,
        sql_output="OPEN|PRIMARY|READ WRITE",
    )

    assert result.returncode == 0
    assert "ORAC_DB_HEALTH_OK" in result.stdout


def test_check_wrapper_rejects_freepdb1_mounted_when_original_status_is_5(
    tmp_path: Path,
) -> None:
    result = _run_wrapper(tmp_path, original_status=5, sql_output="OPEN|PRIMARY|MOUNTED")

    assert result.returncode == 5
    assert "ORAC_DB_HEALTH_FAILED" in result.stdout


def test_check_wrapper_rejects_missing_freepdb1_when_original_status_is_5(
    tmp_path: Path,
) -> None:
    result = _run_wrapper(tmp_path, original_status=5, sql_output="OPEN|PRIMARY|MISSING")

    assert result.returncode == 5


def test_dockerfile_healthcheck_resolves_through_orac_wrapper() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert "CHECK_DB_FILE=checkDBStatus-orac.sh" in dockerfile
    assert "checkDBStatus-orac.sh ${ORACLE_BASE}/checkDBStatus-orac.sh" in dockerfile
    assert "/opt/oracle/checkDBStatus.sh" not in dockerfile


def test_ords_config_uses_persistent_config_and_runtime_symlink() -> None:
    setup = ORDS_SETUP.read_text(encoding="utf-8")
    startup = ORDS_STARTUP.read_text(encoding="utf-8")
    deploy = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    for script in [deploy]:
        assert "/opt/oracle/oradata/orac/ords/conf" in script
        assert "/home/oracle/orac/ords/conf" in script

    for script in [setup, startup]:
        assert "/opt/oracle/oradata/orac/ords/conf" in script
        assert 'ORDS_CONF=${ORDS_HOME}/conf' in script

    assert 'ln -s "${ORDS_CONF_PERSISTENT}" "${ORDS_CONF}"' in setup
    assert 'ln -s "${ORDS_CONF_PERSISTENT}" "${ORDS_CONF}"' in startup
    assert 'find -L "${ORDS_CONF}"' in setup


def test_startup_does_not_run_ords_install() -> None:
    startup = ORDS_STARTUP.read_text(encoding="utf-8")

    assert "ords install" not in startup
    assert " install" not in "\n".join(
        line for line in startup.splitlines() if "bin/ords" in line
    )


def test_listener_repair_normalises_tcp_host_and_preserves_extproc() -> None:
    script = LISTENER_REPAIR.read_text(encoding="utf-8")

    assert "HOST = 0.0.0.0" in script
    assert "EXTPROC1521" in script
    assert "lsnrctl start LISTENER" in script
    assert "alter system register" not in script
    assert "PROTOCOL[[:space:]]*=[[:space:]]*TCP" in script


def test_proxy_grant_is_minimal() -> None:
    sql = ORDS_POST_INSTALL.read_text(encoding="utf-8").lower()

    assert "alter user orac_apx_pub grant connect through ords_public_user;" in sql
    assert sql.count("grant connect through ords_public_user") == 4
    assert "grant dba" not in sql
    assert "grant all" not in sql


def test_apex_admin_account_is_reset_and_unexpired_during_setup() -> None:
    script = APEX_ROLE_SETUP.read_text(encoding="utf-8")

    assert '[[ -z "${ORACLE_PWD:-}" ]]' in script
    assert "whenever sqlerror exit failure rollback" in script
    assert "create or replace procedure orac_apx_pub.orac_admin_setup_tmp" in script
    assert "authid definer" in script
    assert "drop procedure orac_apx_pub.orac_admin_setup_tmp" in script
    assert "alter session set current_schema = &&apex_owner" not in script
    assert "ORAC_APEX_ADMIN_SETUP_FAILED" in script
    assert "apex_application_install.set_workspace_id" in script
    assert "apex_util.set_security_group_id" in script
    assert "apex_util.reset_password" in script
    assert "p_user_name                    => 'ORAC_ADMIN'" in script
    assert "p_new_password                 => '${ORACLE_PWD}'" in script
    assert "p_change_password_on_first_use => false" in script
    assert "apex_util.unlock_account" in script
    assert "apex_util.unexpire_workspace_account" in script
    assert "apex_util.expire_workspace_account" not in script


def test_database_foundation_runs_early_and_does_not_complete_deployment() -> None:
    script = FOUNDATION_SETUP.read_text(encoding="utf-8")
    completion_script = (ORACLE_ROOT / "setup" / "998-complete-orac.sh").read_text(
        encoding="utf-8"
    )
    setup_scripts = sorted(path.name for path in (ORACLE_ROOT / "setup").glob("*.sh"))

    assert FOUNDATION_SETUP.is_file()
    assert not OLD_EXTENDED_STRINGS_SETUP.exists()
    assert (ORACLE_ROOT / "setup" / "998-complete-orac.sh").is_file()
    assert setup_scripts.index("005-orac-db-foundation.sh") < setup_scripts.index(
        "010-apex-install.sh"
    )

    assert "from v\\$database" in script
    assert "log_mode" in script
    assert "from v\\$parameter" in script
    assert "max_string_size" in script
    assert (
        "shutdown immediate;\n"
        "startup mount;\n"
        "alter database noarchivelog;\n"
        "alter database open;\n"
        "alter pluggable database all open;\n"
        "alter pluggable database all save state;"
    ) in script
    assert "startup mount;\n${noarchivelog_sql}\nalter database open upgrade;" in script
    assert "emit_deployment_complete_marker" not in script
    assert "ORAC_DEPLOYMENT_COMPLETE_LIB_ONLY" not in script
    assert "ORAC deployment complete" not in script
    assert "ORAC deployment complete" in completion_script


def test_canonical_apex_url_is_documented_and_used_by_deploy() -> None:
    canonical_url = "http://localhost:8042/ords/r/orac/orac-administration1042/login"
    canonical_path = "/ords/r/orac/orac-administration1042/login"

    assert canonical_url in APEX_DOC.read_text(encoding="utf-8")
    assert canonical_url in INSTALL_DOC.read_text(encoding="utf-8")
    assert canonical_path in DEPLOY_SCRIPT.read_text(encoding="utf-8")


def _run_wrapper(
    tmp_path: Path,
    *,
    original_status: int,
    sql_output: str,
) -> subprocess.CompletedProcess[str]:
    original_check = tmp_path / "original-check.sh"
    original_check.write_text(
        f"#!/usr/bin/env bash\nexit {original_status}\n",
        encoding="utf-8",
    )
    original_check.chmod(original_check.stat().st_mode | stat.S_IXUSR)

    sqlplus = tmp_path / "sqlplus"
    sqlplus.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            cat >/dev/null
            printf '%s\\n' '{sql_output}'
            """
        ),
        encoding="utf-8",
    )
    sqlplus.chmod(sqlplus.stat().st_mode | stat.S_IXUSR)

    env = {
        **os.environ,
        "ORAC_ORIGINAL_CHECK_DB_FILE": str(original_check),
        "SQLPLUS_BIN": str(sqlplus),
        "ORACLE_PDB": "FREEPDB1",
    }

    return subprocess.run(
        ["bash", str(CHECK_WRAPPER)],
        cwd=PROJECT_ROOT,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )
