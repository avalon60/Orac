"""Tests for plugin-owned database deployment support."""
# Author: Clive Bostock
# Date: 2026-06-03
# Description: Verifies plugin database validation, packaging, and deployment gating.

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sys
import subprocess
import tarfile
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from model.plugin_database_deployment import PluginDatabaseDeployer
from model.plugin_database_deployment import DockerPluginDatabaseRunner
from model.plugin_database_deployment import DockerPluginLiquibaseDatabaseRunner
from model.plugin_database_deployment import PluginDatabaseDeploymentError
from model.plugin_database_deployment import PluginDatabaseDeploymentResult
from model.plugin_database_deployment import PluginDatabaseArchive
from model.plugin_database_deployment import PluginDatabaseSchemaProvisioner
from model.plugin_database_deployment import PROTECTED_ORAC_SCHEMAS
from model.plugin_database_deployment import _already_deployed_sql
from model.plugin_database_deployment import _payload_objects_deployed_sql
from model.plugin_database_deployment import expected_deployment_objects
from model.plugin_database_deployment import scan_protected_schema_references
from model.plugin_database_deployment import validate_declared_database_schemas
from model.plugin_database_deployment import validate_plugin_liquibase_changelog
from model.plugin_database_deployment import validate_schema_payload
from model.plugin_routing.discovery import PluginDiscovery
from model.plugin_routing.embeddings import HashEmbeddingProvider
from model.plugin_routing.manager import PluginManager


class _FakeRunner:
    def __init__(
        self,
        *,
        fail: bool = False,
        already_deployed: bool = False,
        payload_objects_deployed: bool | None = None,
    ) -> None:
        self.fail = fail
        self.already_deployed_result = already_deployed
        self.payload_objects_deployed_result = (
            already_deployed
            if payload_objects_deployed is None
            else payload_objects_deployed
        )
        self.calls: list[dict] = []
        self.already_deployed_calls: list[dict] = []
        self.payload_objects_deployed_calls: list[dict] = []
        self.mark_payload_deployed_calls: list[dict] = []

    def already_deployed(self, *, manifest, payload_checksum: str) -> bool:
        self.already_deployed_calls.append(
            {"manifest": manifest, "payload_checksum": payload_checksum}
        )
        return self.already_deployed_result

    def payload_objects_deployed(self, *, manifest, schema_payload_path: Path) -> bool:
        self.payload_objects_deployed_calls.append(
            {"manifest": manifest, "schema_payload_path": schema_payload_path}
        )
        return self.payload_objects_deployed_result

    def mark_payload_deployed(self, *, manifest, payload_checksum: str) -> None:
        self.mark_payload_deployed_calls.append(
            {"manifest": manifest, "payload_checksum": payload_checksum}
        )

    def deploy(self, *, manifest, archive) -> None:
        self.calls.append({"manifest": manifest, "archive": archive})
        if self.fail:
            raise PluginDatabaseDeploymentError("mock deployment failed")


class _FakeProvisioner:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict] = []

    def ensure_schemas(self, manifest) -> None:
        self.calls.append({"manifest": manifest})
        if self.fail:
            raise PluginDatabaseDeploymentError("mock provisioning failed")


class _FakeLogger:
    def __init__(self) -> None:
        self.info: list[str] = []
        self.warning: list[str] = []
        self.debug: list[str] = []

    def log_info(self, message: str) -> None:
        self.info.append(message)

    def log_warning(self, message: str) -> None:
        self.warning.append(message)

    def log_debug(self, message: str) -> None:
        self.debug.append(message)


