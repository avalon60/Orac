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

PAGE_SECTION_RE = re.compile(
    r"prompt --application/pages/page_(\d{5})(.*?)(?=prompt --application/pages/page_|\Z)",
    re.IGNORECASE | re.DOTALL,
)
PAGE_ITEM_BLOCK_RE = re.compile(
    r"wwv_flow_imp_page\.create_page_item\((.*?)\);",
    re.IGNORECASE | re.DOTALL,
)
PAGE_DA_BLOCK_RE = re.compile(
    r"wwv_flow_imp_page\.create_page_da_(?:event|action)\((.*?)\);",
    re.IGNORECASE | re.DOTALL,
)
PAGE_ITEM_NAME_RE = re.compile(r"p_name=>'([^']+)'", re.IGNORECASE)
PAGE_ITEM_REF_RE = re.compile(r"(?<![A-Z0-9_])P([0-9]+)_[A-Z0-9_]+", re.IGNORECASE)


def _apex_page_sections(export_sql: str) -> dict[int, str]:
    """Return APEX export page bodies keyed by page id."""
    return {
        int(match.group(1)): match.group(2)
        for match in PAGE_SECTION_RE.finditer(export_sql)
    }


def _apex_page_item_names(page_body: str, page_id: int) -> set[str]:
    """Return page item names defined in a single APEX export page body."""
    prefix = f"P{page_id}_"
    names: set[str] = set()
    for block_match in PAGE_ITEM_BLOCK_RE.finditer(page_body):
        name_match = PAGE_ITEM_NAME_RE.search(block_match.group(1))
        if name_match:
            item_name = name_match.group(1).upper()
            if item_name.startswith(prefix):
                names.add(item_name)
    return names


