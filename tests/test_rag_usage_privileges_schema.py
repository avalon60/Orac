"""Static contract tests for database-maintained RAG usage privileges."""

# Author: Clive Bostock
# Date: 20-Jul-2026
# Description: Verifies canonical scopes, privilege history, deletion guards, grants, and APEX administration.
# Codex-assisted modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_ROOT = PROJECT_ROOT / "resources" / "db" / "schema"
CORE_ROOT = SCHEMA_ROOT / "orac_core"
CODE_ROOT = SCHEMA_ROOT / "orac_code"
DROP_BOX_ROOT = PROJECT_ROOT / "plugins" / "drop_box" / "db"
APEX_EXPORT = PROJECT_ROOT / "resources" / "db" / "apex" / "orac_apps" / "f1042.sql"
ACCEPTANCE_SQL = (
    PROJECT_ROOT
    / "resources"
    / "db"
    / "acceptance"
    / "rag_usage_privilege_lifecycle.sql"
)
DROP_BOX_MANIFEST = PROJECT_ROOT / "plugins" / "drop_box.json"


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
        spec = _read(CODE_ROOT / "package_spec" / "rag_usage_privilege_api.sql")
        body = _read(CODE_ROOT / "package_body" / "rag_usage_privilege_api.sql")
        self.assertIn("function grant_scope_usage_status_by_id", spec)
        self.assertIn("function grant_scope_usage_by_id", spec)
        self.assertIn("function revoke_scope_usage_by_id", spec)
        self.assertIn("function grant_scope_usage_status_by_id", body)
        self.assertIn("function grant_scope_usage_by_id", body)
        self.assertIn("function revoke_scope_usage_by_id", body)
        self.assertIn("procedure assess_grant_request", body)
        self.assertIn("p_lock_active_row => false", body)
        self.assertIn("p_lock_active_row => true", body)
        self.assertIn("rag_usage_grant_available", body)
        self.assertIn("where knowledge_scope_id = p_knowledge_scope_id", body)
        exact_revoke = body.split("function revoke_scope_usage_by_id", 1)[1]
        self.assertIn(
            "where rag_usage_privilege_id = p_rag_usage_privilege_id", exact_revoke
        )
        self.assertIn("for update", exact_revoke)
        self.assertIn("l_row.row_version <> p_row_version", exact_revoke)
        self.assertIn("l_row.active_yn <> 'y'", exact_revoke)
        self.assertIn("rag_usage_privilege_unknown", exact_revoke)
        self.assertIn("rag_usage_privilege_changed", exact_revoke)
        self.assertIn("rag_usage_already_revoked", exact_revoke)
        self.assertIn("rag_usage_privileges_tapi.upd", exact_revoke)
        self.assertIn("l_active_row.revoke_reason_code := 'expired'", body)
        self.assertIn("rag_usage_privileges_tapi.upd", body)
        self.assertIn("rag_usage_privileges_tapi.ins", body)
        self.assertIn("rag_usage_already_granted", body)
        self.assertNotIn("commit;", body)
        self.assertNotIn("delete from", body)

    def test_rollback_only_acceptance_covers_exact_soft_revoke(self) -> None:
        acceptance = _read(ACCEPTANCE_SQL)
        compact = " ".join(acceptance.split())

        self.assertIn("whenever sqlerror exit failure rollback", acceptance)
        self.assertIn("rollback;", acceptance)
        self.assertNotIn("commit;", acceptance)
        self.assertNotIn("--changeset", acceptance)
        self.assertNotIn("delete from", compact)
        for token in (
            "exercise_scope('project')",
            "exercise_scope('plugin')",
            "grant_scope_usage_status_by_id",
            "grant_scope_usage_by_id",
            "revoke_scope_usage_by_id",
            "new grant was not reported as available",
            "duplicate current grant was not rejected",
            "revoked grant prevented a re-grant",
            "expired grant prevented a re-grant",
            "re-grant did not soft-close the expired historical row",
            "scheduled stored-active grant was not reported as redundant",
            "conflicting scheduled grant was not rejected",
            "rag_usage_privilege_unknown",
            "rag_usage_privilege_changed",
            "rag_usage_already_revoked",
            "stored-active privilege was not versioned and soft-revoked",
            "re-grant did not create a new history row",
            "rag_usage_privilege_lifecycle_ok",
        ):
            self.assertIn(token, acceptance)

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
        manifest = _read(DROP_BOX_MANIFEST)
        self.assertIn(
            '"knowledge_scope_validation"',
            manifest,
        )
        self.assertFalse(
            (
                SCHEMA_ROOT
                / "orac_plugin"
                / "grant"
                / "knowledge_scope_validation_to_dropbox.sql"
            ).exists()
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
        self.assertIn(
            "orac_code.rag_usage_privilege_api.grant_scope_usage_by_id", page_40
        )
        self.assertIn(
            "orac_code.rag_usage_privilege_api.revoke_scope_usage_by_id", page_40
        )
        self.assertIn("orac_code.rag_usage_scope_lov_v", export)
        self.assertIn("p_name=>'p39_project_id'", export)
        self.assertIn("p_name=>'p39_plugin_registry_id'", export)
        self.assertIn("p_button_name=>'apply_filters'", export)
        self.assertIn("p_button_name=>'administer'", page_39)
        self.assertIn("p_button_position=>'right_of_ir_search_bar'", page_39)
        self.assertIn('aria-label="manage privilege"', page_39)
        self.assertIn(
            "p40_rag_usage_privilege_id:#rag_usage_privilege_id#", page_39
        )
        self.assertNotIn("p40_username", page_39)
        self.assertNotIn("p40_canonical_scope", export)
        self.assertNotIn("canonical_scope", page_39)
        self.assertNotIn("p39_scope_key", page_39)
        self.assertIn("p_db_column_name=>'scope_type'", page_39)
        self.assertIn("p_column_label=>'scope type'", page_39)
        self.assertIn("p_db_column_name=>'scope_key'", page_39)
        self.assertIn("p_column_label=>'target'", page_39)
        self.assertIn(
            "username:scope_type:scope_key:privilege_state", page_39
        )
        for action in ("native_show", "native_hide", "native_clear"):
            self.assertEqual(page_39.count(f"p_action=>'{action}'"), 2)
        self.assertIn("p_triggering_expression=>'project'", page_39)
        self.assertIn("p_triggering_expression=>'plugin'", page_39)
        self.assertIn("p_affected_elements=>'p39_project_id'", page_39)
        self.assertIn("p_affected_elements=>'p39_plugin_registry_id'", page_39)
        action_column = page_39.split("p_db_column_name=>'rag_usage_privilege_id'", 1)[
            1
        ].split(");", 1)[0]
        self.assertNotIn("p_display_text_as=>'hidden_escape_sc'", action_column)
        for item_name in (
            "p40_rag_usage_privilege_id",
            "p40_row_version",
            "p40_scope_type",
            "p40_project_scope_id",
            "p40_plugin_scope_id",
            "p40_revoke_reason_code",
        ):
            self.assertIn(f"p_name=>'{item_name}'", page_40)
        self.assertNotIn("instr(:p40_", page_40)
        self.assertNotIn("substr(:p40_", page_40)
        self.assertNotIn("scope_type || ':'", page_40)
        self.assertEqual(page_40.count("p_triggering_element=>'p40_scope_type'"), 1)
        self.assertIn("p_name=>'scope target visibility'", page_40)
        self.assertNotIn("p_action=>'native_javascript_code'", page_40)
        self.assertEqual(page_40.count("p_action=>'native_show'"), 3)
        self.assertEqual(page_40.count("p_action=>'native_hide'"), 3)
        self.assertEqual(page_40.count("p_action=>'native_clear'"), 2)
        self.assertEqual(page_40.count("p_action=>'native_enable'"), 1)
        self.assertEqual(page_40.count("p_action=>'native_disable'"), 1)
        self.assertEqual(
            page_40.count("p_action=>'native_execute_plsql_code'"), 1
        )
        self.assertNotIn("p_triggering_condition_type=>'equals'", page_40)
        self.assertIn("p_client_condition_expression=>'project'", page_40)
        self.assertIn("p_client_condition_expression=>'plugin'", page_40)
        self.assertEqual(
            page_40.count("p_client_condition_element=>'p40_scope_type'"), 2
        )
        self.assertIn("p_affected_elements=>'p40_project_scope_id'", page_40)
        self.assertIn("p_affected_elements=>'p40_plugin_scope_id'", page_40)
        self.assertEqual(page_40.count("p_execute_on_page_init=>'n'"), 4)
        self.assertIn("p_validation_name=>'eligible project is selected'", page_40)
        self.assertIn("p_validation_name=>'eligible plugin is selected'", page_40)
        self.assertIn("p_error_message=>'select an eligible project.'", page_40)
        self.assertIn("p_error_message=>'select an eligible plugin.'", page_40)
        self.assertEqual(
            page_40.count(
                "p_when_button_pressed=>wwv_flow_imp.id(15200100000000305)"
            ),
            3,
        )
        self.assertIn("p_name=>'p40_grant_status'", page_40)
        self.assertIn("p_name=>'check proposed grant'", page_40)
        self.assertIn(
            "p_triggering_element=>'p40_username,p40_scope_type,p40_project_scope_id,p40_plugin_scope_id'",
            page_40,
        )
        self.assertIn("p_plug_name=>'applicable grant exists'", page_40)
        self.assertIn(
            "an applicable grant already exists for this principal and target.",
            page_40,
        )
        self.assertIn(
            "orac_code.rag_usage_privilege_api.grant_scope_usage_status_by_id",
            page_40,
        )
        self.assertIn(
            "p_validation_name=>'applicable grant does not already exist'",
            page_40,
        )
        self.assertIn("p_client_condition_element=>'p40_grant_status'", page_40)
        self.assertEqual(
            page_40.count(
                "p_client_condition_expression=>'rag_usage_already_granted'"
            ),
            2,
        )
        self.assertIn("p_affected_button_id=>wwv_flow_imp.id(15200100000000305)", page_40)
        form_region = page_40.split("p_plug_name=>'rag usage privilege'", 1)[1].split(
            ");", 1
        )[0]
        self.assertIn("t-form--stretchinputs", form_region)
        for item_name in (
            "p40_username",
            "p40_scope_type",
            "p40_project_scope_id",
            "p40_plugin_scope_id",
            "p40_effective_on",
            "p40_expires_on",
        ):
            item = page_40.split(f"p_name=>'{item_name}'", 1)[1].split(");", 1)[0]
            self.assertIn("p_read_only_when=>'p40_rag_usage_privilege_id'", item)
            self.assertIn("p_read_only_when_type=>'item_is_not_null'", item)
            self.assertIn("p_colspan=>12", item)
            self.assertIn("p_grid_label_column_span=>3", item)
            self.assertIn("p_field_template=>", item)
            self.assertIn("p_item_template_options=>'#default#'", item)
        for item_name in ("p40_grant_reason_code", "p40_revoke_reason_code"):
            item = page_40.split(f"p_name=>'{item_name}'", 1)[1].split(");", 1)[0]
            self.assertIn("p_colspan=>12", item)
            self.assertIn("p_grid_label_column_span=>3", item)
            self.assertIn("p_field_template=>", item)
            self.assertIn("p_item_template_options=>'#default#'", item)
        self.assertIn("p_button_name=>'grant'", page_40)
        self.assertIn("p_button_condition_type=>'item_is_null'", page_40)
        self.assertIn("p_button_name=>'revoke'", page_40)
        self.assertIn("stored_active_yn = ''y''", page_40)
        self.assertIn("p_button_name=>'close'", page_40)
        self.assertIn("stored_active_yn = ''n''", page_40)
        revoke_button = page_40.split("p_button_name=>'revoke'", 1)[1].split(");", 1)[0]
        self.assertIn("p_button_execute_validations=>'n'", revoke_button)
        self.assertIn("p_confirm_message=>", revoke_button)
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
        result_item = page_40.split("p_name=>'p40_result_code'", 1)[1].split(
            ");", 1
        )[0]
        self.assertIn("p_display_as=>'native_hidden'", result_item)
        self.assertIn("'value_protected', 'y'", result_item)
        self.assertNotIn("p_prompt=>'result'", result_item)
        close_dialog = page_40.split("p_process_name=>'close dialog'", 1)[1].split(
            ");", 1
        )[0]
        self.assertIn(
            "p_attribute_01=>'p40_rag_usage_privilege_id,p40_username,p40_scope_type,request'",
            close_dialog,
        )
        self.assertIn(
            "p_process_when=>':p40_result_code in (''rag_usage_granted'', ''rag_usage_revoked'')'",
            close_dialog,
        )
        self.assertIn("p_process_when_type=>'expression'", close_dialog)
        self.assertNotIn("insert into orac_core.rag_usage_privileges", export)


if __name__ == "__main__":
    unittest.main()