class _FakeCursor:
    def __init__(self, *, user_exists: bool = False) -> None:
        self.user_exists = user_exists
        self.statements: list[tuple[str, dict | None]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def execute(self, sql: str, binds: dict | None = None) -> None:
        self.statements.append((sql, binds))

    def fetchone(self) -> tuple[int]:
        return (1 if self.user_exists else 0,)


class _FakeSession:
    def __init__(self, cursor: _FakeCursor) -> None:
        self.cursor_obj = cursor
        self.committed = False
        self.closed = False

    def cursor(self) -> _FakeCursor:
        return self.cursor_obj

    def commit(self) -> None:
        self.committed = True

    def close(self) -> None:
        self.closed = True


def _runtime(mode: str = "on_demand") -> dict:
    return {"mode": mode}


def _database(
    schema_name: str = "orac_ha",
    *,
    required: bool = True,
    deployment: dict | None = None,
) -> dict:
    result = {
        "required": required,
        "on_missing": "warn_disable",
        "schemas": [
            {
                "schema_name": schema_name,
                "purpose": "Test plugin storage.",
                "managed_by": "orac",
                "minimum_version": "1.0.0",
                "version_check": {"enabled": False},
                "backup": {"include": True, "export_mode": "schema"},
            }
        ],
    }
    if deployment is not None:
        result["deployment"] = deployment
    return result


def _manifest(plugin_id: str, *, database: dict | None = None) -> dict:
    payload = {
        "schema_version": 2,
        "plugin_id": plugin_id,
        "name": plugin_id.replace("_", " ").title(),
        "description": "Test plugin.",
        "version": "1.0.0",
        "enabled": True,
        "capabilities": [f"{plugin_id}.query"],
        "entitlements": [],
        "entry_point": "plugin:TestPlugin",
        "runtime": _runtime(),
    }
    if database is not None:
        payload["database"] = database
    return payload


def _write_plugin(
    plugins_dir: Path,
    plugin_id: str,
    manifest: dict,
    *,
    with_schema: bool = False,
    with_liquibase: bool = False,
    ddl: str = "create table orac_ha.example_table (id number);\n",
) -> None:
    plugin_dir = plugins_dir / plugin_id
    plugin_dir.mkdir()
    (plugin_dir / "plugin.py").write_text("class TestPlugin:\n    pass\n", encoding="utf-8")
    if with_schema:
        schema_dir = plugin_dir / "db" / "schema" / "table"
        schema_dir.mkdir(parents=True)
        (schema_dir / "example.sql").write_text(ddl, encoding="utf-8")
    if with_liquibase:
        liquibase_dir = plugin_dir / "db" / "liquibase"
        liquibase_dir.mkdir(parents=True, exist_ok=True)
        (liquibase_dir / "pluginController.xml").write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
<databaseChangeLog
  xmlns="http://www.liquibase.org/xml/ns/dbchangelog"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  logicalFilePath="plugins/{plugin_id}/db/liquibase/pluginController.xml"
  xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog https://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-4.30.xsd">
  <changeSet id="{plugin_id}-example" author="cbostock" contextFilter="plugin,prod" labels="plugin,{plugin_id}">
    <sqlFile path="../schema/table/example.sql" relativeToChangelogFile="true" endDelimiter="/" splitStatements="true" stripComments="false"/>
  </changeSet>
</databaseChangeLog>
""",
            encoding="utf-8",
        )
    (plugins_dir / f"{plugin_id}.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )


def _discover_one(plugins_dir: Path):
    manifests, errors = PluginDiscovery(plugins_dir).discover()
    if errors:
        raise AssertionError(errors)
    return manifests[0]


class PluginDatabaseDeploymentTests(unittest.TestCase):
    """Tests plugin-owned database deployment behaviour."""

    def test_expected_view_columns_are_collected_for_deployment_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins:
            plugins_dir = Path(temp_plugins)
            _write_plugin(
                plugins_dir,
                "alpha",
                _manifest("alpha", database=_database()),
            )
            manifest = _discover_one(plugins_dir)
            schema_path = plugins_dir / "alpha" / "db" / "schema"
            view_path = schema_path / "view" / "example_v.sql"
            view_path.parent.mkdir(parents=True)
            view_path.write_text(
                "-- orac-expected-columns: entity_id, last_updated\n"
                "create or replace view orac_ha.example_v as\n"
                "select entity_id, last_updated from orac_ha.example_table;\n",
                encoding="utf-8",
            )

            expected = expected_deployment_objects(
                manifest=manifest,
                schema_payload_path=schema_path,
            )

            self.assertEqual(
                expected["columns"],
                [
                    {
                        "owner": "ORAC_HA",
                        "object_name": "EXAMPLE_V",
                        "column_name": "ENTITY_ID",
                    },
                    {
                        "owner": "ORAC_HA",
                        "object_name": "EXAMPLE_V",
                        "column_name": "LAST_UPDATED",
                    },
                ],
            )

    def test_payload_verification_sql_checks_expected_columns(self) -> None:
        sql = _payload_objects_deployed_sql(
            expected={
                "objects": [],
                "grants": [],
                "columns": [
                    {
                        "owner": "ORAC_HA",
                        "object_name": "HA_CONTROL_RESOLUTION_V",
                        "column_name": "LAST_UPDATED",
                    }
                ],
            },
            oracle_pdb="FREEPDB1",
        )

        self.assertIn("from dba_tab_columns", sql)
        self.assertIn("table_name = 'HA_CONTROL_RESOLUTION_V'", sql)
        self.assertIn("column_name = 'LAST_UPDATED'", sql)

    def test_protected_schema_list_is_centralised(self) -> None:
        self.assertIn("orac_core", PROTECTED_ORAC_SCHEMAS)
        self.assertIn("orac_api", PROTECTED_ORAC_SCHEMAS)

    def test_database_deployment_defaults_to_sqlplus(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins:
            plugins_dir = Path(temp_plugins)
            _write_plugin(
                plugins_dir,
                "alpha",
                _manifest("alpha", database=_database()),
            )

            manifest = _discover_one(plugins_dir)

            self.assertEqual(manifest.database_deployment.deployment_type, "sqlplus")
            self.assertIsNone(manifest.database_deployment.controller)

    def test_database_deployment_liquibase_metadata_is_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins:
            plugins_dir = Path(temp_plugins)
            _write_plugin(
                plugins_dir,
                "alpha",
                _manifest(
                    "alpha",
                    database=_database(
                        deployment={
                            "type": "liquibase",
                            "controller": "db/liquibase/pluginController.xml",
                        }
                    ),
                ),
            )

            manifest = _discover_one(plugins_dir)

            self.assertEqual(manifest.database_deployment.deployment_type, "liquibase")
            self.assertEqual(
                manifest.database_deployment.controller,
                "db/liquibase/pluginController.xml",
            )

    def test_plugin_without_database_section_behaves_as_before(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins, tempfile.TemporaryDirectory() as temp_cache:
            plugins_dir = Path(temp_plugins)
            _write_plugin(plugins_dir, "alpha", _manifest("alpha"))
            manager = PluginManager(
                embedding_provider=HashEmbeddingProvider(),
                plugins_dir=plugins_dir,
                cache_dir=Path(temp_cache),
            )

            report = manager.refresh()

            self.assertEqual(report["indexed_plugin_count"], 1)
            self.assertEqual(report["deployment_status"]["alpha"], "not_required")
            self.assertIsNotNone(manager.get_manifest("alpha"))

    def test_required_missing_schema_warn_disable_disables_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins, tempfile.TemporaryDirectory() as temp_cache:
            plugins_dir = Path(temp_plugins)
            _write_plugin(plugins_dir, "alpha", _manifest("alpha", database=_database()))
            manager = PluginManager(
                embedding_provider=HashEmbeddingProvider(),
                plugins_dir=plugins_dir,
                cache_dir=Path(temp_cache),
            )

            report = manager.refresh()

            self.assertEqual(report["indexed_plugin_count"], 0)
            self.assertEqual(report["dependency_disabled"], 1)
            self.assertEqual(report["deployment_status"]["alpha"], "missing_disabled")
            self.assertIsNone(manager.get_manifest("alpha"))

    def test_optional_missing_schema_does_not_disable_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins, tempfile.TemporaryDirectory() as temp_cache:
            plugins_dir = Path(temp_plugins)
            _write_plugin(
                plugins_dir,
                "alpha",
                _manifest("alpha", database=_database(required=False)),
            )
            manager = PluginManager(
                embedding_provider=HashEmbeddingProvider(),
                plugins_dir=plugins_dir,
                cache_dir=Path(temp_cache),
            )

            report = manager.refresh()

            self.assertEqual(report["indexed_plugin_count"], 1)
            self.assertEqual(report["deployment_status"]["alpha"], "optional_missing")
            self.assertIsNotNone(manager.get_manifest("alpha"))

    def test_optional_deployment_failure_does_not_disable_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins, tempfile.TemporaryDirectory() as temp_cache, tempfile.TemporaryDirectory() as temp_archive:
            plugins_dir = Path(temp_plugins)
            _write_plugin(
                plugins_dir,
                "alpha",
                _manifest("alpha", database=_database(required=False)),
                with_schema=True,
            )
            deployer = PluginDatabaseDeployer(
                runner=_FakeRunner(fail=True),
                schema_provisioner=_FakeProvisioner(),
                archive_root=Path(temp_archive),
                clock=lambda: datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
            )
            manager = PluginManager(
                embedding_provider=HashEmbeddingProvider(),
                plugins_dir=plugins_dir,
                cache_dir=Path(temp_cache),
                database_deployer=deployer,
            )

            report = manager.refresh()

            self.assertEqual(report["indexed_plugin_count"], 1)
            self.assertEqual(report["deployment_status"]["alpha"], "deployment_failed")
            self.assertIsNotNone(manager.get_manifest("alpha"))

    def test_declared_protected_schema_names_are_rejected(self) -> None:
        for schema_name in ("orac", "ORAC_CORE"):
            with self.subTest(schema_name=schema_name):
                with tempfile.TemporaryDirectory() as temp_plugins:
                    plugins_dir = Path(temp_plugins)
                    _write_plugin(
                        plugins_dir,
                        "alpha",
                        _manifest("alpha", database=_database(schema_name)),
                        with_schema=True,
                    )

                    manifests, errors = PluginDiscovery(plugins_dir).discover()

                    self.assertEqual(manifests, [])
                    self.assertEqual(len(errors), 1)
                    self.assertIn("protected Orac schema", errors[0])

    def test_static_scanner_rejects_protected_schema_references(self) -> None:
        cases = {
            "synonym": "create synonym x for orac_core.some_table;\n",
            "grant": "grant select on orac_api.some_view to orac_ha;\n",
            "select": "select * from orac_code.some_package;\n",
            "quoted": 'select * from "ORAC_CORE".some_table;\n',
        }
        for label, ddl in cases.items():
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as temp_dir:
                    schema_dir = Path(temp_dir) / "db" / "schema" / "table"
                    schema_dir.mkdir(parents=True)
                    ddl_path = schema_dir / "bad.sql"
                    ddl_path.write_text(ddl, encoding="utf-8")

                    violations = scan_protected_schema_references(schema_dir.parent)

                    self.assertEqual(len(violations), 1)
                    self.assertEqual(violations[0].path, ddl_path)
                    self.assertEqual(violations[0].line_number, 1)
                    self.assertIn("orac_", violations[0].schema_name)
                    with self.assertRaises(PluginDatabaseDeploymentError):
                        validate_schema_payload(schema_dir.parent)

    def test_valid_home_assistant_payload_passes_static_validation(self) -> None:
        manifest = next(
            item
            for item in PluginDiscovery(Path("plugins")).discover()[0]
            if item.plugin_id == "home_assistant"
        )

        validate_declared_database_schemas(manifest)
        validate_schema_payload(manifest.plugin_dir / "db" / "schema")

        self.assertEqual(manifest.database_schemas[0].schema_name, "orac_ha")

    def test_home_assistant_uses_liquibase_deployment_controller(self) -> None:
        manifest = next(
            item
            for item in PluginDiscovery(Path("plugins")).discover()[0]
            if item.plugin_id == "home_assistant"
        )

        self.assertEqual(manifest.database_deployment.deployment_type, "liquibase")
        self.assertEqual(
            manifest.database_deployment.controller,
            "db/liquibase/pluginController.xml",
        )

    def test_home_assistant_liquibase_controller_has_stable_identity(self) -> None:
        controller = Path("plugins") / "home_assistant" / "db" / "liquibase" / "pluginController.xml"
        text = controller.read_text(encoding="utf-8")
        controller_dir = controller.parent / "controllers"

        self.assertIn(
            'logicalFilePath="plugins/home_assistant/db/liquibase/pluginController.xml"',
            text,
        )
        self.assertIn("dbchangelog-4.30.xsd", text)
        self.assertNotIn("<sqlFile", text)
        self.assertNotIn("includeAll", text)
        self.assertIn('file="controllers/01_table.xml"', text)
        self.assertIn('file="controllers/11_comment.xml"', text)
        self.assertTrue((controller_dir / "01_table.xml").is_file())
        self.assertTrue((controller_dir / "11_comment.xml").is_file())

    def test_home_assistant_liquibase_controller_validates_referenced_sql(self) -> None:
        manifest = next(
            item
            for item in PluginDiscovery(Path("plugins")).discover()[0]
            if item.plugin_id == "home_assistant"
        )

        referenced = validate_plugin_liquibase_changelog(manifest)
        plugin_dir = manifest.plugin_dir.resolve()
        referenced_relative = {
            path.relative_to(plugin_dir).as_posix()
            for path in referenced
        }

        self.assertIn("db/schema/table/ha_areas.sql", referenced_relative)
        self.assertIn("db/schema/package_body/ha_sync_api.sql", referenced_relative)
        self.assertIn("db/schema/grant/ha_sync_api_to_orac_plugin.sql", referenced_relative)
        self.assertNotIn("apex/f10010.sql", referenced_relative)

    def test_home_assistant_payload_contains_sync_api_contract(self) -> None:
        schema_dir = Path("plugins") / "home_assistant" / "db" / "schema"

        self.assertTrue((schema_dir / "table" / "ha_sync_runs.sql").is_file())
        self.assertTrue((schema_dir / "table" / "ha_source_timestamps.sql").is_file())
        self.assertTrue((schema_dir / "table" / "ha_audit_columns.sql").is_file())
        self.assertTrue((schema_dir / "package_spec" / "ha_sync_api.sql").is_file())
        self.assertTrue((schema_dir / "package_body" / "ha_sync_api.sql").is_file())
        self.assertTrue(
            (schema_dir / "grant" / "ha_sync_api_to_orac_plugin.sql").is_file()
        )

        package_body = (
            schema_dir / "package_body" / "ha_sync_api.sql"
        ).read_text(encoding="utf-8")
        grant_text = (
            schema_dir / "grant" / "ha_sync_api_to_orac_plugin.sql"
        ).read_text(encoding="utf-8")

        self.assertIn("procedure begin_sync_run", package_body)
        self.assertIn("delete from orac_ha.ha_states_current", package_body)
        self.assertIn("delete from orac_ha.ha_entities", package_body)
        self.assertIn("delete from orac_ha.ha_devices", package_body)
        self.assertIn("delete from orac_ha.ha_areas", package_body)
        self.assertIn("merge into orac_ha.ha_entities dst", package_body)
        self.assertIn("merge into orac_ha.ha_states_current dst", package_body)
        self.assertIn("json_value(p_payload, '$.created_at')) ha_created_at", package_body)
        self.assertIn("json_value(p_payload, '$.modified_at')) ha_modified_at", package_body)
        self.assertIn("dst.ha_created_at", package_body)
        self.assertIn("dst.ha_modified_at", package_body)
        self.assertNotIn("dst.created_at", package_body)
        self.assertNotIn("dst.modified_at", package_body)
        self.assertNotIn("row_version = row_version + 1", package_body)
        self.assertNotIn("updated_on     = systimestamp", package_body)
        self.assertIn(
            "grant execute on orac_ha.ha_sync_api to orac_plugin",
            grant_text,
        )

    def test_home_assistant_payload_contains_persistent_alias_contract(self) -> None:
        schema_dir = Path("plugins") / "home_assistant" / "db" / "schema"
        table_text = (schema_dir / "table" / "device_aliases.sql").read_text(
            encoding="utf-8"
        )
        primary_key_text = (schema_dir / "constraint_pk" / "dalias_pk.sql").read_text(
            encoding="utf-8"
        )
        all_foreign_keys = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (schema_dir / "constraint_fk").glob("*.sql")
        )
        view_text = (
            schema_dir / "view" / "ha_control_resolution_v.sql"
        ).read_text(encoding="utf-8")
        grant_text = (
            schema_dir / "grant" / "ha_control_resolution_v_to_orac_plugin.sql"
        ).read_text(encoding="utf-8")
        abbreviation_text = Path(
            "resources/db/data_model/table_abbreviations.csv"
        ).read_text(encoding="utf-8")

        self.assertIn("create table orac_ha.device_aliases", table_text)
        self.assertIn("alias_name", table_text)
        self.assertIn("enabled_flag", table_text)
        self.assertIn("row_version", table_text)
        self.assertIn("primary key (alias_name, entity_id)", primary_key_text)
        self.assertNotIn("device_aliases", all_foreign_keys)
        self.assertIn("create or replace view orac_ha.ha_control_resolution_v", view_text)
        self.assertIn("json_value(sta.attributes, '$.device_class')", view_text)
        self.assertIn("json_value(sta.attributes, '$.unit_of_measurement')", view_text)
        self.assertIn("sta.last_changed", view_text)
        self.assertIn("sta.last_updated", view_text)
        self.assertIn("ent.disabled_by", view_text)
        self.assertIn("dal.enabled_flag = 'Y'", view_text)
        self.assertIn("coalesce(ent.area_id, dev.area_id)", view_text)
        self.assertIn(
            "grant select on orac_ha.ha_control_resolution_v to orac_plugin",
            grant_text,
        )
        self.assertIn("device_aliases,dalias", abbreviation_text)

    def test_home_assistant_payload_uses_formatted_sql_changelogs(self) -> None:
        schema_dir = Path("plugins") / "home_assistant" / "db" / "schema"
        hard_folders = (
            "table",
            "index",
            "constraint_fk",
            "constraint_other",
            "constraint_pk",
            "constraint_uc",
        )
        for folder in hard_folders:
            for path in (schema_dir / folder).glob("*.sql"):
                with self.subTest(path=path):
                    text = path.read_text(encoding="utf-8").lower()
                    self.assertTrue(text.startswith("--liquibase formatted sql"))
                    self.assertIn("--changeset", text)
                    self.assertIn("--preconditions", text)
                    self.assertNotIn("execute immediate", text)
                    self.assertNotRegex(text, r"(?m)^declare\\s*$")
                    self.assertNotIn("runonchange:true", text)

        controller_dir = Path("plugins") / "home_assistant" / "db" / "liquibase" / "controllers"
        for path in controller_dir.glob("*.xml"):
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertNotIn("<sqlFile", text)

    def test_home_assistant_source_timestamps_and_audit_triggers_are_explicit(self) -> None:
        schema_dir = Path("plugins") / "home_assistant" / "db" / "schema"
        table_text = "\n".join(
            (schema_dir / "table" / name).read_text(encoding="utf-8").lower()
            for name in ("ha_areas.sql", "ha_devices.sql", "ha_entities.sql")
        )
        migration_text = (
            schema_dir / "table" / "ha_source_timestamps.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("ha_created_at", table_text)
        self.assertIn("ha_modified_at", table_text)
        self.assertNotRegex(table_text, r"\\bcreated_at\\s+timestamp")
        self.assertNotRegex(table_text, r"\\bmodified_at\\s+timestamp")
        self.assertIn("set ha_created_at = coalesce(ha_created_at, created_at)", migration_text)
        self.assertIn("set ha_modified_at = coalesce(ha_modified_at, modified_at)", migration_text)
        self.assertIn("drop column created_at", migration_text)
        self.assertIn("drop column modified_at", migration_text)

        for trigger_name in (
            "ha_areas_biu",
            "ha_devices_biu",
            "ha_entities_biu",
            "ha_states_current_biu",
            "ha_sync_runs_biu",
            "dalias_biu",
        ):
            trigger_text = (
                schema_dir / "trigger" / f"{trigger_name}.sql"
            ).read_text(encoding="utf-8").lower()
            with self.subTest(trigger=trigger_name):
                self.assertIn("--liquibase formatted sql", trigger_text)
                self.assertIn("before insert or update", trigger_text)
                self.assertIn("sys_context('apex$session', 'app_user')", trigger_text)
                self.assertIn("sys_context('userenv', 'proxy_user')", trigger_text)
                self.assertIn("sys_context('userenv', 'session_user')", trigger_text)
                self.assertIn(":new.row_version := nvl(:old.row_version, 1) + 1", trigger_text)

    def test_valid_schema_name_orac_ha_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins:
            plugins_dir = Path(temp_plugins)
            _write_plugin(
                plugins_dir,
                "alpha",
                _manifest("alpha", database=_database("ORAC_HA")),
                with_schema=True,
            )

            manifest = _discover_one(plugins_dir)

            self.assertEqual(manifest.database_schemas[0].schema_name, "orac_ha")
            validate_declared_database_schemas(manifest)

    def test_archive_contains_manifest_plugin_json_and_schema_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins, tempfile.TemporaryDirectory() as temp_archive:
            plugins_dir = Path(temp_plugins)
            _write_plugin(
                plugins_dir,
                "alpha",
                _manifest("alpha", database=_database()),
                with_schema=True,
            )
            manifest = _discover_one(plugins_dir)
            deployer = PluginDatabaseDeployer(
                runner=_FakeRunner(),
                archive_root=Path(temp_archive),
                clock=lambda: datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
            )

            archive = deployer.create_archive(manifest)

            with tarfile.open(archive.archive_path, "r:gz") as tar:
                names = set(tar.getnames())
                manifest_data = json.loads(tar.extractfile("manifest.json").read().decode("utf-8"))

            self.assertIn("plugin.json", names)
            self.assertIn("manifest.json", names)
            self.assertIn("db/schema/table/example.sql", names)
            self.assertEqual(manifest_data["plugin_id"], "alpha")
            self.assertEqual(manifest_data["plugin_version"], "1.0.0")
            self.assertEqual(manifest_data["schema_version"], 2)
            self.assertEqual(manifest_data["database"]["schemas"][0]["schema_name"], "orac_ha")
            self.assertEqual(manifest_data["payload_checksum"], archive.payload_checksum)
            self.assertEqual(len(archive.archive_checksum), 64)

    def test_liquibase_archive_contains_controller_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins, tempfile.TemporaryDirectory() as temp_archive:
            plugins_dir = Path(temp_plugins)
            _write_plugin(
                plugins_dir,
                "alpha",
                _manifest(
                    "alpha",
                    database=_database(deployment={"type": "liquibase"}),
                ),
                with_schema=True,
                with_liquibase=True,
            )
            manifest = _discover_one(plugins_dir)
            deployer = PluginDatabaseDeployer(
                runner=_FakeRunner(),
                liquibase_runner=_FakeRunner(),
                archive_root=Path(temp_archive),
                clock=lambda: datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
            )

            archive = deployer.create_archive(manifest)

            with tarfile.open(archive.archive_path, "r:gz") as tar:
                names = set(tar.getnames())
                manifest_data = json.loads(
                    tar.extractfile("manifest.json").read().decode("utf-8")
                )

            self.assertIn("db/liquibase/pluginController.xml", names)
            self.assertEqual(manifest_data["deployment"]["type"], "liquibase")

    def test_home_assistant_liquibase_archive_contains_controller_tree(self) -> None:
        manifest = next(
            item
            for item in PluginDiscovery(Path("plugins")).discover()[0]
            if item.plugin_id == "home_assistant"
        )
        with tempfile.TemporaryDirectory() as temp_archive:
            deployer = PluginDatabaseDeployer(
                runner=_FakeRunner(),
                liquibase_runner=_FakeRunner(),
                archive_root=Path(temp_archive),
                clock=lambda: datetime(2026, 6, 22, 12, 0, tzinfo=UTC),
            )

            archive = deployer.create_archive(manifest)

            with tarfile.open(archive.archive_path, "r:gz") as tar:
                names = set(tar.getnames())

            self.assertIn("db/liquibase/pluginController.xml", names)
            self.assertIn("db/liquibase/controllers/01_table.xml", names)
            self.assertIn("db/liquibase/controllers/11_comment.xml", names)
            self.assertIn("db/schema/table/ha_areas.sql", names)
            self.assertNotIn("apex/f10010.sql", names)

    def test_liquibase_changelog_rejects_include_all(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins:
            plugins_dir = Path(temp_plugins)
            _write_plugin(
                plugins_dir,
                "alpha",
                _manifest(
                    "alpha",
                    database=_database(deployment={"type": "liquibase"}),
                ),
                with_schema=True,
                with_liquibase=True,
            )
            controller = plugins_dir / "alpha" / "db" / "liquibase" / "pluginController.xml"
            controller.write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<databaseChangeLog xmlns="http://www.liquibase.org/xml/ns/dbchangelog">
  <includeAll path="../schema" relativeToChangelogFile="true"/>
</databaseChangeLog>
""",
                encoding="utf-8",
            )
            manifest = _discover_one(plugins_dir)

            with self.assertRaises(PluginDatabaseDeploymentError) as exc:
                validate_plugin_liquibase_changelog(manifest)

            self.assertIn("includeAll is not allowed", str(exc.exception))

    def test_liquibase_changelog_accepts_sqlfile_wrappers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins:
            plugins_dir = Path(temp_plugins)
            _write_plugin(
                plugins_dir,
                "alpha",
                _manifest(
                    "alpha",
                    database=_database(deployment={"type": "liquibase"}),
                ),
                with_schema=True,
                with_liquibase=True,
            )
            manifest = _discover_one(plugins_dir)

            referenced = validate_plugin_liquibase_changelog(manifest)

            self.assertEqual(len(referenced), 1)
            self.assertEqual(referenced[0].name, "example.sql")

    def test_plugin_security_rejects_cross_plugin_schema_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins:
            plugins_dir = Path(temp_plugins)
            _write_plugin(
                plugins_dir,
                "alpha",
                _manifest("alpha", database=_database()),
                with_schema=True,
                ddl="create or replace view orac_ha.bad_v as select * from orac_beta.some_table;\n",
            )
            manifest = _discover_one(plugins_dir)

            with self.assertRaises(PluginDatabaseDeploymentError) as exc:
                validate_schema_payload(
                    manifest.plugin_dir / "db" / "schema",
                    manifest=manifest,
                )

            self.assertIn("undeclared plugin-like schema 'orac_beta'", str(exc.exception))

    def test_plugin_security_rejects_public_synonym(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins:
            plugins_dir = Path(temp_plugins)
            _write_plugin(
                plugins_dir,
                "alpha",
                _manifest("alpha", database=_database()),
                with_schema=True,
                ddl="create public synonym bad_syn for orac_ha.example_table;\n",
            )
            manifest = _discover_one(plugins_dir)

            with self.assertRaises(PluginDatabaseDeploymentError) as exc:
                validate_schema_payload(
                    manifest.plugin_dir / "db" / "schema",
                    manifest=manifest,
                )

            self.assertIn("public synonyms are not allowed", str(exc.exception))

    def test_liquibase_runner_invokes_isolated_schema_deploy_script(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            script_path = temp_path / "deploy-plugin-liquibase-db.sh"
            script_path.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            archive_path = temp_path / "alpha-db.tar.gz"
            archive_path.write_bytes(b"archive")
            commands: list[list[str]] = []

            def command_runner(command, **_kwargs):
                commands.append(command)
                return subprocess.CompletedProcess(command, 0, "", "")

            runner = DockerPluginLiquibaseDatabaseRunner(
                deploy_script_source_path=script_path,
                command_runner=command_runner,
            )
            manifest = type(
                "Manifest",
                (),
                {
                    "plugin_id": "alpha",
                    "version": "1.0.0",
                    "database_deployment": type(
                        "Deployment",
                        (),
                        {"controller": "db/liquibase/pluginController.xml"},
                    )(),
                    "database_schemas": [
                        type("Schema", (), {"schema_name": "orac_alpha"})()
                    ],
                },
            )()
            archive = PluginDatabaseArchive(
                archive_path=archive_path,
                payload_checksum="a" * 64,
                archive_checksum="b" * 64,
                manifest={},
            )

            runner.deploy(manifest=manifest, archive=archive)

            self.assertIn("deploy-plugin-liquibase-db.sh", commands[0][2])
            self.assertIn("--schema-name", commands[-1])
            self.assertIn("ORAC_ALPHA", commands[-1])
            self.assertIn("--default-schema-name", commands[-1])
            self.assertIn("--liquibase-schema-name", commands[-1])
            self.assertIn("--controller", commands[-1])

    def test_liquibase_deployer_uses_liquibase_runner_for_state_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins, tempfile.TemporaryDirectory() as temp_archive:
            plugins_dir = Path(temp_plugins)
            _write_plugin(
                plugins_dir,
                "alpha",
                _manifest(
                    "alpha",
                    database=_database(deployment={"type": "liquibase"}),
                ),
                with_schema=True,
                with_liquibase=True,
            )
            manifest = _discover_one(plugins_dir)
            sqlplus_runner = _FakeRunner(already_deployed=True)
            liquibase_runner = _FakeRunner(already_deployed=False)
            provisioner = _FakeProvisioner()
            deployer = PluginDatabaseDeployer(
                runner=sqlplus_runner,
                liquibase_runner=liquibase_runner,
                schema_provisioner=provisioner,
                archive_root=Path(temp_archive),
                clock=lambda: datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
            )

            result = deployer.deploy_if_needed(manifest)

            self.assertEqual(result.status, "deployed")
            self.assertEqual(len(sqlplus_runner.already_deployed_calls), 0)
            self.assertEqual(len(sqlplus_runner.calls), 0)
            self.assertEqual(len(liquibase_runner.already_deployed_calls), 1)
            self.assertEqual(len(liquibase_runner.calls), 1)

    def test_liquibase_already_deployed_sql_requires_schema_and_tracking(self) -> None:
        sql = _already_deployed_sql(
            plugin_id="alpha",
            plugin_version="1.0.0",
            payload_checksum="a" * 64,
            schema_names=["orac_alpha"],
            oracle_pdb="FREEPDB1",
            require_liquibase_tracking=True,
        )

        self.assertIn("from dba_users", sql)
        self.assertIn("'ORAC_ALPHA'", sql)
        self.assertIn("'DATABASECHANGELOG'", sql)
        self.assertIn("'DATABASECHANGELOGLOCK'", sql)
        self.assertIn("from ORAC_ALPHA.databasechangelog", sql)

    def test_deployment_failure_prevents_routing_eligibility(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins, tempfile.TemporaryDirectory() as temp_cache, tempfile.TemporaryDirectory() as temp_archive:
            plugins_dir = Path(temp_plugins)
            _write_plugin(
                plugins_dir,
                "alpha",
                _manifest("alpha", database=_database()),
                with_schema=True,
            )
            runner = _FakeRunner(fail=True)
            deployer = PluginDatabaseDeployer(
                runner=runner,
                schema_provisioner=_FakeProvisioner(),
                archive_root=Path(temp_archive),
                clock=lambda: datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
            )
            manager = PluginManager(
                embedding_provider=HashEmbeddingProvider(),
                plugins_dir=plugins_dir,
                cache_dir=Path(temp_cache),
                database_deployer=deployer,
            )

            report = manager.refresh()

            self.assertEqual(report["indexed_plugin_count"], 0)
            self.assertEqual(report["deployment_status"]["alpha"], "deployment_failed")
            self.assertIsNone(manager.get_manifest("alpha"))
            self.assertEqual(len(runner.calls), 1)

    def test_deployment_success_allows_routing_eligibility(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins, tempfile.TemporaryDirectory() as temp_cache, tempfile.TemporaryDirectory() as temp_archive:
            plugins_dir = Path(temp_plugins)
            _write_plugin(
                plugins_dir,
                "alpha",
                _manifest("alpha", database=_database()),
                with_schema=True,
            )
            runner = _FakeRunner()
            deployer = PluginDatabaseDeployer(
                runner=runner,
                schema_provisioner=_FakeProvisioner(),
                archive_root=Path(temp_archive),
                clock=lambda: datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
            )
            manager = PluginManager(
                embedding_provider=HashEmbeddingProvider(),
                plugins_dir=plugins_dir,
                cache_dir=Path(temp_cache),
                database_deployer=deployer,
            )

            report = manager.refresh()

            self.assertEqual(report["indexed_plugin_count"], 1)
            self.assertEqual(report["deployment_status"]["alpha"], "deployed")
            self.assertIsNotNone(manager.get_manifest("alpha"))
            self.assertEqual(len(runner.calls), 1)

    def test_deployment_lifecycle_is_logged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins, tempfile.TemporaryDirectory() as temp_archive:
            plugins_dir = Path(temp_plugins)
            _write_plugin(
                plugins_dir,
                "alpha",
                _manifest("alpha", database=_database()),
                with_schema=True,
            )
            manifest = _discover_one(plugins_dir)
            logger = _FakeLogger()
            deployer = PluginDatabaseDeployer(
                runner=_FakeRunner(),
                schema_provisioner=_FakeProvisioner(),
                archive_root=Path(temp_archive),
                clock=lambda: datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
                logger=logger,
            )

            result = deployer.deploy_if_needed(manifest)

            self.assertEqual(result.status, "deployed")
            log_text = "\n".join(logger.info)
            self.assertIn("deployment check starting", log_text)
            self.assertIn("payload validated", log_text)
            self.assertIn("Provisioning plugin database schemas", log_text)
            self.assertIn("Packaging plugin database payload", log_text)
            self.assertIn("Staging and deploying plugin database archive", log_text)

    def test_docker_runner_syncs_container_deploy_script_before_archive_deploy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            script_path = temp_path / "deploy-plugin-db.sh"
            script_path.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            archive_path = temp_path / "alpha-db.tar.gz"
            archive_path.write_bytes(b"archive")
            commands: list[list[str]] = []

            def command_runner(command, **_kwargs):
                commands.append(command)
                return subprocess.CompletedProcess(command, 0, "", "")

            runner = DockerPluginDatabaseRunner(
                deploy_script_source_path=script_path,
                command_runner=command_runner,
            )
            manifest = type(
                "Manifest",
                (),
                {"plugin_id": "alpha", "version": "1.0.0"},
            )()
            archive = PluginDatabaseArchive(
                archive_path=archive_path,
                payload_checksum="a" * 64,
                archive_checksum="b" * 64,
                manifest={},
            )

            runner.deploy(manifest=manifest, archive=archive)

            self.assertEqual(commands[0][0:2], ["docker", "cp"])
            self.assertEqual(commands[0][1], "cp")
            self.assertIn("deploy-plugin-db.sh", commands[0][2])
            self.assertEqual(commands[1][0:3], ["docker", "exec", "-u"])
            self.assertIn("chmod 750", commands[1][-1])
            self.assertIn("--archive", commands[-1])

    def test_existing_successful_checksum_skips_redeployment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins, tempfile.TemporaryDirectory() as temp_cache, tempfile.TemporaryDirectory() as temp_archive:
            plugins_dir = Path(temp_plugins)
            _write_plugin(
                plugins_dir,
                "alpha",
                _manifest("alpha", database=_database()),
                with_schema=True,
            )
            runner = _FakeRunner(already_deployed=True)
            deployer = PluginDatabaseDeployer(
                runner=runner,
                schema_provisioner=_FakeProvisioner(),
                archive_root=Path(temp_archive),
                clock=lambda: datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
            )
            manager = PluginManager(
                embedding_provider=HashEmbeddingProvider(),
                plugins_dir=plugins_dir,
                cache_dir=Path(temp_cache),
                database_deployer=deployer,
            )

            report = manager.refresh()

            self.assertEqual(report["indexed_plugin_count"], 1)
            self.assertEqual(report["deployment_status"]["alpha"], "already_deployed")
            self.assertIsNotNone(manager.get_manifest("alpha"))
            self.assertEqual(len(runner.already_deployed_calls), 1)
            self.assertEqual(len(runner.calls), 0)

    def test_existing_valid_payload_objects_skip_stale_checksum_redeployment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins, tempfile.TemporaryDirectory() as temp_cache, tempfile.TemporaryDirectory() as temp_archive:
            plugins_dir = Path(temp_plugins)
            _write_plugin(
                plugins_dir,
                "alpha",
                _manifest("alpha", database=_database()),
                with_schema=True,
            )
            runner = _FakeRunner(
                already_deployed=False,
                payload_objects_deployed=True,
            )
            provisioner = _FakeProvisioner()
            deployer = PluginDatabaseDeployer(
                runner=runner,
                schema_provisioner=provisioner,
                archive_root=Path(temp_archive),
                clock=lambda: datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
            )
            manager = PluginManager(
                embedding_provider=HashEmbeddingProvider(),
                plugins_dir=plugins_dir,
                cache_dir=Path(temp_cache),
                database_deployer=deployer,
            )

            report = manager.refresh()

            self.assertEqual(report["indexed_plugin_count"], 1)
            self.assertEqual(report["deployment_status"]["alpha"], "already_deployed")
            self.assertIsNotNone(manager.get_manifest("alpha"))
            self.assertEqual(len(runner.already_deployed_calls), 1)
            self.assertEqual(len(runner.payload_objects_deployed_calls), 1)
            self.assertEqual(len(runner.mark_payload_deployed_calls), 1)
            self.assertEqual(len(provisioner.calls), 0)
            self.assertEqual(len(runner.calls), 0)

    def test_liquibase_stale_checksum_runs_update_even_when_objects_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins, tempfile.TemporaryDirectory() as temp_cache, tempfile.TemporaryDirectory() as temp_archive:
            plugins_dir = Path(temp_plugins)
            _write_plugin(
                plugins_dir,
                "alpha",
                _manifest(
                    "alpha",
                    database=_database(
                        deployment={"type": "liquibase", "controller": "db/liquibase/pluginController.xml"}
                    ),
                ),
                with_schema=True,
                with_liquibase=True,
            )
            runner = _FakeRunner(
                already_deployed=False,
                payload_objects_deployed=True,
            )
            provisioner = _FakeProvisioner()
            deployer = PluginDatabaseDeployer(
                liquibase_runner=runner,
                schema_provisioner=provisioner,
                archive_root=Path(temp_archive),
                clock=lambda: datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
            )
            manager = PluginManager(
                embedding_provider=HashEmbeddingProvider(),
                plugins_dir=plugins_dir,
                cache_dir=Path(temp_cache),
                database_deployer=deployer,
            )

            report = manager.refresh()

            self.assertEqual(report["indexed_plugin_count"], 1)
            self.assertEqual(report["deployment_status"]["alpha"], "deployed")
            self.assertEqual(len(runner.already_deployed_calls), 1)
            self.assertEqual(len(runner.payload_objects_deployed_calls), 0)
            self.assertEqual(len(runner.mark_payload_deployed_calls), 0)
            self.assertEqual(len(provisioner.calls), 1)
            self.assertEqual(len(runner.calls), 1)

    def test_schema_provisioner_creates_missing_plugin_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins:
            plugins_dir = Path(temp_plugins)
            _write_plugin(
                plugins_dir,
                "alpha",
                _manifest("alpha", database=_database()),
                with_schema=True,
            )
            manifest = _discover_one(plugins_dir)
            cursor = _FakeCursor(user_exists=False)
            session = _FakeSession(cursor)
            provisioner = PluginDatabaseSchemaProvisioner(
                session_factory=lambda: session,
                password_factory=lambda: "generated-password",
            )

            provisioner.ensure_schemas(manifest)

            statements = [statement for statement, _binds in cursor.statements]
            self.assertIn(
                "select count(*) from dba_users where username = :schema_name",
                statements[0],
            )
            self.assertTrue(
                any(
                    statement.startswith("create user ORAC_HA identified by")
                    for statement in statements
                )
            )
            self.assertIn("alter user ORAC_HA quota unlimited on users", statements)
            self.assertIn("grant create table to ORAC_HA", statements)
            self.assertTrue(session.committed)
            self.assertTrue(session.closed)


if __name__ == "__main__":
    unittest.main()