def _apex_item_references(text: str) -> set[tuple[int, str]]:
    """Return page item references found in APEX export component text."""
    return {
        (int(match.group(1)), match.group(0).upper())
        for match in PAGE_ITEM_REF_RE.finditer(text)
    }


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

    def test_plugin_registry_ui_metadata_is_projected_through_approved_path(
        self,
    ) -> None:
        table_sql = (
            (
                PROJECT_ROOT
                / "resources/db/schema/orac_core/table/plugin_registry_ui_metadata.sql"
            )
            .read_text(encoding="utf-8")
            .lower()
        )
        api_view_sql = (
            (PROJECT_ROOT / "resources/db/schema/orac_api/view/plugin_registry_v.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        code_view_sql = (
            (PROJECT_ROOT / "resources/db/schema/orac_code/view/plugin_registry_v.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        package_spec = (
            (
                PROJECT_ROOT
                / "resources/db/schema/orac_code/package_spec/plugin_registry_api.sql"
            )
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertIn("ui_icon_class   varchar2(128 char)", table_sql)
        self.assertIn("ui_accent_class varchar2(128 char)", table_sql)
        self.assertNotIn("default 'fa fa-plug'", table_sql)
        self.assertIn("ui_icon_class", api_view_sql)
        self.assertIn("ui_accent_class", api_view_sql)
        self.assertIn("ui_icon_class", code_view_sql)
        self.assertIn("ui_accent_class", code_view_sql)
        self.assertIn("p_ui_icon_class", package_spec)
        self.assertIn("p_ui_accent_class", package_spec)

    def test_menu_view_lists_only_installed_enabled_apps(self) -> None:
        view_sql = (
            PROJECT_ROOT
            / "resources/db/schema/orac_code/view/plugin_apex_app_menu_v.sql"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "create or replace force view orac_code.plugin_apex_app_menu_v",
            view_sql,
        )
        self.assertIn("enabled = 'Y'", view_sql)
        self.assertIn("install_status = 'installed'", view_sql)
        self.assertIn("installed_app_id is not null", view_sql)
        self.assertIn("left join orac_code.plugin_registry_v plugin", view_sql)
        self.assertIn(
            "coalesce(app.icon, plugin.ui_icon_class, 'fa fa-plug') as icon",
            view_sql,
        )

    def test_visible_menu_view_generates_safe_card_links(self) -> None:
        view_sql = (
            (
                PROJECT_ROOT
                / "resources/db/schema/orac_code/view/plugin_apex_app_menu_visible_v.sql"
            )
            .read_text(encoding="utf-8")
            .lower()
        )

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
            (
                PROJECT_ROOT
                / "resources/db/schema/orac_code/view/plugin_apex_app_menu_visible_v.sql"
            )
            .read_text(encoding="utf-8")
            .lower()
        )
        package_spec = (
            (
                PROJECT_ROOT
                / "resources/db/schema/orac_code/package_spec/plugin_apex_app_auth_api.sql"
            )
            .read_text(encoding="utf-8")
            .lower()
        )
        package_body = (
            (
                PROJECT_ROOT
                / "resources/db/schema/orac_code/package_body/plugin_apex_app_auth_api.sql"
            )
            .read_text(encoding="utf-8")
            .lower()
        )

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
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1043.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertIn("wwv_flow_imp_shared.create_acl_role", export_sql)
        self.assertIn("p_static_id=>'administrator'", export_sql)
        self.assertIn("p_static_id=>'contributor'", export_sql)
        self.assertIn("p_static_id=>'reader'", export_sql)
        self.assertIn("p_users=>wwv_flow_t_varchar2('orac_admin')", export_sql)
        self.assertNotIn("apex_acl.", export_sql)

    def test_f1043_landing_page_exposes_plugin_service_operations(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1043.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        page_1 = _apex_page_sections(export_sql)[1]

        self.assertIn("p_id=>1", export_sql)
        self.assertIn("p_name=>'plugin operations'", export_sql)
        self.assertIn("p_plug_name=>'plugin operations heading'", page_1)
        self.assertIn("<h1>plugin operations</h1>", page_1)
        self.assertIn("p_plug_name=>'service state summary'", export_sql)
        self.assertIn("orac-ops-summary", page_1)
        for icon in (
            "fa fa-list",
            "fa fa-play",
            "fa fa-stop",
            "fa fa-exclamation-triangle",
            "fa fa-ban",
            "fa fa-sliders",
            "fa fa-key",
        ):
            self.assertIn(icon, page_1)
        self.assertIn("p_plug_name=>'plugin service status'", export_sql)
        self.assertIn("from orac_code.plugin_service_status_v", export_sql)
        self.assertIn("p_plug_source_type=>'native_ir'", export_sql)
        for column in (
            "plugin_id",
            "service_code",
            "service_name",
            "effective_policy",
            "current_state",
            "owner_id",
            "lease_active_yn",
            "lease_expires_on",
            "last_started_on",
            "last_heartbeat_on",
            "last_tick_on",
            "last_error_message",
            "row_version",
            "set_auto_action",
            "set_manual_action",
            "disable_action",
        ):
            self.assertIn(column, export_sql)
        self.assertNotIn("lease_token", export_sql)
        for token in (
            "p1_policy_plugin_id",
            "p1_policy_service_code",
            "p1_policy_row_version",
            "p1_policy_target",
            "set_service_policy_auto",
            "set_service_policy_manual",
            "set_service_policy_disabled",
            "orac_code.plugin_service_admin_api.set_policy",
            "p_row_version  => to_number(:p1_policy_row_version)",
        ):
            self.assertIn(token, page_1)
        self.assertIn("effective_policy_badge_class", page_1)
        self.assertIn("current_state_badge_class", page_1)
        self.assertIn("lease_active_badge_class", page_1)
        self.assertIn("dd-mon-yyyy hh24:mi:ss", page_1)
        self.assertIn(
            "p_report_columns=>'plugin_id:service_code:service_name:effective_policy:"
            "current_state:lease_active_yn:lease_expires_on:last_heartbeat_on:"
            "last_error_message:'",
            page_1,
        )
        self.assertIn("p_db_column_name=>'owner_id'", page_1)
        self.assertNotIn("ui_icon_class", page_1)
        self.assertNotIn("ui_accent_class", page_1)
        self.assertNotIn("p_icon_class_column_name=>'icon'", page_1)

    def test_f1043_plugin_navigation_page_preserves_launcher_cards(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1043.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        page_2 = _apex_page_sections(export_sql)[2]

        self.assertIn("p_id=>2", export_sql)
        self.assertIn("p_name=>'plugin navigation'", export_sql)
        self.assertIn("p_alias=>'plugin-navigation'", export_sql)
        self.assertIn("p_list_item_link_text=>'plugin navigation'", export_sql)
        self.assertIn(
            "p_list_item_link_target=>'f?p=&app_id.:2:&app_session.::&debug.:::'",
            export_sql,
        )
        self.assertIn("from orac_code.plugin_apex_app_menu_visible_v", export_sql)
        self.assertIn("p_icon_class_column_name=>'icon'", page_2)
        self.assertNotIn("metric_icon", page_2)

    def test_f1043_service_operations_do_not_query_plugin_owned_tables(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1043.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertNotIn("orac_dropbox", export_sql)
        self.assertNotRegex(export_sql, r"\bfrom\s+orac_(dropbox|ha)\.")
        self.assertNotRegex(export_sql, r"\bjoin\s+orac_(dropbox|ha)\.")

    def test_f1043_renders_plugin_apps_cards_from_visible_view(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1043.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

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
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1043.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertIn("p_layout_type=>'grid'", export_sql)
        self.assertIn("p_grid_column_count=>3", export_sql)
        self.assertIn("p_inline_css=>wwv_flow_string.join", export_sql)
        self.assertIn("grid-template-columns: repeat(auto-fit", export_sql)
        self.assertIn("26.25rem", export_sql)
        self.assertIn("max-width: 80.75rem", export_sql)
        self.assertIn("nth-child(6n+2)", export_sql)
        self.assertIn("orac-plugin-card-hub .a-cardview-iconwrap", export_sql)
        self.assertIn("orac-plugin-card-hub .a-cardview-headerbody", export_sql)
        self.assertIn("p_region_css_classes=>'orac-plugin-card-hub'", export_sql)
        self.assertIn("p_component_css_classes=>'orac-plugin-card-hub'", export_sql)
        self.assertIn("p_card_css_classes=>'orac-plugin-card'", export_sql)
        self.assertIn("p_icon_source_type=>'dynamic_class'", export_sql)
        self.assertIn("p_icon_position=>'top'", export_sql)
        self.assertIn("p_action_type=>'full_card'", export_sql)
        self.assertIn("p_link_target_type=>'redirect_url'", export_sql)
        self.assertIn("p_link_target=>'&card_link.'", export_sql)

    def test_f1043_synchronizes_theme_when_launched_from_orac_admin(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1043.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

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
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertIn("p_list_item_link_text=>'plugins'", export_sql)
        self.assertIn(
            "p_list_item_link_target=>'f?p=&app_id.:34:&session.::&debug.::::'",
            export_sql,
        )
        self.assertIn("p_list_item_icon=>'fa-plug'", export_sql)
        self.assertIn("p_list_item_current_for_pages=>'34,35,36'", export_sql)

    def test_f1042_plugins_page_uses_standard_card_hub(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

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
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertIn("p_list_item_link_text=>'plugin apps'", export_sql)
        self.assertIn(
            "p_list_item_link_target=>'f?p=1043:2:&app_session.:orac_theme_sync:&debug.:rp::'",
            export_sql,
        )
        self.assertIn("p_list_item_icon=>'fa-plug'", export_sql)
        self.assertIn(
            "p_list_text_01=>'launch installed plugin applications and administration surfaces.'",
            export_sql,
        )

    def test_f1042_plugins_page_links_to_plugin_app_maintenance(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertIn("p_list_item_link_text=>'manage plugin apps'", export_sql)
        self.assertIn(
            "p_list_item_link_target=>'f?p=&app_id.:35:&app_session.::&debug.:::'",
            export_sql,
        )
        self.assertIn("p_list_item_icon=>'fa-list-alt'", export_sql)
        self.assertIn("p_list_item_current_for_pages=>'35,36'", export_sql)

    def test_f1042_manage_plugin_apps_report_uses_code_view(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

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
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

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
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertIn("p_column_alias=>'edit_pref_id'", export_sql)
        self.assertIn(
            "p_column_link=>'f?p=&app_id.:6:&app_session.::&debug.:rp:p6_pref_id:#edit_pref_id#'",
            export_sql,
        )
        self.assertNotIn("p6_rowid", export_sql)
        self.assertNotIn("p6_rowid:#rowid#", export_sql)

    def test_f1042_user_preferences_form_uses_pref_id_primary_key(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertRegex(
            export_sql,
            r"(?s)p_name=>'p6_pref_id'.*?,p_is_primary_key=>true",
        )
        self.assertIn(",p_include_rowid_column=>false", export_sql)
        self.assertIn(",p_attribute_01=>'p6_pref_id,request'", export_sql)

    def test_f1042_user_preferences_report_filters_editable_preferences(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        display_view_sql = (
            (
                PROJECT_ROOT
                / "resources/db/schema/orac_code/view/user_preferences_display_v.sql"
            )
            .read_text(encoding="utf-8")
            .lower()
        )

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
            (
                PROJECT_ROOT
                / "resources/db/schema/orac_code/package_body/preference_lov_api.sql"
            )
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertIn("if l_pref_definition.lov_type is null then", package_body)
        self.assertIn("return l_rows.to_clob;", package_body)
        self.assertIn("else\n        return l_rows.to_clob;", package_body)

    def test_f1042_user_preferences_lov_items_are_render_guarded(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertIn("when :p6_control_type = ''select_list'' then", export_sql)
        self.assertIn(
            "when :p6_control_type in (''popup_lov'', ''select_one'')",
            export_sql,
        )
        self.assertIn("else", export_sql)
        self.assertIn("to_clob(json_array())", export_sql)

    def test_f1042_user_location_keeps_dedicated_search_path(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertIn("p_name=>'user location results'", export_sql)
        self.assertIn("user-location-results", export_sql)
        self.assertIn("p6_pref_key,p6_pref_value_search_term", export_sql)
        self.assertIn("and :p6_pref_key <> ''user_location'' then", export_sql)
        self.assertIn("$v(''p6_pref_key'') === ''user_location''", export_sql)
        self.assertNotIn("p_name=>'weather location results'", export_sql)
        self.assertNotIn("weather-location-results", export_sql)

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
            "user_location",
        )

        for pref_key in editable_runtime_preferences:
            with self.subTest(pref_key=pref_key):
                self.assertEqual(self._seeded_editable_flag(seed_sql, pref_key), "Y")
                self.assertEqual(self._seeded_active_flag(seed_sql, pref_key), "Y")

    def test_user_location_seed_retires_weather_location(self) -> None:
        seed_sql = (
            (
                PROJECT_ROOT
                / "resources/db/schema/orac_core/seed_data/prfdfn_preference_catalog.sql"
            )
            .read_text(encoding="utf-8")
            .lower()
        )
        seed_merge = seed_sql.split(") src", maxsplit=1)[0]
        user_location_row = self._seeded_row(seed_sql, "user_location")

        self.assertIn("'user location'", user_location_row)
        self.assertIn("'json'", user_location_row)
        self.assertIn("'select_one'", user_location_row)
        self.assertIn("p_pref_key      => 'user_location'", user_location_row)
        self.assertIn("'profile'", user_location_row)
        self.assertIn("location-aware features", user_location_row)
        self.assertNotIn("weather_location", seed_merge)
        self.assertIn(
            "delete from orac_core.user_preferences old_pref\n"
            " where old_pref.pref_key = 'weather_location'",
            seed_sql,
        )
        self.assertIn(
            "and new_pref.pref_key = 'user_location'",
            seed_sql,
        )
        self.assertIn(
            "update orac_core.user_preferences\n"
            "   set pref_key = 'user_location'\n"
            " where pref_key = 'weather_location'",
            seed_sql,
        )
        self.assertIn(
            "delete from orac_core.preference_definitions\n"
            " where pref_key = 'weather_location'",
            seed_sql,
        )
        self.assertLess(
            seed_sql.index("delete from orac_core.user_preferences old_pref"),
            seed_sql.index("update orac_core.user_preferences"),
        )
        self.assertLess(
            seed_sql.index("update orac_core.user_preferences"),
            seed_sql.index(
                "delete from orac_core.preference_definitions\n"
                " where pref_key = 'weather_location'"
            ),
        )

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
            (
                PROJECT_ROOT
                / "resources/db/schema/orac_core/seed_data/prfdfn_preference_catalog.sql"
            )
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertIn(
            "delete from orac_core.user_preferences\n where pref_key = 'email_opt_in'",
            seed_sql,
        )
        self.assertIn(
            "delete from orac_core.preference_definitions\n where pref_key = 'email_opt_in'",
            seed_sql,
        )
        self.assertLess(
            seed_sql.index(
                "delete from orac_core.user_preferences\n where pref_key = 'email_opt_in'"
            ),
            seed_sql.index(
                "delete from orac_core.preference_definitions\n where pref_key = 'email_opt_in'"
            ),
        )

    def test_orac_prefs_seed_filters_user_editable_defaults(self) -> None:
        package_body = (
            (
                PROJECT_ROOT
                / "resources/db/schema/orac_code/package_body/orac_prefs_seed.sql"
            )
            .read_text(encoding="utf-8")
            .lower()
        )

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
            (
                PROJECT_ROOT
                / "resources/db/schema/orac_code/package_spec/plugin_apex_app_admin_api.sql"
            )
            .read_text(encoding="utf-8")
            .lower()
        )
        package_body = (
            (
                PROJECT_ROOT
                / "resources/db/schema/orac_code/package_body/plugin_apex_app_admin_api.sql"
            )
            .read_text(encoding="utf-8")
            .lower()
        )

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

    def test_plugin_apex_exports_have_no_undefined_page_item_references(self) -> None:
        exports = sorted((PROJECT_ROOT / "plugins").glob("*/apex/f*.sql"))

        self.assertTrue(exports)
        for export_path in exports:
            with self.subTest(export_path=export_path.relative_to(PROJECT_ROOT)):
                export_sql = export_path.read_text(encoding="utf-8")
                page_sections = _apex_page_sections(export_sql)
                page_items = {
                    page_id: _apex_page_item_names(page_body, page_id)
                    for page_id, page_body in page_sections.items()
                }
                missing_references: list[str] = []
                cross_page_da_references: list[str] = []

                for source_page_id, page_body in page_sections.items():
                    for referenced_page_id, item_name in _apex_item_references(
                        page_body
                    ):
                        if item_name not in page_items.get(referenced_page_id, set()):
                            missing_references.append(
                                f"page {source_page_id} references undefined {item_name}"
                            )

                    for da_match in PAGE_DA_BLOCK_RE.finditer(page_body):
                        for referenced_page_id, item_name in _apex_item_references(
                            da_match.group(1)
                        ):
                            if referenced_page_id != source_page_id:
                                cross_page_da_references.append(
                                    f"page {source_page_id} dynamic action references "
                                    f"{item_name}"
                                )

                self.assertEqual(missing_references, [])
                self.assertEqual(cross_page_da_references, [])

    def test_home_assistant_uses_plugin_app_authorization(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "plugins/home_assistant/apex/f10010.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertNotIn("p_attribute_01=>'return true;'", export_sql)
        self.assertIn(
            "orac_code.plugin_apex_app_auth_api.has_required_role", export_sql
        )
        self.assertIn("''orac_admin''", export_sql)
        self.assertGreaterEqual(export_sql.count("p_required_role=>"), 3)

    def test_drop_box_declares_required_admin_apex_app(self) -> None:
        manifest = (
            (PROJECT_ROOT / "plugins/drop_box.json").read_text(encoding="utf-8").lower()
        )

        self.assertIn('"app_alias": "orac_dropbox_admin"', manifest)
        self.assertIn('"app_export": "apex/f10020.sql"', manifest)
        self.assertIn('"workspace": "orac"', manifest)
        self.assertIn('"parsing_schema": "orac_apx_pub"', manifest)
        self.assertIn('"application_id": 10020', manifest)
        self.assertIn('"install_required": true', manifest)
        self.assertIn('"orac_admin"', manifest)

    def test_drop_box_apex_app_uses_plugin_app_security_pattern(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "plugins/drop_box/apex/f10020.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertIn("p_default_application_id=>10020", export_sql)
        self.assertIn("drop box admin", export_sql)
        self.assertIn("p_cookie_name=>'&workspace_cookie.'", export_sql)
        self.assertIn("p_switch_in_session_yn=>'y'", export_sql)
        self.assertIn("p_rejoin_existing_sessions=>'y'", export_sql)
        self.assertIn(
            "orac_code.plugin_apex_app_auth_api.has_required_role", export_sql
        )
        self.assertIn("''orac_admin''", export_sql)
        self.assertIn(":request = ''orac_theme_sync''", export_sql)
        self.assertIn("s.application_id = 1042", export_sql)
        self.assertIn("s.application_id = :app_id", export_sql)
        self.assertGreaterEqual(export_sql.count("p_required_role=>"), 3)

    def test_drop_box_apex_app_uses_admin_views_and_api_only(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "plugins/drop_box/apex/f10020.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertIn("create drop location", export_sql)
        self.assertIn("about drop box locations", export_sql)
        self.assertIn("drop box locations are folders watched by orac", export_sql)
        self.assertIn("p_plug_source_type=>'native_ir'", export_sql)
        self.assertIn("wwv_flow_imp_page.create_worksheet", export_sql)
        self.assertIn("orac_dropbox.drop_location_admin_v", export_sql)
        self.assertIn("orac_dropbox.drop_location_summary_admin_v", export_sql)
        self.assertIn("orac_dropbox.drop_job_admin_v", export_sql)
        self.assertIn("orac_dropbox.drop_job_event_admin_v", export_sql)
        self.assertIn("orac_dropbox.drop_processing_profile_lov_v", export_sql)
        self.assertIn("orac_dropbox.drop_box_admin_api.create_location", export_sql)
        self.assertIn("orac_dropbox.drop_box_admin_api.update_location", export_sql)
        self.assertIn("orac_dropbox.drop_box_admin_api.set_enabled", export_sql)
        self.assertIn("orac_dropbox.drop_box_admin_api.delete_location", export_sql)
        self.assertIn("orac_code.plugin_lov_v", export_sql)
        self.assertIn("total_job_count", export_sql)
        self.assertIn("p_name=>'drop location form'", export_sql)
        self.assertIn("p_name=>'drop location detail'", export_sql)
        self.assertIn("p_name=>'job detail'", export_sql)
        self.assertIn("p_name=>'activity'", export_sql)
        self.assertIn("p_list_item_link_text=>'activity'", export_sql)
        self.assertIn(
            'p_column_linktext=>\'<span role="img" aria-label="edit"', export_sql
        )
        self.assertIn("p_column_linktext=>'view jobs'", export_sql)
        self.assertIn("view_jobs_location_id", export_sql)
        self.assertIn("toggle_location", export_sql)
        self.assertIn("p2_target_plugin_key", export_sql)
        self.assertIn("p2_target_project_key", export_sql)
        self.assertIn("p_name=>'dialog closed'", export_sql)
        self.assertIn("p_bind_event_type=>'apexafterclosedialog'", export_sql)
        self.assertIn("p_action=>'native_refresh'", export_sql)
        self.assertNotRegex(
            export_sql,
            r"\b(insert|update|delete|merge)\s+(into\s+)?orac_dropbox\.",
        )
        self.assertNotRegex(
            export_sql,
            r"orac_dropbox\.drop_[a-z0-9_]+\.[a-z0-9_]+%type",
        )
        self.assertNotIn("orac_core.", export_sql)
        self.assertNotIn("orac_api.", export_sql)

    def test_drop_box_page_two_form_layout_and_switches(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "plugins/drop_box/apex/f10020.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        page_two = export_sql[
            export_sql.index(
                "prompt --application/pages/page_00002"
            ) : export_sql.index("prompt --application/pages/page_00003")
        ]

        self.assertIn("p_page_mode=>'modal'", page_two)
        self.assertIn("p_dialog_chained=>'n'", page_two)
        self.assertIn("p_dialog_resizable=>'y'", page_two)

        for region in (
            "basic details",
            "target / routing",
            "scanner rules",
            "processing instructions",
            "post-processing / future use",
            "audit / metadata",
        ):
            self.assertIn(f"p_plug_name=>'{region}'", page_two)

        ordered_tokens = (
            "p_name=>'p2_location_code'",
            "p_name=>'p2_display_name'",
            "p_name=>'p2_enabled_yn'",
            "p_name=>'p2_path'",
            "p_name=>'p2_target_scope_type'",
            "p_name=>'p2_target_plugin_key'",
            "p_name=>'p2_target_project_key'",
            "p_name=>'p2_processing_profile'",
            "p_name=>'p2_allowed_extensions'",
            "p_name=>'p2_recursive_yn'",
            "p_name=>'p2_ignore_patterns'",
            "p_name=>'p2_max_file_size_mb'",
            "p_name=>'p2_stability_seconds'",
            "p_name=>'p2_processing_instruction'",
            "p_name=>'p2_move_processed_yn'",
            "p_name=>'p2_processed_path'",
            "p_name=>'p2_failed_path'",
        )
        positions = [page_two.index(token) for token in ordered_tokens]
        self.assertEqual(positions, sorted(positions))

        for item in ("p2_enabled_yn", "p2_recursive_yn", "p2_move_processed_yn"):
            item_start = page_two.index(f"p_name=>'{item}'")
            item_end = page_two.find(
                "wwv_flow_imp_page.create_page_item", item_start + 1
            )
            item_text = page_two[
                item_start : item_end if item_end != -1 else len(page_two)
            ]
            self.assertIn("p_display_as=>'native_yes_no'", item_text)
            self.assertIn("'use_defaults', 'y'", item_text)

        self.assertIn("p_cHeight=>12".lower(), page_two)
        profile_start = page_two.index("p_name=>'p2_processing_profile'")
        profile_end = page_two.find(
            "wwv_flow_imp_page.create_page_item", profile_start + 1
        )
        profile_text = page_two[
            profile_start : profile_end if profile_end != -1 else len(page_two)
        ]
        self.assertIn("p_display_as=>'native_select_list'", profile_text)
        self.assertIn("drop_processing_profile_lov_v", profile_text)
        self.assertIn("display_label d", profile_text)
        self.assertIn("profile_code r", profile_text)
        self.assertNotIn("p_display_as=>'native_text_field'", profile_text)
        self.assertIn("named ingestion recipe", profile_text)
        self.assertNotIn("p_name=>'p2_profile_description'", page_two)
        self.assertNotIn("p_name=>'p2_profile_default_instruction'", page_two)
        self.assertIn("p_plug_name=>'audit / metadata'", page_two)
        self.assertIn("p_plug_source_type=>'native_dynamic_content'", page_two)
        self.assertIn("created at", page_two)
        self.assertIn("updated at", page_two)
        self.assertIn("row version", page_two)
        self.assertNotIn("p_name=>'p2_created_on'", page_two)
        self.assertNotIn("p_name=>'p2_updated_on'", page_two)
        self.assertNotIn("p_name=>'p2_row_version_display'", page_two)
        self.assertNotIn(":p2_created_on", page_two)
        self.assertNotIn(":p2_updated_on", page_two)
        self.assertNotIn(":p2_row_version_display", page_two)
        page_two_items = _apex_page_item_names(page_two, 2)
        self.assertNotIn("P2_CREATED_ON", page_two_items)
        self.assertNotIn("P2_UPDATED_ON", page_two_items)
        self.assertNotIn("P2_ROW_VERSION_DISPLAY", page_two_items)

        load_process_start = page_two.index("p_process_name=>'load drop location'")
        load_process_end = page_two.find(
            "wwv_flow_imp_page.create_page_process",
            load_process_start + 1,
        )
        load_process_text = page_two[
            load_process_start : (
                load_process_end if load_process_end != -1 else len(page_two)
            )
        ]
        load_process_page_two_refs = {
            item_name
            for referenced_page_id, item_name in _apex_item_references(
                load_process_text
            )
            if referenced_page_id == 2
        }
        self.assertLessEqual(load_process_page_two_refs, page_two_items)

    def test_drop_box_page_two_submit_boundaries(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "plugins/drop_box/apex/f10020.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        page_two = export_sql[
            export_sql.index(
                "prompt --application/pages/page_00002"
            ) : export_sql.index("prompt --application/pages/page_00003")
        ]

        self.assertIn("p_button_name=>'cancel'", page_two)
        self.assertIn("p_button_action=>'redirect_page'", page_two)
        self.assertIn("p_button_position=>'close'", page_two)
        self.assertIn("p_button_execute_validations=>'n'", page_two)
        self.assertIn("p_button_name=>'save'", page_two)
        self.assertIn("p_button_action=>'submit'", page_two)
        self.assertIn("p_button_position=>'next'", page_two)
        self.assertIn("p_button_name=>'delete'", page_two)
        self.assertIn("p_button_position=>'delete'", page_two)
        self.assertIn("t-button--danger", page_two)
        self.assertIn("p_confirm_message=>'delete this drop location?", page_two)
        self.assertIn("p_confirm_style=>'danger'", page_two)
        self.assertIn("p_button_condition=>'p2_drop_location_id'", page_two)
        self.assertIn("p_button_condition_type=>'item_is_not_null'", page_two)
        self.assertEqual(
            page_two.count("orac_dropbox.drop_box_admin_api.create_location"),
            1,
        )
        self.assertEqual(
            page_two.count("orac_dropbox.drop_box_admin_api.update_location"),
            1,
        )
        self.assertEqual(
            page_two.count("orac_dropbox.drop_box_admin_api.delete_location"),
            1,
        )
        self.assertIn("p_process_when=>'save'", page_two)
        self.assertIn("p_process_when_type=>'request_in_condition'", page_two)
        self.assertIn("p_process_name=>'delete drop location'", page_two)
        self.assertIn("p_process_when=>'delete'", page_two)
        self.assertIn("p_process_type=>'native_close_window'", page_two)
        self.assertIn("p_process_name=>'close dialog after save'", page_two)
        self.assertIn("p_process_name=>'close dialog after delete'", page_two)
        self.assertIn("p_attribute_01=>'p2_drop_location_id,request'", page_two)
        self.assertNotIn("p_branch_type=>'redirect_url'", page_two)
        self.assertNotIn("p_branch_name=>'after save'", page_two)
        self.assertNotIn("p_branch_name=>'after delete'", page_two)
        self.assertNotIn("p3_drop_location_id:&p2_drop_location_id", page_two)
        self.assertIn("l_target_key varchar2(200 char)", page_two)
        self.assertNotIn("orac_dropbox.drop_location.target_scope_key%type", page_two)
        self.assertNotIn("native_form_dml", page_two)
        self.assertNotIn("automatic row processing", page_two)
        self.assertNotRegex(
            page_two,
            r"\b(insert|update|delete|merge)\s+(into\s+)?orac_dropbox\.",
        )

    def test_drop_box_page_two_toggles_plugin_target_by_scope(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "plugins/drop_box/apex/f10020.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        page_two = export_sql[
            export_sql.index(
                "prompt --application/pages/page_00002"
            ) : export_sql.index("prompt --application/pages/page_00003")
        ]

        self.assertIn("p_name=>'toggle plugin target'", page_two)
        self.assertIn("p_triggering_element=>'p2_target_scope_type'", page_two)
        self.assertIn("p_execute_on_page_init=>'y'", page_two)
        self.assertIn("p_action=>'native_javascript_code'", page_two)
        self.assertIn("$v(''p2_target_scope_type'') === ''plugin''", page_two)
        self.assertIn("apex.item(''p2_target_plugin_key'').enable()", page_two)
        self.assertIn("apex.item(''p2_target_plugin_key'').disable()", page_two)
        self.assertNotIn("p2_target_plugin_key').setvalue", page_two)

    def test_drop_box_page_two_profile_lov_and_field_behaviour(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "plugins/drop_box/apex/f10020.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        page_two = export_sql[
            export_sql.index(
                "prompt --application/pages/page_00002"
            ) : export_sql.index("prompt --application/pages/page_00003")
        ]

        self.assertNotIn("p_name=>'show profile description'", page_two)
        self.assertNotIn("p_name=>'show profile default instruction'", page_two)
        self.assertNotIn("p_affected_elements=>'p2_profile_description'", page_two)
        self.assertNotIn(
            "p_affected_elements=>'p2_profile_default_instruction'", page_two
        )
        self.assertIn("from orac_dropbox.drop_processing_profile_lov_v", page_two)

        self.assertIn("p_name=>'normalize case fields'", page_two)
        self.assertIn(
            "p_triggering_element=>'p2_location_code,p2_target_project_key,p2_allowed_extensions'",
            page_two,
        )
        self.assertIn(
            "apex.item(itemname).setvalue(transformvalue(value), null, true)", page_two
        )
        self.assertIn(
            "p2_location_code'', function(value) { return value.touppercase(); }",
            page_two,
        )
        self.assertIn(
            "p2_target_project_key'', function(value) { return value.touppercase(); }",
            page_two,
        )
        self.assertIn(
            "p2_allowed_extensions'', function(value) { return value.tolowercase(); }",
            page_two,
        )

        self.assertIn("p_name=>'toggle processed path'", page_two)
        self.assertIn("p_triggering_element=>'p2_move_processed_yn'", page_two)
        self.assertIn("$v(''p2_move_processed_yn'') === ''y''", page_two)
        self.assertIn("apex.item(''p2_processed_path'').enable()", page_two)
        self.assertIn("apex.item(''p2_processed_path'').disable()", page_two)
        self.assertNotIn("apex.item(''p2_failed_path'').disable()", page_two)

    def test_drop_box_activity_page_uses_persisted_event_view(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "plugins/drop_box/apex/f10020.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        activity_page = export_sql[
            export_sql.index(
                "prompt --application/pages/page_00005"
            ) : export_sql.index("prompt --application/pages/page_09999")
        ]

        self.assertIn("p_name=>'activity'", activity_page)
        self.assertIn("from orac_dropbox.drop_job_event_admin_v evt", activity_page)
        self.assertIn("join orac_dropbox.drop_job_admin_v job", activity_page)
        self.assertIn("on job.drop_job_id = evt.drop_job_id", activity_page)
        for token in (
            "event_ts",
            "location_code",
            "location_display_name",
            "drop_job_id",
            "source_filename",
            "source_path",
            "event_type",
            "event_message",
        ):
            self.assertIn(token, activity_page)
        self.assertNotRegex(
            activity_page,
            r"\b(insert|update|delete|merge)\s+(into\s+)?orac_dropbox\.",
        )

    def test_plugin_lov_view_is_narrow_and_apex_granted(self) -> None:
        view_sql = (
            (PROJECT_ROOT / "resources/db/schema/orac_code/view/plugin_lov_v.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        grants_sql = (
            (
                PROJECT_ROOT
                / "resources/db/schema/orac_code/grant/orac_code_consumer_view_access.sql"
            )
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertIn("create or replace force view orac_code.plugin_lov_v", view_sql)
        self.assertIn("from orac_code.plugin_registry_v", view_sql)
        self.assertNotIn("from orac_api.plugin_registry_v", view_sql)
        self.assertIn("plugin_id", view_sql)
        self.assertIn("display_label", view_sql)
        self.assertIn("plugin_version", view_sql)
        self.assertIn("install_status", view_sql)
        self.assertIn("readiness_status", view_sql)
        self.assertIn("enabled", view_sql)
        self.assertIn("enabled = 'y'", view_sql)
        self.assertIn("install_status = 'success'", view_sql)
        self.assertIn("configuration_status in ('success', 'not_required')", view_sql)
        self.assertIn("dependency_status in ('success', 'not_required')", view_sql)
        self.assertIn("'already_deployed'", view_sql)
        self.assertIn("'optional_missing'", view_sql)
        self.assertIn("readiness_status = 'success'", view_sql)
        self.assertNotIn("install_status = 'installed'", view_sql)
        self.assertNotIn("manifest_hash", view_sql)
        self.assertNotIn("package_hash", view_sql)
        self.assertNotIn("installed_path", view_sql)
        self.assertNotIn("config_path", view_sql)
        self.assertIn(
            "grant read on orac_code.plugin_lov_v to orac_apx_pub;", grants_sql
        )
        self.assertNotIn(
            "grant read on orac_code.plugin_registry_v to orac_apx_pub", grants_sql
        )

    def test_home_assistant_synchronizes_theme_when_launched_from_plugin_hub(
        self,
    ) -> None:
        export_sql = (
            (PROJECT_ROOT / "plugins/home_assistant/apex/f10010.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

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

    def test_plugin_docs_explain_manifest_icon_configuration(self) -> None:
        docs = (PROJECT_ROOT / "docs/plugins.md").read_text(encoding="utf-8").lower()

        self.assertIn("ui.icon_class", docs)
        self.assertIn("apex_apps[].icon_class", docs)
        self.assertIn("legacy `apex_apps[].icon`", docs)
        self.assertIn("fa-folder-open", docs)
        self.assertIn("fa fa-folder-open", docs)
        self.assertIn("fa fa-[a-z0-9-]+", docs)
        self.assertIn("fa fa-plug", docs)
        self.assertIn("registry value\nas `null`", docs)
        self.assertIn("plugin manifest icons must not influence", docs)
        self.assertIn("operational dashboard sql", docs)
        self.assertIn("ui.accent_class", docs)
        self.assertIn("fixed safe allowlist", docs)

    def test_home_assistant_status_dashboard_is_read_only(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "plugins/home_assistant/apex/f10010.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

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
        self.assertIn(
            "grant execute on orac_code.plugin_service_admin_api to orac_apx_pub;",
            package_grants,
        )
        self.assertNotIn(
            "grant execute on orac_code.plugin_service_api to orac_apx_pub;",
            package_grants,
        )
        self.assertIn(
            "grant read on orac_code.plugin_apex_app_menu_v to orac;", view_grants
        )
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
        self.assertIn(
            "grant read on orac_code.plugin_service_status_v to orac_apx_pub;",
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
