"""Tests for the core Liquibase deployment checker."""
# Author: Clive Bostock
# Date: 22-Jun-2026
# Description: Verifies core Liquibase formatted SQL coverage checks.

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import textwrap


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHECKER_PATH = PROJECT_ROOT / "scripts/check_core_liquibase.py"
SPEC = importlib.util.spec_from_file_location("check_core_liquibase", CHECKER_PATH)
assert SPEC is not None
check_core_liquibase = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = check_core_liquibase
SPEC.loader.exec_module(check_core_liquibase)


def _write_schema_controller(root: Path, body: str) -> None:
    controller = root / "resources/db/schema/orac_core/schemaController.xml"
    controller.parent.mkdir(parents=True, exist_ok=True)
    controller.write_text(
        textwrap.dedent(
            f"""\
            <?xml version="1.0" encoding="UTF-8"?>
            <databaseChangeLog
              xmlns="http://www.liquibase.org/xml/ns/dbchangelog">
            {body}
            </databaseChangeLog>
            """
        ).lstrip(),
        encoding="utf-8",
    )


def _write_product_controller(root: Path) -> None:
    controller = root / "resources/db/schema/productController.xml"
    controller.parent.mkdir(parents=True, exist_ok=True)
    controller.write_text(
        textwrap.dedent(
            """\
            <?xml version="1.0" encoding="UTF-8"?>
            <databaseChangeLog
              xmlns="http://www.liquibase.org/xml/ns/dbchangelog">
              <include file="orac_core/schemaController.xml"
                       relativeToChangelogFile="true"/>
            </databaseChangeLog>
            """
        ),
        encoding="utf-8",
    )


def _write_properties(root: Path, text: str = "changeLogFile=productController.xml\n") -> None:
    path = root / "resources/db/liquibase/liquibase-core.properties"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_formatted_table(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            """\
            --liquibase formatted sql

            --changeset clive:create_table_orac_core_users context:core labels:core stripComments:false
            --preconditions onFail:HALT onError:HALT
            --precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'ORAC_CORE' and table_name = 'USERS';
            create table orac_core.users (id number);
            --rollback drop table orac_core.users purge;
            """
        ),
        encoding="utf-8",
    )


def test_reports_unformatted_core_schema_sql(tmp_path: Path) -> None:
    schema_file = tmp_path / "resources/db/schema/orac_core/table/users.sql"
    schema_file.parent.mkdir(parents=True, exist_ok=True)
    schema_file.write_text("create table orac_core.users (id number);\n", encoding="utf-8")
    _write_product_controller(tmp_path)
    _write_schema_controller(
        tmp_path,
        '<includeAll path="table" relativeToChangelogFile="true" errorIfMissingOrEmpty="false"/>',
    )
    _write_properties(tmp_path)

    issues = check_core_liquibase.run_checks(tmp_path)

    assert any("lacks --liquibase formatted sql" in issue for issue in issues)


def test_accepts_reachable_formatted_core_schema_sql(tmp_path: Path) -> None:
    _write_formatted_table(tmp_path / "resources/db/schema/orac_core/table/users.sql")
    _write_product_controller(tmp_path)
    _write_schema_controller(
        tmp_path,
        '<includeAll path="table" relativeToChangelogFile="true" errorIfMissingOrEmpty="false"/>',
    )
    _write_properties(tmp_path)

    assert check_core_liquibase.run_checks(tmp_path) == []


def test_rejects_sqlfile_wrapper_in_active_controller(tmp_path: Path) -> None:
    _write_formatted_table(tmp_path / "resources/db/schema/orac_core/table/users.sql")
    _write_product_controller(tmp_path)
    _write_schema_controller(
        tmp_path,
        """
          <changeSet id="baseline_orac_core_table_users" author="clive">
            <sqlFile path="table/users.sql" relativeToChangelogFile="true"/>
          </changeSet>
        """,
    )
    _write_properties(tmp_path)

    issues = check_core_liquibase.run_checks(tmp_path)

    assert any("uses sqlFile wrappers" in issue for issue in issues)


def test_reports_custom_core_tracking_table_configuration(tmp_path: Path) -> None:
    _write_product_controller(tmp_path)
    _write_schema_controller(tmp_path, "")
    _write_properties(
        tmp_path,
        "\n".join(
            [
                "changeLogFile=productController.xml",
                "databaseChangeLogTableName=orac_databasechangelog",
                "",
            ]
        ),
    )

    issues = check_core_liquibase.run_checks(tmp_path)

    assert any("custom databaseChangeLogTableName" in issue for issue in issues)


def test_reports_stale_apex_exports_under_schema_root(tmp_path: Path) -> None:
    stale_export = (
        tmp_path
        / "resources"
        / "db"
        / "schema"
        / "orac_core"
        / "orac_apps"
        / "f1042.sql"
    )
    stale_export.parent.mkdir(parents=True, exist_ok=True)
    stale_export.write_text("-- APEX export\n", encoding="utf-8")
    _write_product_controller(tmp_path)
    _write_schema_controller(tmp_path, "")
    _write_properties(tmp_path)

    issues = check_core_liquibase.run_checks(tmp_path)

    assert any("APEX exports must live under resources/db/apex" in issue for issue in issues)


def test_current_repository_core_liquibase_check_passes() -> None:
    assert check_core_liquibase.main(["--root", str(PROJECT_ROOT)]) == 0
