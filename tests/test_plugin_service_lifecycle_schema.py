"""Static checks for core-owned plugin service lifecycle schema."""
# Author: Clive Bostock
# Date: 02-Jul-2026
# Description: Verifies plugin service lifecycle storage, APIs, grants, and
#   database-time lease semantics.

from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_ROOT = PROJECT_ROOT / "resources" / "db" / "schema"


class PluginServiceLifecycleSchemaTests(unittest.TestCase):
    """Verify core service lifecycle schema files and boundary rules."""

    def _read(self, relative_path: str) -> str:
        return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8").lower()

    def test_core_service_table_files_and_abbreviation_are_registered(self) -> None:
        required_files = [
            "resources/db/schema/orac_core/table/plugin_services.sql",
            "resources/db/schema/orac_core/index/plgsvc_pk.sql",
            "resources/db/schema/orac_core/index/plgsvc_uk1_idx.sql",
            "resources/db/schema/orac_core/constraint_pk/plgsvc_pk.sql",
            "resources/db/schema/orac_core/constraint_uc/plgsvc_uk1.sql",
            "resources/db/schema/orac_core/constraint_other/plgsvc_ck1.sql",
            "resources/db/schema/orac_core/constraint_other/plgsvc_ck2.sql",
            "resources/db/schema/orac_core/constraint_other/plgsvc_ck3.sql",
            "resources/db/schema/orac_core/trigger/plgsvc_bu.sql",
            "resources/db/schema/orac_core/comment/plugin_services.sql",
        ]
        for relative_path in required_files:
            self.assertTrue((PROJECT_ROOT / relative_path).is_file(), relative_path)

        abbreviations = self._read("docs/agent-guardrails/table-abbreviations.csv")
        self.assertIn("orac_core,plugin_services,plgsvc", abbreviations)

    def test_core_service_table_uses_composite_logical_identity_and_char_semantics(self) -> None:
        table_sql = self._read("resources/db/schema/orac_core/table/plugin_services.sql")
        unique_sql = self._read("resources/db/schema/orac_core/constraint_uc/plgsvc_uk1.sql")
        code_check_sql = self._read("resources/db/schema/orac_core/constraint_other/plgsvc_ck3.sql")

        self.assertIn("create table orac_core.plugin_services", table_sql)
        self.assertIn("plugin_id", table_sql)
        self.assertIn("service_code", table_sql)
        self.assertIn("plugin_id         varchar2(128 char) not null", table_sql)
        self.assertIn("service_code      varchar2(128 char) not null", table_sql)
        self.assertNotIn("varchar2(128) ", table_sql)
        self.assertIn("unique (plugin_id, service_code)", unique_sql)
        self.assertIn("regexp_like(service_code, '^[a-z][a-z0-9_]{1,127}$')", code_check_sql)

    def test_policy_and_state_values_are_validated_separately(self) -> None:
        policy_sql = self._read("resources/db/schema/orac_core/constraint_other/plgsvc_ck1.sql")
        state_sql = self._read("resources/db/schema/orac_core/constraint_other/plgsvc_ck2.sql")

        self.assertIn("'disabled'", policy_sql)
        self.assertIn("'manual'", policy_sql)
        self.assertIn("'auto'", policy_sql)
        for state in (
            "registered",
            "starting",
            "running",
            "stopping",
            "stopped",
            "failed",
            "disabled",
            "lease_lost",
        ):
            self.assertIn(f"'{state}'", state_sql)

    def test_orac_code_api_exposes_atomic_lease_contract(self) -> None:
        spec_sql = self._read("resources/db/schema/orac_code/package_spec/plugin_service_api.sql")
        body_sql = self._read("resources/db/schema/orac_code/package_body/plugin_service_api.sql")
        tapi_body_sql = self._read("resources/db/schema/orac_api/package_body/plugin_services_tapi.sql")

        self.assertIn("procedure register_service", spec_sql)
        self.assertIn("procedure set_service_policy", spec_sql)
        self.assertIn("function try_acquire_service_lease", spec_sql)
        self.assertIn("function heartbeat_service_lease", spec_sql)
        self.assertIn("function release_service_lease", spec_sql)
        self.assertIn("function mark_service_state", spec_sql)
        self.assertIn("orac_api.plugin_services_tapi.try_acquire_lease", body_sql)
        self.assertNotIn("insert into orac_core.plugin_services", body_sql)
        self.assertNotIn("update orac_core.plugin_services", body_sql)
        self.assertIn("update orac_api.plugin_services_v", tapi_body_sql)
        self.assertIn("or lease_expires_on <= cast(systimestamp as timestamp)", tapi_body_sql)
        self.assertIn(
            "lease_expires_on  = cast(systimestamp as timestamp) + numtodsinterval",
            tapi_body_sql,
        )

    def test_service_status_view_and_grants_are_narrow(self) -> None:
        status_view_sql = self._read("resources/db/schema/orac_code/view/plugin_service_status_v.sql")
        code_grant_sql = self._read("resources/db/schema/orac_code/grant/plugin_service_runtime_access.sql")
        consumer_view_grant_sql = self._read(
            "resources/db/schema/orac_code/grant/orac_code_consumer_view_access.sql"
        )
        api_grant_sql = self._read("resources/db/schema/orac_api/grant/plugin_services_to_orac_code.sql")

        self.assertIn("create or replace view orac_code.plugin_service_status_v", status_view_sql)
        self.assertIn("cast(systimestamp as timestamp)", status_view_sql)
        for column in (
            "service_id",
            "plugin_id",
            "service_code",
            "effective_policy",
            "current_state",
            "owner_id",
            "lease_token",
            "lease_expires_on",
            "last_started_on",
            "last_heartbeat_on",
            "last_tick_on",
            "last_error_message",
        ):
            self.assertIn(column, status_view_sql)
        self.assertIn("grant execute on orac_code.plugin_service_api to orac;", code_grant_sql)
        self.assertIn("grant read on orac_code.plugin_service_status_v to orac;", code_grant_sql)
        self.assertIn(
            "grant read on orac_code.plugin_service_status_v to orac_apx_pub;",
            consumer_view_grant_sql,
        )
        self.assertIn("grant execute on orac_api.plugin_services_tapi to orac_code;", api_grant_sql)
        self.assertNotIn("grant read on orac_core.plugin_services to orac", code_grant_sql)

    def test_core_run_all_includes_plugin_service_objects(self) -> None:
        run_all_sql = self._read("resources/db/schema/orac_core/run_all.sql")
        expected_includes = [
            "@table/plugin_services.sql",
            "@index/plgsvc_pk.sql",
            "@index/plgsvc_uk1_idx.sql",
            "@constraint_pk/plgsvc_pk.sql",
            "@constraint_uc/plgsvc_uk1.sql",
            "@constraint_other/plgsvc_ck1.sql",
            "@constraint_other/plgsvc_ck2.sql",
            "@constraint_other/plgsvc_ck3.sql",
            "@comment/plugin_services.sql",
            "@trigger/plgsvc_bu.sql",
        ]
        for include in expected_includes:
            self.assertIn(include, run_all_sql)


if __name__ == "__main__":
    unittest.main()
