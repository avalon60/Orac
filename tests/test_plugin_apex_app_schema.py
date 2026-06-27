"""Static checks for plugin APEX app registry schema assets."""
# Author: Clive Bostock
# Date: 2026-06-20
# Description: Verifies plugin APEX app registry DDL and grants remain narrow.

from __future__ import annotations

import configparser
from pathlib import Path
import re
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
APEX_ROOT = PROJECT_ROOT / "resources/db/apex"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


class PluginApexAppSchemaTests(unittest.TestCase):
    """Verify static schema assets for plugin-supplied APEX app registration."""

    def test_core_registry_assets_are_declared(self) -> None:
        expected = (
            "resources/db/schema/orac_core/table/plugin_apex_apps.sql",
            "resources/db/schema/orac_core/index/plg_apxapp_pk.sql",
            "resources/db/schema/orac_core/index/plg_apxapp_uk1_idx.sql",
            "resources/db/schema/orac_core/index/plg_apxapp_idx1.sql",
            "resources/db/schema/orac_core/constraint_pk/plg_apxapp_pk.sql",
            "resources/db/schema/orac_core/constraint_uc/plg_apxapp_uk1.sql",
            "resources/db/schema/orac_core/constraint_other/plg_apxapp_ck1.sql",
            "resources/db/schema/orac_core/constraint_other/plg_apxapp_ck2.sql",
            "resources/db/schema/orac_core/trigger/plg_apxapp_bu.sql",
            "resources/db/schema/orac_core/comment/plugin_apex_apps.sql",
        )

        for relative_path in expected:
            with self.subTest(relative_path=relative_path):
                self.assertTrue((PROJECT_ROOT / relative_path).is_file())

    def test_core_apex_exports_live_outside_schema_root(self) -> None:
        """Orac-owned APEX exports must not be mixed into schema controllers."""
        old_schema_root = PROJECT_ROOT / "resources" / "db" / "schema" / "orac_core"

        self.assertTrue((APEX_ROOT / "orac_ws").is_dir())
        self.assertTrue((APEX_ROOT / "orac_apps").is_dir())
        self.assertFalse((old_schema_root / "orac_ws").exists())
        self.assertFalse((old_schema_root / "orac_apps").exists())

    def test_plugin_apex_app_admin_api_assets_are_declared(self) -> None:
        expected = (
            "resources/db/schema/orac_code/package_spec/plugin_apex_app_admin_api.sql",
            "resources/db/schema/orac_code/package_body/plugin_apex_app_admin_api.sql",
        )

        for relative_path in expected:
            with self.subTest(relative_path=relative_path):
                self.assertTrue((PROJECT_ROOT / relative_path).is_file())

    def test_table_abbreviation_is_registered(self) -> None:
        abbreviations = (
            PROJECT_ROOT / "docs" / "agent-guardrails" / "table-abbreviations.csv"
        ).read_text(encoding="utf-8")

        self.assertIn("orac_core,plugin_apex_apps,plg_apxapp", abbreviations)

    def test_menu_view_lists_only_installed_enabled_apps(self) -> None:
        view_sql = (
            PROJECT_ROOT
            / "resources/db/schema/orac_code/view/plugin_apex_app_menu_v.sql"
        ).read_text(encoding="utf-8")

        self.assertIn("enabled = 'Y'", view_sql)
        self.assertIn("install_status = 'installed'", view_sql)
        self.assertIn("installed_app_id is not null", view_sql)

    def test_visible_menu_view_generates_safe_card_links(self) -> None:
        view_sql = (
            PROJECT_ROOT
            / "resources/db/schema/orac_code/view/plugin_apex_app_menu_visible_v.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn(
            "create or replace force view orac_code.plugin_apex_app_menu_visible_v",
            view_sql,
        )
        self.assertIn("from orac_code.plugin_apex_app_menu_v", view_sql)
        self.assertIn("apex_util.prepare_url", view_sql)
        self.assertIn("installed_app_id", view_sql)
        self.assertIn("coalesce(entry_page_id, 1)", view_sql)
        self.assertTrue("v('app_session')" in view_sql or "app_session" in view_sql)
        self.assertIn("p_checksum_type => 'session'", view_sql)
        self.assertIn("card_link", view_sql)
        self.assertIn(":orac_theme_sync:", view_sql)
        self.assertIn(":rp::", view_sql)

    def test_visible_menu_view_fails_closed_for_required_roles(self) -> None:
        view_sql = (
            PROJECT_ROOT
            / "resources/db/schema/orac_code/view/plugin_apex_app_menu_visible_v.sql"
        ).read_text(encoding="utf-8").lower()
        package_spec = (
            PROJECT_ROOT
            / "resources/db/schema/orac_code/package_spec/plugin_apex_app_auth_api.sql"
        ).read_text(encoding="utf-8").lower()
        package_body = (
            PROJECT_ROOT
            / "resources/db/schema/orac_code/package_body/plugin_apex_app_auth_api.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("required_roles is null", view_sql)
        self.assertIn("json_serialize(required_roles", view_sql)
        self.assertIn("= '[]'", view_sql)
        self.assertIn("json_table(", view_sql)
        self.assertIn("orac_code.plugin_apex_app_auth_api.has_required_role", view_sql)
        self.assertIn("function has_required_role", package_spec)
        self.assertIn("return number", package_spec)
        self.assertIn("apex_util.find_security_group_id", package_body)
        self.assertIn("apex_util.set_security_group_id", package_body)
        self.assertIn("from apex_appl_acl_user_roles", package_body)
        self.assertIn("when 'orac_admin' then", package_body)
        self.assertIn("'administrator'", package_body)
        self.assertIn("else", package_body)
        self.assertIn("return 0", package_body)

    def test_f1043_defines_acl_roles_and_seeds_admin(self) -> None:
        export_sql = (
            PROJECT_ROOT / "resources/db/apex/orac_apps/f1043.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("wwv_flow_imp_shared.create_acl_role", export_sql)
        self.assertIn("p_static_id=>'administrator'", export_sql)
        self.assertIn("p_static_id=>'contributor'", export_sql)
        self.assertIn("p_static_id=>'reader'", export_sql)
        self.assertIn("p_users=>wwv_flow_t_varchar2('orac_admin')", export_sql)
        self.assertNotIn("apex_acl.", export_sql)

    def test_f1043_renders_plugin_apps_cards_from_visible_view(self) -> None:
        export_sql = (
            PROJECT_ROOT / "resources/db/apex/orac_apps/f1043.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("p_plug_name=>'plugin apps'", export_sql)
        self.assertIn("p_plug_display_point=>'body'", export_sql)
        self.assertIn("p_plug_source_type=>'native_cards'", export_sql)
        self.assertIn("p_plug_template=>4501440665235496320", export_sql)
        self.assertIn("t-cards--featured t-cards--block", export_sql)
        self.assertIn("force-fa-lg:t-cards--displayicons:t-cards--3cols", export_sql)
        self.assertIn("t-cards--animcolorfill", export_sql)
        self.assertIn("from orac_code.plugin_apex_app_menu_visible_v", export_sql)
        self.assertNotIn("orac_core.plugin_apex_apps", export_sql)
        self.assertIn("p_link_target=>'&card_link.'", export_sql)
        self.assertIn("p_link_target_type=>'redirect_url'", export_sql)
        self.assertIn("p_title_column_name=>'card_title'", export_sql)
        self.assertIn("p_sub_title_column_name=>'card_subtitle'", export_sql)
        self.assertIn("p_body_column_name=>'description'", export_sql)
        self.assertIn("p_icon_class_column_name=>'icon'", export_sql)

    def test_f1043_plugin_apps_cards_use_standard_dynamic_card_display(self) -> None:
        export_sql = (
            PROJECT_ROOT / "resources/db/apex/orac_apps/f1043.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("p_layout_type=>'grid'", export_sql)
        self.assertIn("p_grid_column_count=>3", export_sql)
        self.assertIn("p_icon_source_type=>'dynamic_class'", export_sql)
        self.assertIn("p_icon_position=>'top'", export_sql)
        self.assertIn("p_action_type=>'full_card'", export_sql)
        self.assertIn("p_link_target_type=>'redirect_url'", export_sql)
        self.assertIn("p_link_target=>'&card_link.'", export_sql)

    def test_f1043_synchronizes_theme_when_launched_from_orac_admin(self) -> None:
        export_sql = (
            PROJECT_ROOT / "resources/db/apex/orac_apps/f1043.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("p_current_theme_style_id=>3544795214802435419", export_sql)
        self.assertIn("p_process_name=>'synchronize orac theme style'", export_sql)
        self.assertIn(":request = ''orac_theme_sync''", export_sql)
        self.assertIn("apex_application_theme_styles", export_sql)
        self.assertIn("s.application_id = 1042", export_sql)
        self.assertIn("s.application_id = :app_id", export_sql)
        self.assertIn("s.name           = l_theme_style_name", export_sql)
        self.assertTrue(
            "apex_util.set_current_theme_style" in export_sql
            or "apex_theme.set_session_style" in export_sql
        )
        self.assertIn("when no_data_found then", export_sql)

    def test_f1042_has_plugins_navigation_entry(self) -> None:
        export_sql = (
            PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("p_list_item_link_text=>'plugins'", export_sql)
        self.assertIn(
            "p_list_item_link_target=>'f?p=&app_id.:34:&session.::&debug.::::'",
            export_sql,
        )
        self.assertIn("p_list_item_icon=>'fa-plug'", export_sql)
        self.assertIn("p_list_item_current_for_pages=>'34,35,36'", export_sql)

    def test_f1042_plugins_page_uses_standard_card_hub(self) -> None:
        export_sql = (
            PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("p_id=>34", export_sql)
        self.assertIn("p_name=>'plugins'", export_sql)
        self.assertIn("p_alias=>'plugins'", export_sql)
        self.assertIn("p_name=>'plugins cards'", export_sql)
        self.assertIn("p_plug_name=>'plugins'", export_sql)
        self.assertIn("p_plug_source_type=>'native_list'", export_sql)
        self.assertIn("p_list_template_id=>2886769488667748277", export_sql)
        self.assertIn("p_plug_template=>4501440665235496320", export_sql)
        self.assertIn("t-cards--featured t-cards--block", export_sql)
        self.assertIn("force-fa-lg:t-cards--displayicons:t-cards--3cols", export_sql)
        self.assertIn("t-cards--animcolorfill", export_sql)

    def test_f1042_plugins_card_launches_plugin_apps(self) -> None:
        export_sql = (
            PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("p_list_item_link_text=>'plugin apps'", export_sql)
        self.assertIn(
            "p_list_item_link_target=>'f?p=1043:1:&app_session.:orac_theme_sync:&debug.:rp::'",
            export_sql,
        )
        self.assertIn("p_list_item_icon=>'fa-plug'", export_sql)
        self.assertIn(
            "p_list_text_01=>'launch installed plugin applications and administration surfaces.'",
            export_sql,
        )

    def test_f1042_plugins_page_links_to_plugin_app_maintenance(self) -> None:
        export_sql = (
            PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("p_list_item_link_text=>'manage plugin apps'", export_sql)
        self.assertIn(
            "p_list_item_link_target=>'f?p=&app_id.:35:&app_session.::&debug.:::'",
            export_sql,
        )
        self.assertIn("p_list_item_icon=>'fa-list-alt'", export_sql)
        self.assertIn("p_list_item_current_for_pages=>'35,36'", export_sql)

    def test_f1042_manage_plugin_apps_report_uses_code_view(self) -> None:
        export_sql = (
            PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("p_id=>35", export_sql)
        self.assertIn("p_name=>'manage plugin apps'", export_sql)
        self.assertIn("p_plug_name=>'plugin apps'", export_sql)
        self.assertIn("p_plug_source_type=>'native_ir'", export_sql)
        self.assertIn("from orac_code.plugin_apex_apps_v", export_sql)
        self.assertNotIn("from orac_core.plugin_apex_apps", export_sql)
        self.assertIn("p_column_link=>'f?p=&app_id.:36:", export_sql)
        self.assertIn("p36_plugin_id,p36_app_alias:#plugin_id#,#app_alias#", export_sql)
        self.assertIn("p_db_column_name=>'enabled'", export_sql)
        self.assertIn("p_db_column_name=>'row_version'", export_sql)

    def test_f1042_plugin_app_form_toggles_enabled_via_admin_api(self) -> None:
        export_sql = (
            PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("p_id=>36", export_sql)
        self.assertIn("p_name=>'plugin app'", export_sql)
        self.assertIn("p_name=>'p36_enabled'", export_sql)
        self.assertIn("p_display_as=>'native_yes_no'", export_sql)
        self.assertIn("p_name=>'p36_row_version'", export_sql)
        self.assertIn("orac_code.plugin_apex_app_admin_api.set_enabled", export_sql)
        self.assertIn("p_enabled     => :p36_enabled", export_sql)
        self.assertIn("p_row_version => :p36_row_version", export_sql)
        self.assertIn("from orac_code.plugin_apex_apps_v", export_sql)
        self.assertNotRegex(
            export_sql,
            r"\b(update|insert|delete|merge)\s+(into\s+)?orac_(core|api)\.plugin_apex_apps",
        )

    def test_f1042_user_preferences_edit_route_uses_pref_id(self) -> None:
        export_sql = (
            PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("p_column_alias=>'edit_pref_id'", export_sql)
        self.assertIn(
            "p_column_link=>'f?p=&app_id.:6:&app_session.::&debug.:rp:p6_pref_id:#edit_pref_id#'",
            export_sql,
        )
        self.assertNotIn("p6_rowid", export_sql)
        self.assertNotIn("p6_rowid:#rowid#", export_sql)

    def test_f1042_user_preferences_form_uses_pref_id_primary_key(self) -> None:
        export_sql = (
            PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertRegex(
            export_sql,
            r"(?s)p_name=>'p6_pref_id'.*?,p_is_primary_key=>true",
        )
        self.assertIn(",p_include_rowid_column=>false", export_sql)
        self.assertIn(",p_attribute_01=>'p6_pref_id,request'", export_sql)

    def test_f1042_user_preferences_report_filters_editable_preferences(self) -> None:
        export_sql = (
            PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql"
        ).read_text(encoding="utf-8").lower()
        display_view_sql = (
            PROJECT_ROOT
            / "resources/db/schema/orac_code/view/user_preferences_display_v.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("from user_preferences_display_v", export_sql)
        self.assertIn("and is_active = ''y''", export_sql)
        self.assertIn("and is_user_editable = ''y''", export_sql)
        self.assertIn("coalesce(d.is_active, 'n') as is_active", display_view_sql)
        self.assertIn(
            "coalesce(d.is_user_editable, 'n') as is_user_editable",
            display_view_sql,
        )

    def test_preference_lov_api_returns_empty_lov_for_non_lov_preferences(self) -> None:
        package_body = (
            PROJECT_ROOT
            / "resources/db/schema/orac_code/package_body/preference_lov_api.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("if l_pref_definition.lov_type is null then", package_body)
        self.assertIn("return l_rows.to_clob;", package_body)
        self.assertIn("else\n        return l_rows.to_clob;", package_body)

    def test_f1042_user_preferences_lov_items_are_render_guarded(self) -> None:
        export_sql = (
            PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("when :p6_control_type = ''select_list'' then", export_sql)
        self.assertIn(
            "when :p6_control_type in (''popup_lov'', ''select_one'')",
            export_sql,
        )
        self.assertIn("else", export_sql)
        self.assertIn("to_clob(json_array())", export_sql)

    def test_f1042_weather_location_keeps_dedicated_search_path(self) -> None:
        export_sql = (
            PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("p_name=>'weather location results'", export_sql)
        self.assertIn("p6_pref_key,p6_pref_value_search_term", export_sql)
        self.assertIn("and :p6_pref_key <> ''weather_location'' then", export_sql)
        self.assertIn("$v(''p6_pref_key'') === ''weather_location''", export_sql)

    def test_user_preference_seed_hides_unwired_starred_preferences(self) -> None:
        seed_sql = (
            PROJECT_ROOT
            / "resources/db/schema/orac_core/seed_data/prfdfn_preference_catalog.sql"
        ).read_text(encoding="utf-8")

        self.assertEqual(
            self._seeded_editable_flag(seed_sql, "enable_feedback"),
            "N",
        )
        self.assertEqual(self._seeded_editable_flag(seed_sql, "push_opt_in"), "N")
        self.assertEqual(self._seeded_editable_flag(seed_sql, "rows_per_report"), "N")
        self.assertEqual(self._seeded_editable_flag(seed_sql, "temperature"), "N")
        self.assertEqual(
            self._seeded_editable_flag(seed_sql, "enable_advanced_mode"),
            "N",
        )
        self.assertEqual(self._seeded_editable_flag(seed_sql, "landing_page_id"), "N")

    def test_runtime_preference_catalogue_matches_documented_active_keys(self) -> None:
        seed_sql = (
            PROJECT_ROOT
            / "resources/db/schema/orac_core/seed_data/prfdfn_preference_catalog.sql"
        ).read_text(encoding="utf-8")
        editable_runtime_preferences = (
            "date_format",
            "force_concise",
            "max_tokens",
            "show_reasoning",
            "strip_reasoning_tags",
            "timezone",
            "tts_pitch",
            "tts_rate",
            "tts_voice",
        )

        for pref_key in editable_runtime_preferences:
            with self.subTest(pref_key=pref_key):
                self.assertEqual(self._seeded_editable_flag(seed_sql, pref_key), "Y")
                self.assertEqual(self._seeded_active_flag(seed_sql, pref_key), "Y")

    def test_shipped_config_uses_runtime_preference_default_keys(self) -> None:
        config = configparser.ConfigParser()
        config.optionxform = str
        config.read(PROJECT_ROOT / "resources/config/orac.ini", encoding="utf-8")

        expected_defaults = (
            "date_format_default",
            "force_concise_default",
            "max_tokens_default",
            "show_reasoning_default",
            "strip_reasoning_tags_default",
            "timezone_default",
            "tts_pitch_default",
            "tts_rate_default",
        )
        ambiguous_scalar_keys = (
            "date_format",
            "force_concise",
            "max_tokens",
            "show_reasoning",
            "strip_reasoning_tags",
            "timezone",
            "tts_pitch",
            "tts_rate",
        )

        self.assertTrue(config.has_section("settings"))
        for key in expected_defaults:
            with self.subTest(default_key=key):
                self.assertTrue(config.has_option("settings", key))
        for key in ambiguous_scalar_keys:
            with self.subTest(ambiguous_key=key):
                self.assertFalse(config.has_option("settings", key))

    def test_email_opt_in_removed_from_preference_catalogue(self) -> None:
        seed_sql = (
            PROJECT_ROOT
            / "resources/db/schema/orac_core/seed_data/prfdfn_preference_catalog.sql"
        ).read_text(encoding="utf-8")
        seed_merge = seed_sql.split(") src", maxsplit=1)[0]
        rollback_text = "\n".join(
            line for line in seed_sql.splitlines() if line.startswith("--rollback")
        )
        build_log = (PROJECT_ROOT / "build.log").read_text(encoding="utf-8")

        self.assertNotIn("email_opt_in", seed_merge)
        self.assertNotIn("email notifications", seed_merge.lower())
        self.assertNotIn("email_opt_in", rollback_text)
        self.assertNotIn("email_opt_in", build_log)

    def test_email_opt_in_cleanup_sql_is_idempotent(self) -> None:
        seed_sql = (
            PROJECT_ROOT
            / "resources/db/schema/orac_core/seed_data/prfdfn_preference_catalog.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn(
            "delete from orac_core.user_preferences\n where pref_key = 'email_opt_in'",
            seed_sql,
        )
        self.assertIn(
            "delete from orac_core.preference_definitions\n where pref_key = 'email_opt_in'",
            seed_sql,
        )
        self.assertLess(
            seed_sql.index("delete from orac_core.user_preferences\n where pref_key = 'email_opt_in'"),
            seed_sql.index("delete from orac_core.preference_definitions\n where pref_key = 'email_opt_in'"),
        )

    def test_orac_prefs_seed_filters_user_editable_defaults(self) -> None:
        package_body = (
            PROJECT_ROOT
            / "resources/db/schema/orac_code/package_body/orac_prefs_seed.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertEqual(package_body.count("and is_user_editable = 'y'"), 2)

    @staticmethod
    def _seeded_editable_flag(seed_sql: str, pref_key: str) -> str:
        row_sql = PluginApexAppSchemaTests._seeded_row(seed_sql, pref_key)
        flag_match = re.search(
            r"cast\(null as varchar2\(1000 byte\)\)"
            r"(?:\s+as\s+regex_pattern)?,\s*"
            r"'[YN]'(?:\s+as\s+is_required)?,\s*"
            r"'([YN])'(?:\s+as\s+is_user_editable)?,\s*\d+",
            row_sql,
            re.DOTALL,
        )
        if flag_match is None:
            raise AssertionError(f"Missing editable flag for {pref_key}")

        return flag_match.group(1)

    @staticmethod
    def _seeded_active_flag(seed_sql: str, pref_key: str) -> str:
        row_sql = PluginApexAppSchemaTests._seeded_row(seed_sql, pref_key)
        flag_match = re.search(
            r",\s*'([YN])'(?:\s+as\s+is_active)?\s*\n\s*from dual",
            row_sql,
        )
        if flag_match is None:
            raise AssertionError(f"Missing active flag for {pref_key}")

        return flag_match.group(1)

    @staticmethod
    def _seeded_row(seed_sql: str, pref_key: str) -> str:
        row_match = re.search(
            rf"select\s+'{re.escape(pref_key)}'.*?\n\s*from dual",
            seed_sql,
            re.DOTALL,
        )
        if row_match is None:
            raise AssertionError(f"Missing preference seed row for {pref_key}")

        return row_match.group(0)

    def test_plugin_apex_app_admin_api_only_toggles_enabled(self) -> None:
        package_spec = (
            PROJECT_ROOT
            / "resources/db/schema/orac_code/package_spec/plugin_apex_app_admin_api.sql"
        ).read_text(encoding="utf-8").lower()
        package_body = (
            PROJECT_ROOT
            / "resources/db/schema/orac_code/package_body/plugin_apex_app_admin_api.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("procedure set_enabled", package_spec)
        self.assertNotIn("upsert_app", package_spec)
        self.assertIn("p_enabled", package_spec)
        self.assertIn("p_row_version", package_spec)
        self.assertIn("upper(p_enabled) not in ('y', 'n')", package_body)
        self.assertIn("and row_version = p_row_version", package_body)
        self.assertIn("l_row.enabled := upper(p_enabled)", package_body)
        self.assertIn("orac_api.plugin_apex_apps_tapi.upd", package_body)

    def test_apex_exports_do_not_disable_session_rejoin(self) -> None:
        exports = (
            PROJECT_ROOT / "resources/db/apex/orac_apps/f1043.sql",
            PROJECT_ROOT / "plugins/home_assistant/apex/f10010.sql",
            PROJECT_ROOT / "plugins/drop_box/apex/f10020.sql",
        )

        for export_path in exports:
            with self.subTest(export_path=export_path):
                export_sql = export_path.read_text(encoding="utf-8").lower()
                self.assertNotIn("p_rejoin_existing_sessions=>'n'", export_sql)
                self.assertIn("p_rejoin_existing_sessions=>'y'", export_sql)
                self.assertIn("p_cookie_name=>'&workspace_cookie.'", export_sql)
                self.assertIn("p_switch_in_session_yn=>'y'", export_sql)

    def test_home_assistant_uses_plugin_app_authorization(self) -> None:
        export_sql = (
            PROJECT_ROOT / "plugins/home_assistant/apex/f10010.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertNotIn("p_attribute_01=>'return true;'", export_sql)
        self.assertIn("orac_code.plugin_apex_app_auth_api.has_required_role", export_sql)
        self.assertIn("''orac_admin''", export_sql)
        self.assertGreaterEqual(export_sql.count("p_required_role=>"), 3)

    def test_drop_box_declares_required_admin_apex_app(self) -> None:
        manifest = (PROJECT_ROOT / "plugins/drop_box.json").read_text(
            encoding="utf-8"
        ).lower()

        self.assertIn('"app_alias": "orac_dropbox_admin"', manifest)
        self.assertIn('"app_export": "apex/f10020.sql"', manifest)
        self.assertIn('"workspace": "orac"', manifest)
        self.assertIn('"parsing_schema": "orac_apx_pub"', manifest)
        self.assertIn('"application_id": 10020', manifest)
        self.assertIn('"install_required": true', manifest)
        self.assertIn('"orac_admin"', manifest)

    def test_drop_box_apex_app_uses_plugin_app_security_pattern(self) -> None:
        export_sql = (
            PROJECT_ROOT / "plugins/drop_box/apex/f10020.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("p_default_application_id=>10020", export_sql)
        self.assertIn("drop box admin", export_sql)
        self.assertIn("p_cookie_name=>'&workspace_cookie.'", export_sql)
        self.assertIn("p_switch_in_session_yn=>'y'", export_sql)
        self.assertIn("p_rejoin_existing_sessions=>'y'", export_sql)
        self.assertIn("orac_code.plugin_apex_app_auth_api.has_required_role", export_sql)
        self.assertIn("''orac_admin''", export_sql)
        self.assertIn(":request = ''orac_theme_sync''", export_sql)
        self.assertIn("s.application_id = 1042", export_sql)
        self.assertIn("s.application_id = :app_id", export_sql)
        self.assertGreaterEqual(export_sql.count("p_required_role=>"), 3)

    def test_drop_box_apex_app_uses_admin_views_and_api_only(self) -> None:
        export_sql = (
            PROJECT_ROOT / "plugins/drop_box/apex/f10020.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("orac_dropbox.drop_location_admin_v", export_sql)
        self.assertIn("orac_dropbox.drop_job_admin_v", export_sql)
        self.assertIn("orac_dropbox.drop_job_event_admin_v", export_sql)
        self.assertIn("orac_dropbox.drop_box_admin_api", export_sql)
        self.assertIn("orac_code.plugin_lov_v", export_sql)
        self.assertIn("p_name=>'drop location form'", export_sql)
        self.assertIn("p_name=>'recent jobs'", export_sql)
        self.assertIn("p_name=>'job events'", export_sql)
        self.assertNotRegex(
            export_sql,
            r"\b(insert|update|delete|merge)\s+(into\s+)?orac_dropbox\.",
        )
        self.assertNotIn("orac_core.", export_sql)
        self.assertNotIn("orac_api.", export_sql)

    def test_plugin_lov_view_is_narrow_and_apex_granted(self) -> None:
        view_sql = (
            PROJECT_ROOT / "resources/db/schema/orac_code/view/plugin_lov_v.sql"
        ).read_text(encoding="utf-8").lower()
        grants_sql = (
            PROJECT_ROOT
            / "resources/db/schema/orac_code/grant/orac_code_consumer_view_access.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("create or replace view orac_code.plugin_lov_v", view_sql)
        self.assertIn("plugin_id", view_sql)
        self.assertIn("display_label", view_sql)
        self.assertIn("plugin_version", view_sql)
        self.assertIn("install_status", view_sql)
        self.assertIn("readiness_status", view_sql)
        self.assertIn("enabled", view_sql)
        self.assertNotIn("manifest_hash", view_sql)
        self.assertNotIn("package_hash", view_sql)
        self.assertNotIn("installed_path", view_sql)
        self.assertNotIn("config_path", view_sql)
        self.assertIn("grant read on orac_code.plugin_lov_v to orac_apx_pub;", grants_sql)
        self.assertNotIn("grant read on orac_code.plugin_registry_v to orac_apx_pub", grants_sql)

    def test_home_assistant_synchronizes_theme_when_launched_from_plugin_hub(self) -> None:
        export_sql = (
            PROJECT_ROOT / "plugins/home_assistant/apex/f10010.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("p_current_theme_style_id=>3544795214802435419", export_sql)
        self.assertIn("p_process_name=>'synchronize orac theme style'", export_sql)
        self.assertIn(":request = ''orac_theme_sync''", export_sql)
        self.assertIn("apex_application_theme_styles", export_sql)
        self.assertIn("s.application_id = 1042", export_sql)
        self.assertIn("s.application_id = :app_id", export_sql)
        self.assertIn("s.name           = l_theme_style_name", export_sql)
        self.assertTrue(
            "apex_util.set_current_theme_style" in export_sql
            or "apex_theme.set_session_style" in export_sql
        )
        self.assertIn("when no_data_found then", export_sql)

    def test_plugin_docs_explain_apex_theme_inheritance(self) -> None:
        docs = (PROJECT_ROOT / "docs/plugins.md").read_text(encoding="utf-8").lower()

        self.assertIn("theme inheritance", docs)
        self.assertIn("orac_theme_sync", docs)
        self.assertIn("application `1042`", docs)
        self.assertIn("apex_application_theme_styles", docs)
        self.assertTrue(
            "apex_util.set_current_theme_style" in docs
            or "apex_theme.set_session_style" in docs
        )
        self.assertIn("orac_code.plugin_apex_app_menu_visible_v", docs)

    def test_home_assistant_status_dashboard_is_read_only(self) -> None:
        export_sql = (
            PROJECT_ROOT / "plugins/home_assistant/apex/f10010.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("p_plug_name=>'home assistant status'", export_sql)
        self.assertIn("p_plug_source_type=>'native_dynamic_content'", export_sql)
        self.assertIn("from orac_ha.ha_status_summary_v", export_sql)
        self.assertIn("last_startup_sync_at", export_sql)
        self.assertIn("last_startup_sync_status", export_sql)
        self.assertIn("last_state_sync_at", export_sql)
        self.assertIn("last_state_sync_status", export_sql)
        self.assertIn("last_areas_processed", export_sql)
        self.assertIn("last_devices_processed", export_sql)
        self.assertIn("last_entities_processed", export_sql)
        self.assertIn("last_states_processed", export_sql)
        self.assertIn("last_error_message_redacted", export_sql)
        self.assertIn("updated_at", export_sql)
        self.assertIn("last structural sync", export_sql)
        self.assertIn("last state sync", export_sql)
        self.assertIn("last redacted error", export_sql)
        self.assertNotIn("area_alias", export_sql)
        self.assertNotRegex(
            export_sql,
            r"\b(insert|update|delete|merge)\s+(into\s+)?orac_ha\.",
        )

    def test_grants_remain_narrow(self) -> None:
        package_grants = (
            PROJECT_ROOT
            / "resources/db/schema/orac_code/grant/orac_code_consumer_package_access.sql"
        ).read_text(encoding="utf-8")
        view_grants = (
            PROJECT_ROOT
            / "resources/db/schema/orac_code/grant/orac_code_consumer_view_access.sql"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "grant execute on orac_code.plugin_apex_app_registry_api to orac;",
            package_grants,
        )
        self.assertIn(
            "grant execute on orac_code.plugin_apex_app_auth_api to orac_apx_pub;",
            package_grants,
        )
        self.assertIn(
            "grant execute on orac_code.plugin_apex_app_admin_api to orac_apx_pub;",
            package_grants,
        )
        self.assertIn("grant read on orac_code.plugin_apex_app_menu_v to orac;", view_grants)
        self.assertIn(
            "grant read on orac_code.plugin_apex_app_menu_v to orac_apx_pub;",
            view_grants,
        )
        self.assertIn(
            "grant read on orac_code.plugin_apex_app_menu_visible_v to orac_apx_pub;",
            view_grants,
        )
        self.assertIn(
            "grant read on orac_code.plugin_apex_apps_v to orac_apx_pub;",
            view_grants,
        )
        self.assertNotIn(
            "grant read on orac_core.plugin_apex_apps to orac_apx_pub",
            view_grants.lower(),
        )
        self.assertNotIn("grant dba", package_grants.lower() + view_grants.lower())
        self.assertNotIn("grant all", package_grants.lower() + view_grants.lower())


if __name__ == "__main__":
    unittest.main()
