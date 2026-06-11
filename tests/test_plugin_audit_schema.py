"""Tests for the static plugin audit schema and API assets."""
# Author: Clive Bostock
# Date: 25-May-2026
# Description: Verifies plugin audit schema assets, grants, and install order.

from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_ROOT = PROJECT_ROOT / "resources/db/schema"
CORE_ROOT = SCHEMA_ROOT / "orac_core"
API_ROOT = SCHEMA_ROOT / "orac_api"
CODE_ROOT = SCHEMA_ROOT / "orac_code"


class PluginAuditSchemaTests(unittest.TestCase):
    """Static checks for the plugin audit database/API asset set."""

    def _read(self, relative_path: str) -> str:
        path = PROJECT_ROOT / relative_path
        self.assertTrue(path.exists(), f"missing expected file: {relative_path}")
        return path.read_text(encoding="utf-8")

    def test_table_abbreviations_are_canonical(self) -> None:
        """The approved abbreviations remain stable and documented."""
        abbreviations = self._read("docs/agent-guardrails/table-abbreviations.csv")

        self.assertIn("orac_core,plugin_invocations,plg_inv", abbreviations)
        self.assertIn("orac_core,plugin_audit_events,plg_audevt", abbreviations)
        self.assertNotIn("plg_aud_evt", abbreviations)

    def test_plugin_audit_core_objects_exist_and_are_named_consistently(self) -> None:
        """Core plugin audit tables, constraints, indexes, triggers, and comments exist."""
        expected_files = [
            "resources/db/schema/orac_core/table/plugin_invocations.sql",
            "resources/db/schema/orac_core/table/plugin_audit_events.sql",
            "resources/db/schema/orac_core/constraint_pk/plg_inv_pk.sql",
            "resources/db/schema/orac_core/constraint_pk/plg_audevt_pk.sql",
            "resources/db/schema/orac_core/constraint_fk/plg_inv_convs_fk1.sql",
            "resources/db/schema/orac_core/constraint_fk/plg_inv_mesgs_fk1.sql",
            "resources/db/schema/orac_core/constraint_fk/plg_inv_users_fk1.sql",
            "resources/db/schema/orac_core/constraint_fk/plg_audevt_plg_inv_fk1.sql",
            "resources/db/schema/orac_core/constraint_other/plg_inv_ck1.sql",
            "resources/db/schema/orac_core/constraint_other/plg_inv_ck2.sql",
            "resources/db/schema/orac_core/constraint_other/plg_inv_ck3.sql",
            "resources/db/schema/orac_core/constraint_other/plg_inv_ck4.sql",
            "resources/db/schema/orac_core/constraint_other/plg_audevt_ck1.sql",
            "resources/db/schema/orac_core/constraint_other/plg_audevt_ck2.sql",
            "resources/db/schema/orac_core/constraint_other/plg_audevt_ck3.sql",
            "resources/db/schema/orac_core/index/plg_inv_pk.sql",
            "resources/db/schema/orac_core/index/plg_inv_convs_fk1_idx.sql",
            "resources/db/schema/orac_core/index/plg_inv_mesgs_fk1_idx.sql",
            "resources/db/schema/orac_core/index/plg_inv_req_idx.sql",
            "resources/db/schema/orac_core/index/plg_inv_users_fk1_idx.sql",
            "resources/db/schema/orac_core/index/plg_audevt_pk.sql",
            "resources/db/schema/orac_core/index/plg_audevt_plg_inv_fk1_idx.sql",
            "resources/db/schema/orac_core/trigger/plg_inv_bu.sql",
            "resources/db/schema/orac_core/trigger/plg_audevt_bu.sql",
            "resources/db/schema/orac_core/comment/plugin_invocations.sql",
            "resources/db/schema/orac_core/comment/plugin_audit_events.sql",
        ]

        for relative_path in expected_files:
            self.assertTrue(
                (PROJECT_ROOT / relative_path).exists(),
                f"missing expected file: {relative_path}",
            )

        plugin_invocations = self._read(
            "resources/db/schema/orac_core/table/plugin_invocations.sql"
        )
        plugin_audit_events = self._read(
            "resources/db/schema/orac_core/table/plugin_audit_events.sql"
        )
        self.assertIn("create table orac_core.plugin_invocations", plugin_invocations)
        self.assertIn("create table orac_core.plugin_audit_events", plugin_audit_events)
        self.assertNotIn("plg_aud_evt", plugin_invocations)
        self.assertNotIn("plg_aud_evt", plugin_audit_events)

    def test_plugin_audit_api_objects_exist_and_are_granted(self) -> None:
        """API views, TAPIs, code packages, and grants exist for plugin audit."""
        expected_files = [
            "resources/db/schema/orac_api/view/plugin_invocations_v.sql",
            "resources/db/schema/orac_api/view/plugin_audit_events_v.sql",
            "resources/db/schema/orac_api/package_spec/plugin_invocations_tapi.sql",
            "resources/db/schema/orac_api/package_body/plugin_invocations_tapi.sql",
            "resources/db/schema/orac_api/package_spec/plugin_audit_events_tapi.sql",
            "resources/db/schema/orac_api/package_body/plugin_audit_events_tapi.sql",
            "resources/db/schema/orac_code/package_spec/plugin_audit_api.sql",
            "resources/db/schema/orac_code/package_body/plugin_audit_api.sql",
        ]

        for relative_path in expected_files:
            self.assertTrue(
                (PROJECT_ROOT / relative_path).exists(),
                f"missing expected file: {relative_path}",
            )

        api_grants = self._read(
            "resources/db/schema/orac_api/grant/orac_tapi_consumer_access.sql"
        )
        core_grants = self._read(
            "resources/db/schema/orac_api/privilege/orac_api_core_table_access.sql"
        )
        code_grants = self._read(
            "resources/db/schema/orac_code/grant/orac_code_consumer_package_access.sql"
        )

        self.assertIn(
            "grant select on orac_api.plugin_invocations_v to orac_code with grant option;",
            api_grants,
        )
        self.assertIn(
            "grant select on orac_api.plugin_audit_events_v to orac_code with grant option;",
            api_grants,
        )
        self.assertIn(
            "grant execute on orac_api.plugin_invocations_tapi to orac_code;",
            api_grants,
        )
        self.assertIn(
            "grant execute on orac_api.plugin_audit_events_tapi to orac_code;",
            api_grants,
        )
        self.assertIn(
            "grant select, insert, update, delete on orac_core.plugin_invocations to orac_api with grant option;",
            core_grants,
        )
        self.assertIn(
            "grant select, insert, update, delete on orac_core.plugin_audit_events to orac_api with grant option;",
            core_grants,
        )
        self.assertIn(
            "grant execute on orac_code.plugin_audit_api to orac;",
            code_grants,
        )

    def test_plugin_audit_install_order_includes_new_objects(self) -> None:
        """The core install order includes the plugin audit files in sequence."""
        run_all = self._read("resources/db/schema/orac_core/run_all.sql")

        for token in [
            "@table/plugin_invocations.sql",
            "@table/plugin_audit_events.sql",
            "@index/plg_inv_pk.sql",
            "@index/plg_audevt_pk.sql",
            "@constraint_pk/plg_inv_pk.sql",
            "@constraint_pk/plg_audevt_pk.sql",
            "@constraint_fk/plg_audevt_plg_inv_fk1.sql",
            "@comment/plugin_invocations.sql",
            "@comment/plugin_audit_events.sql",
            "@trigger/plg_inv_bu.sql",
            "@trigger/plg_audevt_bu.sql",
        ]:
            self.assertIn(token, run_all)

    def test_plugin_audit_package_contract_matches_runtime_usage(self) -> None:
        """The package contract matches the runtime seam documented in the docs."""
        package_spec = self._read("resources/db/schema/orac_code/package_spec/plugin_audit_api.sql")
        package_body = self._read("resources/db/schema/orac_code/package_body/plugin_audit_api.sql")
        inv_tapi_spec = self._read("resources/db/schema/orac_api/package_spec/plugin_invocations_tapi.sql")
        inv_tapi_body = self._read("resources/db/schema/orac_api/package_body/plugin_invocations_tapi.sql")
        evt_tapi_spec = self._read("resources/db/schema/orac_api/package_spec/plugin_audit_events_tapi.sql")
        evt_tapi_body = self._read("resources/db/schema/orac_api/package_body/plugin_audit_events_tapi.sql")

        for token in [
            "procedure begin_invocation(",
            "procedure record_policy_decision(",
            "procedure record_confirmation_event(",
            "procedure record_execution_event(",
            "procedure link_message(",
            "end plugin_audit_api;",
        ]:
            self.assertIn(token, package_spec)

        self.assertIn("create or replace package body orac_code.plugin_audit_api as", package_body)
        self.assertIn("end plugin_audit_api;", package_body)
        self.assertIn("create or replace package orac_api.plugin_invocations_tapi", inv_tapi_spec)
        self.assertIn("procedure ins(", inv_tapi_spec)
        self.assertIn("procedure get(", inv_tapi_spec)
        self.assertIn("procedure upd(", inv_tapi_spec)
        self.assertIn("end plugin_invocations_tapi;", inv_tapi_spec)
        self.assertIn("create or replace package body orac_api.plugin_invocations_tapi", inv_tapi_body)
        self.assertIn("end plugin_invocations_tapi;", inv_tapi_body)
        self.assertIn("create or replace package orac_api.plugin_audit_events_tapi", evt_tapi_spec)
        self.assertIn("procedure ins(", evt_tapi_spec)
        self.assertIn("procedure get(", evt_tapi_spec)
        self.assertIn("end plugin_audit_events_tapi;", evt_tapi_spec)
        self.assertIn("create or replace package body orac_api.plugin_audit_events_tapi", evt_tapi_body)
        self.assertIn("end plugin_audit_events_tapi;", evt_tapi_body)
        self.assertEqual(
            package_body.count("l_row.provenance_json := p_provenance_json;"),
            1,
        )
        self.assertIn(
            "current provenance remains preserved on the event row below",
            package_body,
        )

    def test_no_stale_plg_aud_evt_references_remain(self) -> None:
        """No stale plugin audit abbreviation references remain in the repo."""
        search_roots = [
            PROJECT_ROOT / "docs",
            PROJECT_ROOT / "resources/db/schema",
            PROJECT_ROOT / "plugins",
        ]
        matches: list[str] = []
        for root in search_roots:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in {
                    ".csv",
                    ".ini",
                    ".md",
                    ".py",
                    ".sql",
                    ".txt",
                    ".json",
                    ".sh",
                }:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore").lower()
                if "plg_aud_evt" in text:
                    matches.append(str(path.relative_to(PROJECT_ROOT)))

        self.assertEqual(matches, [])


if __name__ == "__main__":
    unittest.main()
