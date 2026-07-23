"""Static contract tests for database-maintained RAG usage privileges."""

# Author: Clive Bostock
# Date: 20-Jul-2026
# Description: Verifies canonical scopes, privilege history, deletion guards, grants, and APEX administration.

from __future__ import annotations

from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_ROOT = PROJECT_ROOT / "resources" / "db" / "schema"
CORE_ROOT = SCHEMA_ROOT / "orac_core"
CODE_ROOT = SCHEMA_ROOT / "orac_code"
DROP_BOX_ROOT = PROJECT_ROOT / "plugins" / "drop_box" / "db"
APEX_EXPORT = PROJECT_ROOT / "resources" / "db" / "apex" / "orac_apps" / "f1042.sql"


def _read(path: Path) -> str:
    """Return lowercase SQL text for stable contract assertions."""
    return path.read_text(encoding="utf-8").lower()


class RagUsagePrivilegeSchemaTests(unittest.TestCase):
    """Verify the database authorization architecture remains fail closed."""

    def test_scope_registry_uses_relational_xor_ownership(self) -> None:
        table = _read(CORE_ROOT / "table" / "knowledge_scopes.sql")
        checks = _read(
            CORE_ROOT / "constraint_other" / "knowledge_scope_privilege_checks.sql"
        )
        foreign_keys = _read(
            CORE_ROOT / "constraint_fk" / "knowledge_scope_privilege_fks.sql"
        )

        self.assertIn("project_id", table)
        self.assertIn("plugin_registry_id", table)
        self.assertNotIn("scope_key", table)
        self.assertIn("constraint kn_scope_ck1", checks)
        self.assertIn("references orac_core.project_registry", foreign_keys)
        self.assertIn("references orac_core.plugin_registry", foreign_keys)

    def test_privilege_history_has_deterministic_active_uniqueness(self) -> None:
        table = _read(CORE_ROOT / "table" / "rag_usage_privileges.sql")
        indexes = _read(CORE_ROOT / "index" / "knowledge_scope_privilege_indexes.sql")

        for token in (
            "user_id",
            "knowledge_scope_id",
            "privilege_code",
            "effective_on",
            "expires_on",
            "granted_by",
            "grant_reason_code",
            "revoked_by",
            "revoke_reason_code",
        ):
            self.assertIn(token, table)
        active_index = indexes[indexes.index("rag_useprv_active_uk_idx") :]
        self.assertIn("case when active_yn = 'y' then user_id end", active_index)
        self.assertNotIn("sysdate", active_index)
        self.assertNotIn("systimestamp", active_index)

    def test_expiry_and_regrant_preserve_history(self) -> None:
        body = _read(CODE_ROOT / "package_body" / "rag_usage_privilege_api.sql")
        self.assertIn("l_row.revoke_reason_code := 'expired'", body)
        self.assertIn("rag_usage_privileges_tapi.upd", body)
        self.assertIn("rag_usage_privileges_tapi.ins", body)
        self.assertIn("rag_usage_already_granted", body)
        self.assertNotIn("delete from", body)

    def test_registry_scope_creation_is_atomic_in_existing_apis(self) -> None:
        project = _read(CODE_ROOT / "package_body" / "project_registry_api.sql")
        plugin = _read(CODE_ROOT / "package_body" / "plugin_registry_api.sql")
        self.assertIn("synchronise_project_scope(l_row.project_id)", project)
        self.assertIn("synchronise_plugin_scope", plugin)
        self.assertNotIn("commit;", project)
        self.assertNotIn("commit;", plugin)

    def test_physical_delete_guards_are_independent(self) -> None:
        triggers = _read(
            CORE_ROOT / "trigger" / "knowledge_scope_privilege_triggers.sql"
        )
        for token in (
            "before delete on orac_core.project_registry",
            "before delete on orac_core.plugin_registry",
            "before delete on orac_core.knowledge_scopes",
        ):
            self.assertIn(token, triggers)
        self.assertNotIn("on delete cascade", triggers)

    def test_normalised_corpus_has_one_authoritative_scope(self) -> None:
        migration = _read(CORE_ROOT / "table" / "zz_knowledge_scope_migration.sql")
        normalization = _read(
            CORE_ROOT / "migration" / "knowledge_scope_normalization.sql"
        )
        source_view = _read(
            SCHEMA_ROOT / "orac_api" / "view" / "knowledge_source_objects_v.sql"
        )
        document_view = _read(
            SCHEMA_ROOT / "orac_api" / "view" / "knowledge_documents_v.sql"
        )
        searchable = _read(CODE_ROOT / "view" / "knowledge_searchable_chunks_v.sql")

        self.assertIn("knowledge_scope_id", source_view)
        self.assertNotIn("target_scope_type", source_view)
        self.assertNotIn("knowledge_scope_id", document_view)
        self.assertNotIn("target_scope_type", document_view)
        self.assertIn("knowledge_scope_id", migration)
        self.assertIn("drop (target_scope_type, target_scope_key)", normalization)
        self.assertIn("target_scope_type", searchable)
        self.assertIn("target_scope_key", searchable)

    def test_plugin_services_distinguish_core_and_plugin_owners(self) -> None:
        migration = _read(CORE_ROOT / "table" / "zz_knowledge_scope_migration.sql")
        checks = _read(
            CORE_ROOT / "constraint_other" / "knowledge_scope_privilege_checks.sql"
        )
        foreign_keys = _read(
            CORE_ROOT / "constraint_fk" / "knowledge_scope_privilege_fks.sql"
        )
        self.assertIn("service.plugin_id = 'orac_core'", migration)
        self.assertIn("service_owner_type = 'core'", checks)
        self.assertIn("constraint plgsvc_registry_fk", foreign_keys)

    def test_runtime_and_apex_receive_separate_privileges(self) -> None:
        grants = _read(CODE_ROOT / "grant" / "rag_usage_access.sql")
        self.assertIn(
            "grant execute on orac_code.rag_usage_authorization_api to orac;",
            grants,
        )
        self.assertIn(
            "grant execute on orac_code.rag_usage_privilege_api to orac_apx_pub;",
            grants,
        )
        self.assertNotIn(
            "rag_usage_privilege_api to orac;",
            grants,
        )

    def test_drop_box_supported_writes_validate_through_plugin_bridge(self) -> None:
        admin_body = _read(
            DROP_BOX_ROOT / "schema" / "package_body" / "drop_box_admin_api.sql"
        )
        bridge = _read(
            SCHEMA_ROOT
            / "orac_plugin"
            / "package_body"
            / "knowledge_scope_validation_api.sql"
        )
        self.assertIn(
            "orac_plugin.knowledge_scope_validation_api.scope_status", admin_body
        )
        self.assertIn("rag_usage_scope_eligible", admin_body)
        self.assertIn("orac_code.knowledge_scope_validation_api", bridge)
        bridge_grant = _read(
            SCHEMA_ROOT
            / "orac_plugin"
            / "grant"
            / "knowledge_scope_validation_to_dropbox.sql"
        )
        self.assertIn(
            "grant execute on orac_plugin.knowledge_scope_validation_api to orac_dropbox",
            bridge_grant,
        )

    def test_apex_1042_has_package_only_privilege_administration(self) -> None:
        export = _read(APEX_EXPORT)
        page_39 = export.split("prompt --application/pages/page_00039", 1)[1].split(
            "prompt --application/pages/page_00040", 1
        )[0]
        page_40 = export.split("prompt --application/pages/page_00040", 1)[1].split(
            "prompt --application/pages/page_09999", 1
        )[0]
        self.assertIn("prompt --application/pages/page_00039", export)
        self.assertIn("prompt --application/pages/page_00040", export)
        self.assertIn("rag usage privileges", export)
        self.assertIn("orac_code.rag_usage_privilege_api.grant_scope_usage", export)
        self.assertIn("orac_code.rag_usage_privilege_api.revoke_scope_usage", export)
        self.assertIn("orac_code.rag_usage_scope_lov_v", export)
        self.assertIn("p_name=>'p39_project_id'", export)
        self.assertIn("p_name=>'p39_plugin_registry_id'", export)
        self.assertIn("p_button_name=>'apply_filters'", export)
        self.assertIn("p_button_name=>'administer'", page_39)
        self.assertIn("p_button_position=>'right_of_ir_search_bar'", page_39)
        self.assertIn('aria-label="manage privilege"', page_39)
        action_column = page_39.split("p_db_column_name=>'rag_usage_privilege_id'", 1)[
            1
        ].split(");", 1)[0]
        self.assertNotIn("p_display_text_as=>'hidden_escape_sc'", action_column)
        self.assertEqual(page_40.count("p_format_mask=>'dd-mon-yyyy hh24:mi'"), 2)
        self.assertNotIn("p_format_mask=>'dd-mon-yyyy hh24:mi tzr'", page_40)
        self.assertIn(
            "from_tz(to_timestamp(:p40_effective_on, ''dd-mon-yyyy hh24:mi''), sessiontimezone)",
            page_40,
        )
        self.assertIn(
            "from_tz(to_timestamp(:p40_expires_on, ''dd-mon-yyyy hh24:mi''), sessiontimezone)",
            page_40,
        )
        self.assertNotIn("insert into orac_core.rag_usage_privileges", export)


if __name__ == "__main__":
    unittest.main()
