"""Static checks for plugin APEX app registry schema assets."""
# Author: Clive Bostock
# Date: 2026-06-20
# Description: Verifies plugin APEX app registry DDL and grants remain narrow.

from __future__ import annotations

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
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
            PROJECT_ROOT / "resources/db/schema/orac_core/orac_apps/f1043.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("wwv_flow_imp_shared.create_acl_role", export_sql)
        self.assertIn("p_static_id=>'administrator'", export_sql)
        self.assertIn("p_static_id=>'contributor'", export_sql)
        self.assertIn("p_static_id=>'reader'", export_sql)
        self.assertIn("p_users=>wwv_flow_t_varchar2('orac_admin')", export_sql)
        self.assertNotIn("apex_acl.", export_sql)

    def test_f1043_renders_plugin_apps_cards_from_visible_view(self) -> None:
        export_sql = (
            PROJECT_ROOT / "resources/db/schema/orac_core/orac_apps/f1043.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("p_plug_name=>'plugin apps'", export_sql)
        self.assertIn("p_plug_display_point=>'body'", export_sql)
        self.assertIn("p_plug_source_type=>'native_cards'", export_sql)
        self.assertIn("from orac_code.plugin_apex_app_menu_visible_v", export_sql)
        self.assertNotIn("orac_core.plugin_apex_apps", export_sql)
        self.assertIn("p_link_target=>'&card_link.'", export_sql)
        self.assertIn("p_link_target_type=>'redirect_url'", export_sql)
        self.assertIn("p_title_column_name=>'card_title'", export_sql)
        self.assertIn("p_sub_title_column_name=>'card_subtitle'", export_sql)
        self.assertIn("p_body_column_name=>'description'", export_sql)
        self.assertIn("p_icon_class_column_name=>'icon'", export_sql)

    def test_apex_exports_do_not_disable_session_rejoin(self) -> None:
        exports = (
            PROJECT_ROOT / "resources/db/schema/orac_core/orac_apps/f1043.sql",
            PROJECT_ROOT / "plugins/home_assistant/apex/f10010.sql",
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
        self.assertIn("grant read on orac_code.plugin_apex_app_menu_v to orac;", view_grants)
        self.assertIn(
            "grant read on orac_code.plugin_apex_app_menu_v to orac_apx_pub;",
            view_grants,
        )
        self.assertIn(
            "grant read on orac_code.plugin_apex_app_menu_visible_v to orac_apx_pub;",
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
