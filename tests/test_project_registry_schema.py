"""Static checks for the core project registry and ingestion target LOV."""
# Author: Clive Bostock
# Date: 11-Jul-2026
# Description: Verifies project registry schema assets and supported LOV access.

from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ProjectRegistrySchemaTests(unittest.TestCase):
    """Static checks for project registry DDL, APIs, grants, and LOV behavior."""

    def _read(self, relative_path: str) -> str:
        path = PROJECT_ROOT / relative_path
        self.assertTrue(path.exists(), f"missing expected file: {relative_path}")
        return path.read_text(encoding="utf-8")

    def test_table_abbreviation_is_registered(self) -> None:
        abbreviations = self._read("docs/agent-guardrails/table-abbreviations.csv")

        self.assertIn("orac_core,project_registry,prjreg", abbreviations)

    def test_core_project_registry_objects_exist(self) -> None:
        expected_files = [
            "resources/db/schema/orac_core/table/project_registry.sql",
            "resources/db/schema/orac_core/index/prjreg_pk.sql",
            "resources/db/schema/orac_core/index/prjreg_uk1_idx.sql",
            "resources/db/schema/orac_core/constraint_pk/prjreg_pk.sql",
            "resources/db/schema/orac_core/constraint_uc/prjreg_uk1.sql",
            "resources/db/schema/orac_core/constraint_other/prjreg_ck1.sql",
            "resources/db/schema/orac_core/constraint_other/prjreg_ck2.sql",
            "resources/db/schema/orac_core/trigger/prjreg_bu.sql",
            "resources/db/schema/orac_core/comment/project_registry.sql",
        ]

        for relative_path in expected_files:
            with self.subTest(path=relative_path):
                self.assertTrue((PROJECT_ROOT / relative_path).exists())

        table_sql = self._read(
            "resources/db/schema/orac_core/table/project_registry.sql"
        ).lower()
        self.assertIn("create table orac_core.project_registry", table_sql)
        for token in (
            "project_id",
            "project_code",
            "display_name",
            "description",
            "active_yn",
            "created_by",
            "created_on",
            "updated_by",
            "updated_on",
            "row_version",
        ):
            self.assertIn(token, table_sql)

    def test_project_registry_constraints_are_canonical(self) -> None:
        unique_sql = self._read(
            "resources/db/schema/orac_core/constraint_uc/prjreg_uk1.sql"
        ).lower()
        code_check_sql = self._read(
            "resources/db/schema/orac_core/constraint_other/prjreg_ck2.sql"
        )

        self.assertIn("unique (project_code)", unique_sql)
        self.assertIn("^[A-Z][A-Z0-9_]{1,99}$", code_check_sql)

    def test_project_registry_is_not_seeded_from_dropbox_target_keys(self) -> None:
        """Drop Box routing keys are historical values, not project evidence."""
        self.assertFalse(
            (
                PROJECT_ROOT
                / "resources/db/schema/orac_core/seed_data/project_registry.sql"
            ).exists()
        )

        seed_text = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore").lower()
            for path in (
                PROJECT_ROOT / "resources/db/schema/orac_core/seed_data"
            ).glob("*.sql")
        )
        self.assertNotIn("project_registry", seed_text)
        self.assertNotIn("orac_dropbox.drop_location", seed_text)
        self.assertNotIn("target_scope_key", seed_text)

        registry_sql = []
        for path in (PROJECT_ROOT / "resources/db/schema").rglob("*.sql"):
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            if "project_registry" in text:
                registry_sql.append(text)

        registry_text = "\n".join(registry_sql)
        self.assertNotIn("select distinct target_scope_key", registry_text)
        self.assertNotIn("insert into orac_api.project_registry_v select", registry_text)
        self.assertNotIn("insert into orac_core.project_registry select", registry_text)
        self.assertNotIn("merge into orac_core.project_registry", registry_text)
        self.assertNotIn("merge into orac_api.project_registry_v", registry_text)
        self.assertNotIn("'orac_core' project_code", registry_text)
        self.assertNotIn("select 'orac_core'", registry_text)

    def test_project_registry_api_and_code_views_use_supported_layers(self) -> None:
        api_view = self._read(
            "resources/db/schema/orac_api/view/project_registry_v.sql"
        ).lower()
        code_view = self._read(
            "resources/db/schema/orac_code/view/project_registry_v.sql"
        ).lower()
        package_spec = self._read(
            "resources/db/schema/orac_code/package_spec/project_registry_api.sql"
        ).lower()
        package_body = self._read(
            "resources/db/schema/orac_code/package_body/project_registry_api.sql"
        ).lower()

        self.assertIn("from orac_core.project_registry", api_view)
        self.assertIn("from orac_api.project_registry_v", code_view)
        self.assertNotIn("from orac_core.project_registry", code_view)
        self.assertIn("row_checksum", code_view)
        self.assertIn("procedure upsert_project", package_spec)
        self.assertIn("procedure create_project", package_spec)
        self.assertIn("procedure update_project", package_spec)
        self.assertIn("procedure deactivate_project", package_spec)
        self.assertIn("orac_api.project_registry_tapi.ins", package_body)
        self.assertIn("orac_api.project_registry_tapi.upd", package_body)
        self.assertNotIn("orac_api.project_registry_tapi.del", package_body)
        self.assertNotIn("update orac_core.project_registry", package_body)

        for audit_column in ("created_on", "created_by", "updated_on", "updated_by"):
            self.assertNotIn(audit_column, code_view)
        self.assertNotIn(", row_version", code_view)

    def test_project_registry_api_enforces_maintenance_rules(self) -> None:
        package_body = self._read(
            "resources/db/schema/orac_code/package_body/project_registry_api.sql"
        ).lower()
        tapi_spec = self._read(
            "resources/db/schema/orac_api/package_spec/project_registry_tapi.sql"
        ).lower()
        trigger_sql = self._read(
            "resources/db/schema/orac_core/trigger/prjreg_bu.sql"
        ).lower()
        self.assertIn("p_row_checksum", package_body)
        self.assertIn("project was changed by another session", package_body)
        self.assertIn("project code already exists", package_body)
        self.assertIn("project code cannot be changed", package_body)
        self.assertIn("l_row.active_yn := 'n'", package_body)
        self.assertNotIn("orac_dropbox.", package_body)
        self.assertNotIn("drop_location_admin_v", package_body)
        self.assertIn("procedure del", tapi_spec)
        self.assertIn("p_row_version", tapi_spec)
        self.assertIn("project code cannot be changed", trigger_sql)

    def test_ingestion_target_lov_is_project_only_until_capabilities_exist(
        self,
    ) -> None:
        lov_sql = self._read(
            "resources/db/schema/orac_code/view/ingestion_target_lov_v.sql"
        ).lower()
        grants_sql = self._read(
            "resources/db/schema/orac_code/grant/orac_code_consumer_view_access.sql"
        ).lower()

        self.assertIn(
            "create or replace force view orac_code.ingestion_target_lov_v",
            lov_sql,
        )
        self.assertIn("'project' target_scope_type", lov_sql)
        self.assertIn("project_code target_scope_key", lov_sql)
        self.assertIn("from orac_api.project_registry_v", lov_sql)
        self.assertNotIn("from orac_code.project_registry_v", lov_sql)
        self.assertIn("where active_yn = 'y'", lov_sql)
        self.assertNotIn("capabilities_summary", lov_sql)
        self.assertNotIn("plugin_services", lov_sql)
        self.assertNotIn("'plugin' target_scope_type", lov_sql)
        self.assertIn(
            "grant read on orac_code.ingestion_target_lov_v to orac_apx_pub;",
            grants_sql,
        )

    def test_core_run_all_includes_project_registry_assets(self) -> None:
        run_all = self._read("resources/db/schema/orac_core/run_all.sql")

        for token in (
            "@table/project_registry.sql",
            "@index/prjreg_pk.sql",
            "@index/prjreg_uk1_idx.sql",
            "@constraint_pk/prjreg_pk.sql",
            "@constraint_uc/prjreg_uk1.sql",
            "@constraint_other/prjreg_ck1.sql",
            "@constraint_other/prjreg_ck2.sql",
            "@comment/project_registry.sql",
            "@trigger/prjreg_bu.sql",
        ):
            self.assertIn(token, run_all)


if __name__ == "__main__":
    unittest.main()
