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


def _write_schema_controller(root: Path, body: str, schema: str = "orac_core") -> None:
    controller = root / f"resources/db/schema/{schema}/schemaController.xml"
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


def _write_product_controller(root: Path, include_api: bool = False) -> None:
    controller = root / "resources/db/schema/productController.xml"
    controller.parent.mkdir(parents=True, exist_ok=True)
    api_include = (
        '  <include file="orac_api/schemaController.xml"\n'
        '           relativeToChangelogFile="true"/>\n'
        if include_api
        else ""
    )
    controller.write_text(
        textwrap.dedent(
            f"""\
            <?xml version="1.0" encoding="UTF-8"?>
            <databaseChangeLog
              xmlns="http://www.liquibase.org/xml/ns/dbchangelog">
              <include file="orac_core/schemaController.xml"
                       relativeToChangelogFile="true"/>
            {api_include.rstrip()}
            </databaseChangeLog>
            """
        ).lstrip(),
        encoding="utf-8",
    )


def _write_api_schema_controller(root: Path) -> None:
    _write_schema_controller(
        root,
        """
          <includeAll path="privilege" relativeToChangelogFile="true" errorIfMissingOrEmpty="false"/>
          <includeAll path="view" relativeToChangelogFile="true" errorIfMissingOrEmpty="false"/>
        """,
        schema="orac_api",
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


def _write_formatted_api_view(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            """\
            --liquibase formatted sql

            --changeset clive:create_view_orac_api_users_v context:core labels:core stripComments:false runOnChange:true
            create or replace force view orac_api.users_v as
            select id
              from orac_core.users;
            --rollback drop view orac_api.users_v;
            """
        ),
        encoding="utf-8",
    )


def _write_core_to_api_privilege(path: Path, extra_sql: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            f"""\
            --liquibase formatted sql

            --changeset clive:grant_orac_core_users_to_orac_api context:core labels:core stripComments:false runOnChange:true
            grant select, insert, update, delete on orac_core.users to orac_api with grant option;
            --rollback revoke select, insert, update, delete on orac_core.users from orac_api;
            {extra_sql}
            """
        ),
        encoding="utf-8",
    )


def _write_formatted_view(path: Path, ddl: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            """\
            --liquibase formatted sql

            --changeset clive:create_view_orac_code_example_v context:core labels:core stripComments:false runOnChange:true
            """
        ),
        encoding="utf-8",
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(ddl)
        handle.write("--rollback drop view orac_code.example_v;\n")


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
    _write_formatted_api_view(tmp_path / "resources/db/schema/orac_api/view/users_v.sql")
    _write_core_to_api_privilege(
        tmp_path / "resources/db/schema/orac_api/privilege/orac_api_core_table_access.sql"
    )
    _write_product_controller(tmp_path, include_api=True)
    _write_schema_controller(
        tmp_path,
        '<includeAll path="table" relativeToChangelogFile="true" errorIfMissingOrEmpty="false"/>',
    )
    _write_api_schema_controller(tmp_path)
    _write_properties(tmp_path)

    assert check_core_liquibase.run_checks(tmp_path) == []


def test_reports_core_table_missing_api_pass_through_view(tmp_path: Path) -> None:
    _write_formatted_table(tmp_path / "resources/db/schema/orac_core/table/users.sql")
    _write_core_to_api_privilege(
        tmp_path / "resources/db/schema/orac_api/privilege/orac_api_core_table_access.sql"
    )
    _write_product_controller(tmp_path, include_api=True)
    _write_schema_controller(
        tmp_path,
        '<includeAll path="table" relativeToChangelogFile="true" errorIfMissingOrEmpty="false"/>',
    )
    _write_api_schema_controller(tmp_path)
    _write_properties(tmp_path)

    issues = check_core_liquibase.run_checks(tmp_path)

    assert any("lacks a reachable API pass-through view" in issue for issue in issues)


def test_reports_core_table_missing_core_to_api_privilege(tmp_path: Path) -> None:
    _write_formatted_table(tmp_path / "resources/db/schema/orac_core/table/users.sql")
    _write_formatted_api_view(tmp_path / "resources/db/schema/orac_api/view/users_v.sql")
    _write_product_controller(tmp_path, include_api=True)
    _write_schema_controller(
        tmp_path,
        '<includeAll path="table" relativeToChangelogFile="true" errorIfMissingOrEmpty="false"/>',
    )
    _write_api_schema_controller(tmp_path)
    _write_properties(tmp_path)

    issues = check_core_liquibase.run_checks(tmp_path)

    assert any("lacks a reachable grant to orac_api" in issue for issue in issues)


def test_reports_prohibited_direct_core_grant(tmp_path: Path) -> None:
    _write_formatted_table(tmp_path / "resources/db/schema/orac_core/table/users.sql")
    _write_formatted_api_view(tmp_path / "resources/db/schema/orac_api/view/users_v.sql")
    _write_core_to_api_privilege(
        tmp_path / "resources/db/schema/orac_api/privilege/orac_api_core_table_access.sql",
        extra_sql=textwrap.dedent(
            """\
            --changeset clive:grant_orac_core_users_to_orac_code context:core labels:core stripComments:false runOnChange:true
            grant select on orac_core.users to orac_code;
            --rollback revoke select on orac_core.users from orac_code;
            """
        ),
    )
    _write_product_controller(tmp_path, include_api=True)
    _write_schema_controller(
        tmp_path,
        '<includeAll path="table" relativeToChangelogFile="true" errorIfMissingOrEmpty="false"/>',
    )
    _write_api_schema_controller(tmp_path)
    _write_properties(tmp_path)

    issues = check_core_liquibase.run_checks(tmp_path)

    assert any("prohibited direct grant on orac_core.users to orac_code" in issue for issue in issues)


def test_rejects_same_schema_view_dependency_without_force_view(tmp_path: Path) -> None:
    _write_formatted_view(
        tmp_path / "resources/db/schema/orac_code/view/example_v.sql",
        "create or replace view orac_code.example_v as\n"
        "select * from orac_code.base_v;\n",
    )
    _write_product_controller(tmp_path)
    _write_schema_controller(
        tmp_path,
        '<includeAll path="../orac_code/view" relativeToChangelogFile="true" errorIfMissingOrEmpty="false"/>',
    )
    _write_properties(tmp_path)

    issues = check_core_liquibase.run_checks(tmp_path)

    assert any("same-schema view dependency must use" in issue for issue in issues)


def test_accepts_same_schema_view_dependency_with_force_view(tmp_path: Path) -> None:
    _write_formatted_view(
        tmp_path / "resources/db/schema/orac_code/view/example_v.sql",
        "create or replace force view orac_code.example_v as\n"
        "select * from orac_code.base_v;\n",
    )
    _write_product_controller(tmp_path)
    _write_schema_controller(
        tmp_path,
        '<includeAll path="../orac_code/view" relativeToChangelogFile="true" errorIfMissingOrEmpty="false"/>',
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
