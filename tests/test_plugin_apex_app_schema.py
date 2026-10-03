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
PAGE_BUTTON_BLOCK_RE = re.compile(
    r"wwv_flow_imp_page\.create_page_button\((.*?)\);",
    re.IGNORECASE | re.DOTALL,
)
WORKSHEET_COLUMN_BLOCK_RE = re.compile(
    r"wwv_flow_imp_page\.create_worksheet_column\((.*?)\);",
    re.IGNORECASE | re.DOTALL,
)
PAGE_DA_BLOCK_RE = re.compile(
    r"wwv_flow_imp_page\.create_page_da_(?:event|action)\((.*?)\);",
    re.IGNORECASE | re.DOTALL,
)
LIST_ITEM_BLOCK_RE = re.compile(
    r"wwv_flow_imp_shared\.create_list_item\((.*?)\);",
    re.IGNORECASE | re.DOTALL,
)
PAGE_ITEM_NAME_RE = re.compile(r"p_name=>'([^']+)'", re.IGNORECASE)
PAGE_ITEM_REF_RE = re.compile(r"(?<![A-Z0-9_])P([0-9]+)_[A-Z0-9_]+", re.IGNORECASE)

DROP_BOX_STATUSES = (
    "queued",
    "processing",
    "handed_off",
    "completed",
    "failed",
    "quarantined",
    "deferred_prerequisite",
    "conversion_retry_wait",
    "skipped_duplicate",
    "skipped_disallowed_type",
    "skipped_too_large",
)


def _expected_lifecycle_bucket(
    drop_box_status: str,
    *,
    request_id_present: bool,
    core_row_present: bool,
    core_status: str | None,
    searchable: str | None,
) -> str:
    """Return the approved exhaustive lifecycle bucket for a test row."""
    if drop_box_status.startswith("skipped_"):
        return "SKIPPED"
    if drop_box_status in {"failed", "quarantined"}:
        return "FAILED_ATTENTION"
    if drop_box_status == "deferred_prerequisite":
        return "PREREQUISITE_DEFERRED"
    if drop_box_status == "conversion_retry_wait":
        return "CONVERSION_RETRY"
    if drop_box_status in {"queued", "processing"}:
        return "AWAITING_HANDOFF"
    if not request_id_present or not core_row_present:
        return "FAILED_ATTENTION"
    if searchable == "Y":
        return "SEARCHABLE"
    if core_status in {"QUEUED", "PROCESSING", "RETRY_WAIT"}:
        return "CORE_IN_PROGRESS"
    return "FAILED_ATTENTION"


def _apex_page_sections(export_sql: str) -> dict[int, str]:
    """Return APEX export page bodies keyed by page id."""
    return {
        int(match.group(1)): match.group(2)
        for match in PAGE_SECTION_RE.finditer(export_sql)
    }


def _apex_component_block(pattern: re.Pattern[str], page_sql: str, marker: str) -> str:
    """Return the APEX component block containing the requested marker."""
    for match in pattern.finditer(page_sql):
        component_block = match.group(1)
        if marker in component_block:
            return component_block
    raise AssertionError(f"APEX component marker not found: {marker}")


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


def _apex_prompt_block(export_sql: str, prompt: str) -> str:
    """Return a shared-component export block that starts with a prompt line."""
    start = export_sql.index(prompt.lower())
    end = export_sql.index("end;\n/", start) + len("end;\n/")
    return export_sql[start:end]


class PluginApexAppSchemaTests(unittest.TestCase):
    """Verify static schema assets for plugin-supplied APEX app registration."""

    def test_plugin_execution_authorization_is_uncached_and_checks_lifecycle(
        self,
    ) -> None:
        body = (
            PROJECT_ROOT
            / "resources/db/schema/orac_code/package_body/plugin_apex_app_auth_api.sql"
        ).read_text()
        availability = body.split("function plugin_is_available(", 1)[1].split(
            "end plugin_is_available;", 1
        )[0]
        for predicate in (
            "plugin.removal_id is null",
            "plugin.enabled = 'Y'",
            "app.installed_app_id = p_application_id",
            "plugin.readiness_status = 'success'",
            "return 0;",
        ):
            self.assertIn(predicate, availability)
        for plugin, filename in (
            ("home_assistant", "f10010.sql"),
            ("drop_box", "f10020.sql"),
        ):
            export = (PROJECT_ROOT / "plugins" / plugin / "apex" / filename).read_text()
            self.assertIn(f"plugin_is_available(''{plugin}'', :APP_ID)", export)
            self.assertIn(",p_caching=>'NOCACHE'", export)
        core = (APEX_ROOT / "orac_apps/f1043.sql").read_text()
        self.assertNotIn("plugin_is_available(", core)

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
        self.assertIn("join orac_code.plugin_registry_v plugin", view_sql)
        self.assertNotIn("left join orac_code.plugin_registry_v plugin", view_sql)
        self.assertIn("plugin.enabled = 'Y'", view_sql)
        self.assertIn("plugin.removal_id is null", view_sql)
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
        self.assertIn("orac_code.apex_return_nav_api.launch_url", view_sql)
        self.assertIn("installed_app_id", view_sql)
        self.assertIn("coalesce(entry_page_id, 1)", view_sql)
        self.assertIn("p_target_app_id  => installed_app_id", view_sql)
        self.assertIn("p_target_page_id => coalesce(entry_page_id, 1)", view_sql)
        self.assertIn("p_request        => 'orac_theme_sync'", view_sql)
        self.assertIn("p_clear_cache    => 'rp'", view_sql)
        self.assertIn("card_link", view_sql)
        self.assertNotIn("apex_util.prepare_url", view_sql)

    def test_apex_return_nav_api_validates_and_derives_navigation(self) -> None:
        package_spec = (
            (
                PROJECT_ROOT
                / "resources/db/schema/orac_code/package_spec/apex_return_nav_api.sql"
            )
            .read_text(encoding="utf-8")
            .lower()
        )
        package_body = (
            (
                PROJECT_ROOT
                / "resources/db/schema/orac_code/package_body/apex_return_nav_api.sql"
            )
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertIn(
            "create or replace package orac_code.apex_return_nav_api", package_spec
        )
        self.assertIn("c_max_depth constant pls_integer := 5", package_spec)
        self.assertIn("normalize_stack", package_spec)
        self.assertIn("launch_url", package_spec)
        self.assertIn("return_label", package_spec)
        self.assertIn("return_url", package_spec)
        self.assertNotIn("p_return_url", package_spec)
        self.assertNotIn("p_return_label", package_spec)

        self.assertIn(
            "c_stack_item_name constant varchar2(30 char) := 'orac_nav_stack'",
            package_body,
        )
        self.assertIn("regexp_like(l_source", package_body)
        self.assertIn("[0-9]{1,10}\\.[0-9]{1,10}", package_body)
        self.assertIn("is_valid_frame", package_body)
        self.assertIn("p_app_id = c_admin_app_id", package_body)
        self.assertIn(
            "p_app_id = c_plugin_app_id and p_page_id in (1, 2, 3, 4)",
            package_body,
        )
        self.assertIn("from orac_code.plugin_apex_app_menu_v", package_body)
        self.assertIn("apex_util.prepare_url", package_body)
        self.assertIn("p_checksum_type => 'session'", package_body)
        self.assertIn("return 'orac admin'", package_body)
        self.assertIn("return 'plugin operations'", package_body)
        self.assertIn("return 'plugin navigation'", package_body)
        self.assertIn("return 'manage plugin apps'", package_body)
        self.assertIn("return 'plugin app'", package_body)
        self.assertIn(
            "coalesce(menu.card_title, menu.label, menu.app_alias)", package_body
        )
        self.assertIn("p_count > c_max_depth", package_body)
        self.assertNotIn("http://", package_body)
        self.assertNotIn("https://", package_body)

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

    def test_f1043_service_plugin_link_requires_one_visible_app(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1043.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        page_one = _apex_page_sections(export_sql)[1]
        plugin_column = _apex_component_block(
            WORKSHEET_COLUMN_BLOCK_RE,
            page_one,
            "p_db_column_name=>'plugin_id'",
        )
        link_column = _apex_component_block(
            WORKSHEET_COLUMN_BLOCK_RE,
            page_one,
            "p_db_column_name=>'plugin_app_link'",
        )

        self.assertIn("from orac_code.plugin_apex_app_menu_visible_v", page_one)
        self.assertIn("from orac_code.plugin_service_status_v", page_one)
        self.assertIn("when app.visible_app_count = 1", page_one)
        self.assertIn("and app.card_link is not null then app.card_link", page_one)
        self.assertIn("end as plugin_app_link", page_one)
        self.assertIn("left join visible_apps app", page_one)
        self.assertIn("and app.app_rank = 1", page_one)
        self.assertNotIn("'orac_core'", page_one)

        self.assertIn(
            "p_column_html_expression=>'{if ?plugin_app_link/}"
            '<a href="#plugin_app_link!attr#">#plugin_id!html#</a>'
            "{else/}#plugin_id!html#{endif/}'",
            plugin_column,
        )
        self.assertNotIn("p_column_link=>", plugin_column)
        self.assertNotIn("p_column_linktext=>", plugin_column)
        self.assertIn("p_display_text_as=>'without_modification'", plugin_column)
        self.assertIn("p_display_text_as=>'hidden_escape_sc'", link_column)

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
        self.assertIn("plugin navigation", export_sql)
        self.assertIn("plugin operations", export_sql)
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
        self.assertIn("p_plug_source_type=>'native_cards'", export_sql)
        self.assertIn("from orac_code.plugin_apex_app_menu_visible_v", export_sql)
        self.assertNotIn("orac_core.plugin_apex_apps", export_sql)
        self.assertIn("p_link_target=>'&card_link.'", export_sql)
        self.assertIn("p_link_target_type=>'redirect_url'", export_sql)
        self.assertIn("p_title_column_name=>'card_title'", export_sql)
        self.assertIn("p_sub_title_column_name=>'card_subtitle'", export_sql)
        self.assertIn("p_body_column_name=>'description'", export_sql)
        self.assertIn("p_icon_class_column_name=>'icon'", export_sql)

    def test_f1043_plugin_apps_cards_use_data_driven_navigation(self) -> None:
        """Verify card navigation behaviour without fixing card presentation."""
        export_sql = (
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1043.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

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

    def test_f1043_is_branded_as_plugin_control(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1043.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertIn("prompt application 1043 - plugin control", export_sql)
        self.assertIn("--   name:            plugin control", export_sql)
        self.assertIn(
            "p_name=>nvl(wwv_flow_application_install.get_application_name,"
            "'plugin control')",
            export_sql,
        )
        self.assertIn("p_logo_text=>'plugin control'", export_sql)
        self.assertIn("p_substitution_value_01=>'plugin control'", export_sql)
        self.assertIn("p_step_title=>'plugin control - log in'", export_sql)
        self.assertIn("p_plug_name=>'plugin control'", export_sql)
        self.assertIn(
            "p_alias=>nvl(wwv_flow_application_install.get_application_alias,'plugin-apps1043')",
            export_sql,
        )

    def test_f1042_removes_dedicated_plugins_navigation(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        pages = _apex_page_sections(export_sql)

        self.assertNotIn("p_list_item_link_text=>'plugins'", export_sql)
        self.assertNotIn("p_name=>'plugins cards'", export_sql)
        self.assertNotIn("p_process_name=>'launch plugin navigation'", export_sql)
        self.assertNotIn("p_short_name=>'plugins'", export_sql)
        self.assertNotIn("p_short_name=>'manage plugin apps'", export_sql)
        self.assertNotIn("p_short_name=>'plugin app'", export_sql)
        self.assertNotIn(34, pages)
        self.assertNotIn(35, pages)
        self.assertNotIn(36, pages)

    def test_f1042_orac_admin_card_launches_plugin_control(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertIn("p_name=>'orac admin cards'", export_sql)
        self.assertIn("p_list_item_link_text=>'plugin control'", export_sql)
        self.assertIn(
            "p_list_item_link_target=>'&orac_launch_plugin_control_url!raw.'",
            export_sql,
        )
        self.assertIn("p_list_item_icon=>'fa fa-plug'", export_sql)
        self.assertIn(
            "p_list_text_01=>'monitor plugin services, manage registered applications "
            "and launch plugin administration tools.'",
            export_sql,
        )
        self.assertIn("p_name=>'orac_launch_plugin_control_url'", export_sql)
        self.assertIn(
            ":orac_launch_plugin_control_url := "
            "orac_code.apex_return_nav_api.launch_url(1043, 1, "
            "''orac_theme_sync'', ''rp'')",
            export_sql,
        )
        self.assertNotIn("orac_launch_plugin_navigation_url", export_sql)
        self.assertNotIn("orac_launch_plugin_operations_url", export_sql)

    def test_plugin_app_scaffold_export_defines_standard_cards(self) -> None:
        scaffold_path = PROJECT_ROOT / "resources/db/apex/orac_apps/f10042.sql"
        self.assertTrue(scaffold_path.is_file())

        export_sql = scaffold_path.read_text(encoding="utf-8").lower()
        page_one = _apex_page_sections(export_sql)[1]

        self.assertIn("prompt application 10042 - plugin app scaffold", export_sql)
        self.assertIn("p_default_application_id=>10042", export_sql)
        self.assertIn("p_default_owner=>'orac_apx_pub'", export_sql)
        self.assertIn(
            "p_name=>nvl(wwv_flow_application_install.get_application_name,"
            "'plugin app scaffold')",
            export_sql,
        )
        self.assertIn(
            "p_alias=>nvl(wwv_flow_application_install.get_application_alias,"
            "'plugin-app-scaffold')",
            export_sql,
        )
        self.assertIn("p_theme_id=>42", export_sql)
        self.assertIn("p_scheme_type=>'native_apex_accounts'", export_sql)
        self.assertNotIn("orac_ha.", export_sql)

        self.assertIn("p_plug_name=>'scaffold cards'", page_one)
        self.assertIn("p_region_css_classes=>'orac-plugin-card-hub'", page_one)
        self.assertIn("p_plug_source_type=>'native_cards'", page_one)
        self.assertIn("p_component_css_classes=>'orac-plugin-card-hub'", page_one)
        self.assertIn("p_card_css_classes=>'orac-plugin-card'", page_one)
        self.assertIn("p_action_type=>'full_card'", page_one)
        self.assertIn("p_link_target=>'&card_link.'", page_one)
        self.assertEqual(3, page_one.count(" card_id'"))
        self.assertIn("''example console'' card_title", page_one)
        self.assertIn("''example setup'' card_title", page_one)
        self.assertIn("''example activity'' card_title", page_one)
        self.assertIn("p_icon_source_type=>'dynamic_class'", page_one)
        self.assertIn("p_icon_position=>'top'", page_one)

    def test_managed_apex_apps_define_cross_app_return_navigation(self) -> None:
        managed_exports = (
            PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql",
            PROJECT_ROOT / "resources/db/apex/orac_apps/f1043.sql",
            PROJECT_ROOT / "resources/db/apex/orac_apps/f10042.sql",
            PROJECT_ROOT / "plugins/home_assistant/apex/f10010.sql",
            PROJECT_ROOT / "plugins/drop_box/apex/f10020.sql",
        )
        required_items = (
            "orac_nav_stack",
            "orac_return_depth",
            "orac_return_label_1",
            "orac_return_label_2",
            "orac_return_label_3",
            "orac_return_label_4",
            "orac_return_label_5",
            "orac_return_url_1",
            "orac_return_url_2",
            "orac_return_url_3",
            "orac_return_url_4",
            "orac_return_url_5",
        )

        for export_path in managed_exports:
            export_sql = export_path.read_text(encoding="utf-8").lower()
            with self.subTest(export=export_path.name):
                nav_bar = _apex_prompt_block(
                    export_sql,
                    "prompt --application/shared_components/navigation/lists/navigation_bar",
                )
                return_list = _apex_prompt_block(
                    export_sql,
                    "prompt --application/shared_components/navigation/lists/cross_app_return_navigation",
                )
                application_processes = _apex_prompt_block(
                    export_sql,
                    "prompt --application/shared_components/logic/application_processes",
                )
                page_0 = _apex_page_sections(export_sql)[0]
                list_items = [
                    block_match.group(1)
                    for block_match in LIST_ITEM_BLOCK_RE.finditer(return_list)
                ]
                more_items = [
                    item
                    for item in list_items
                    if "p_list_item_link_text=>'more'" in item
                ]

                for item_name in required_items:
                    self.assertIn(f"p_name=>'{item_name.upper()}'".lower(), export_sql)

                self.assertIn(
                    "prepare cross-app return navigation", application_processes
                )
                self.assertIn(
                    "wwv_flow_imp_shared.create_flow_process", application_processes
                )
                self.assertIn("p_process_point=>'before_header'", application_processes)
                self.assertIn("p_process_type=>'native_plsql'", application_processes)
                self.assertIn(
                    ":orac_nav_stack := orac_code.apex_return_nav_api.normalize_stack(:orac_nav_stack);",
                    application_processes,
                )
                self.assertIn(
                    ":orac_return_label_1 := orac_code.apex_return_nav_api.return_label(1, :orac_nav_stack);",
                    application_processes,
                )
                self.assertIn(
                    ":orac_return_url_1 := orac_code.apex_return_nav_api.return_url(1, :orac_nav_stack);",
                    application_processes,
                )
                self.assertNotIn(
                    "p_process_name=>'prepare cross-app return navigation'", page_0
                )

                self.assertNotIn("return to &orac_return_label_", nav_bar)
                self.assertIn("p_name=>'cross-app return navigation'", return_list)
                self.assertIn(
                    "p_list_item_link_text=>'return to &orac_return_label_1.'",
                    return_list,
                )
                self.assertIn(
                    "p_list_item_link_target=>'&orac_return_url_1!raw.'", return_list
                )
                self.assertIn(
                    "p_list_item_disp_condition=>':orac_return_depth > 0 and "
                    ":orac_return_label_1 is not null and :orac_return_url_1 is not null'",
                    return_list,
                )
                self.assertEqual(1, len(more_items))
                self.assertIn("p_list_item_link_text=>'more'", more_items[0])
                self.assertIn(
                    "p_list_item_disp_condition=>':orac_return_depth > 1'",
                    more_items[0],
                )
                self.assertNotIn("p_list_item_link_target", more_items[0])
                for position in range(2, 6):
                    self.assertIn(
                        f"p_list_item_link_text=>'return to &orac_return_label_{position}.'",
                        return_list,
                    )
                    self.assertIn(
                        f"p_list_item_link_target=>'&orac_return_url_{position}!raw.'",
                        return_list,
                    )
                    self.assertIn(
                        f":orac_return_label_{position} is not null and "
                        f":orac_return_url_{position} is not null",
                        return_list,
                    )
                self.assertNotIn("orac_return_label_1!raw", return_list)
                self.assertNotIn("orac_return_label_2!raw", return_list)
                self.assertNotIn("orac_return_label_3!raw", return_list)
                self.assertNotIn("orac_return_label_4!raw", return_list)
                self.assertNotIn("orac_return_label_5!raw", return_list)
                self.assertEqual(
                    1, page_0.count("p_plug_name=>'cross-app return navigation'")
                )
                self.assertNotIn("regexp_substr(:orac_nav_stack", export_sql)
                self.assertNotIn("split(:orac_nav_stack", export_sql)
                self.assertNotIn("f?p=' ||", export_sql)
                self.assertNotIn("launched_from_1042", export_sql)

    def test_plugin_apex_apps_do_not_reuse_scaffold_component_ids(self) -> None:
        plugin_exports = (
            PROJECT_ROOT / "plugins/home_assistant/apex/f10010.sql",
            PROJECT_ROOT / "plugins/drop_box/apex/f10020.sql",
        )

        for export_path in plugin_exports:
            export_sql = export_path.read_text(encoding="utf-8").lower()
            with self.subTest(export=export_path.name):
                self.assertNotIn("wwv_flow_imp.id(145", export_sql)

    def test_f1043_navigation_links_to_plugin_app_maintenance(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1043.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertIn("p_list_item_link_text=>'manage plugin apps'", export_sql)
        self.assertIn(
            "p_list_item_link_target=>'f?p=&app_id.:3:&app_session.::&debug.:::'",
            export_sql,
        )
        self.assertIn("p_list_item_icon=>'fa-list-alt'", export_sql)
        self.assertIn("p_list_item_current_for_pages=>'3,4'", export_sql)

    def test_f1043_manage_plugin_apps_report_uses_code_view(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1043.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        page_3 = _apex_page_sections(export_sql)[3]

        self.assertIn("p_id=>3", page_3)
        self.assertIn("p_name=>'manage plugin apps'", page_3)
        self.assertIn("p_plug_name=>'plugin apps'", page_3)
        self.assertIn("p_plug_source_type=>'native_ir'", page_3)
        self.assertIn("from orac_code.plugin_apex_apps_v", page_3)
        self.assertNotIn("from orac_core.plugin_apex_apps", page_3)
        self.assertIn("p_column_link=>'f?p=&app_id.:4:", page_3)
        self.assertIn("p4_plugin_id,p4_app_alias:#plugin_id#,#app_alias#", page_3)
        for column_name in (
            "label",
            "app_alias",
            "plugin_version",
            "installed_app_id",
            "install_status",
            "enabled",
        ):
            self.assertIn(f"p_db_column_name=>'{column_name}'", page_3)
        self.assertIn("p_db_column_name=>'row_version'", page_3)

    def test_f1043_plugin_app_form_toggles_enabled_via_admin_api(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1043.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        page_4 = _apex_page_sections(export_sql)[4]

        self.assertIn("p_id=>4", page_4)
        self.assertIn("p_name=>'plugin app'", page_4)
        self.assertIn("p_page_mode=>'modal'", page_4)
        self.assertIn("p_name=>'p4_plugin_id'", page_4)
        self.assertIn("p_name=>'p4_app_alias'", page_4)
        self.assertIn("p_name=>'p4_enabled'", page_4)
        self.assertIn("p_display_as=>'native_yes_no'", page_4)
        self.assertIn("p_name=>'p4_row_version'", page_4)
        self.assertIn("orac_code.plugin_apex_app_admin_api.set_enabled", page_4)
        self.assertIn("p_enabled     => :p4_enabled", page_4)
        self.assertIn("p_row_version => :p4_row_version", page_4)
        self.assertIn("from orac_code.plugin_apex_apps_v", page_4)
        self.assertIn("p_process_type=>'native_close_window'", page_4)
        self.assertIn("p_action=>'native_dialog_cancel'", page_4)
        self.assertNotRegex(
            page_4,
            r"\b(update|insert|delete|merge)\s+(into\s+)?orac_(core|api)\.plugin_apex_apps",
        )

    def test_f1042_projects_navigation_entry_exists(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertIn("p_list_item_link_text=>'projects'", export_sql)
        self.assertIn(
            "p_list_item_link_target=>'f?p=&app_id.:37:&app_session.::&debug.:::'",
            export_sql,
        )
        self.assertIn("p_list_item_current_for_pages=>'37,38'", export_sql)
        self.assertIn("p_short_name=>'projects'", export_sql)
        self.assertIn("p_page_id=>37", export_sql)
        self.assertIn("p_short_name=>'project'", export_sql)
        self.assertIn("p_page_id=>38", export_sql)

    def test_f1042_projects_report_uses_project_registry_code_view(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        page_37 = _apex_page_sections(export_sql)[37]

        self.assertIn("p_id=>37", page_37)
        self.assertIn("p_name=>'projects'", page_37)
        self.assertIn("p_plug_source_type=>'native_ir'", page_37)
        self.assertIn("from orac_code.project_registry_v", page_37)
        self.assertNotIn("from orac_api.project_registry_v", page_37)
        self.assertNotIn("from orac_core.project_registry", page_37)
        self.assertIn("p_column_link=>'f?p=&app_id.:38:", page_37)
        self.assertIn("p38_project_id:#project_id#", page_37)
        for column_name in (
            "project_code",
            "display_name",
            "description",
            "active_yn",
        ):
            self.assertIn(f"p_db_column_name=>'{column_name}'", page_37)
        for forbidden in (
            "created_by",
            "created_on",
            "updated_by",
            "updated_on",
            "row_version",
            "row_checksum",
        ):
            self.assertNotIn(f"p_db_column_name=>'{forbidden}'", page_37)

    def test_f1042_projects_maintenance_actions_are_visible(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        page_37 = _apex_page_sections(export_sql)[37]
        create_button = _apex_component_block(
            PAGE_BUTTON_BLOCK_RE,
            page_37,
            "p_button_name=>'create_project'",
        )
        edit_column = _apex_component_block(
            WORKSHEET_COLUMN_BLOCK_RE,
            page_37,
            "p_db_column_name=>'project_id'",
        )

        self.assertIn("p_button_image_alt=>'create project'", create_button)
        self.assertIn("p_button_position=>'right_of_ir_search_bar'", create_button)
        self.assertIn("p_button_is_hot=>'y'", create_button)
        self.assertIn(
            "p_button_redirect_url=>'f?p=&app_id.:38:&app_session.::&debug.:rp,38::'",
            create_button,
        )
        self.assertNotIn("t-button--noui", create_button)
        self.assertNotIn("p38_project_id", create_button)

        self.assertIn("p_column_label=>'edit'", edit_column)
        self.assertIn('aria-label="edit"', edit_column)
        self.assertIn("p38_project_id:#project_id#", edit_column)
        self.assertNotIn("hidden_escape_sc", edit_column)
        self.assertIn("p_column_alignment=>'center'", edit_column)

    def test_f1042_project_form_uses_registry_api(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        page_38 = _apex_page_sections(export_sql)[38]

        self.assertIn("p_id=>38", page_38)
        self.assertIn("p_name=>'project'", page_38)
        self.assertIn("p_name=>'p38_project_id'", page_38)
        self.assertIn("p_name=>'p38_project_code'", page_38)
        self.assertIn("p_name=>'p38_display_name'", page_38)
        self.assertIn("p_name=>'p38_description'", page_38)
        self.assertIn("p_name=>'p38_active_yn'", page_38)
        self.assertIn("p_name=>'p38_row_checksum'", page_38)
        self.assertIn("from orac_code.project_registry_v", page_38)
        self.assertIn("orac_code.project_registry_api.create_project", page_38)
        self.assertIn("orac_code.project_registry_api.update_project", page_38)
        self.assertIn("orac_code.project_registry_api.deactivate_project", page_38)
        self.assertNotIn("orac_code.project_registry_api.delete_project", page_38)
        self.assertIn("p_row_checksum => :p38_row_checksum", page_38)
        self.assertIn("p_read_only_when=>'p38_project_id'", page_38)
        self.assertIn("p_read_only_when_type=>'item_is_not_null'", page_38)
        self.assertIn("p_button_name=>'deactivate'", page_38)
        self.assertIn("p_button_image_alt=>'deactivate'", page_38)
        self.assertIn("p_button_condition=>'p38_project_id'", page_38)
        self.assertIn("p_confirm_style=>'danger'", page_38)
        self.assertIn("p_process_when=>'deactivate'", page_38)
        self.assertIn("project deactivated", page_38)
        self.assertIn("p_display_as=>'native_select_list'", page_38)
        self.assertIn("p_named_lov=>'yes_no_yn'", page_38)
        self.assertIn("p38_active_yn := upper(trim(:p38_active_yn))", page_38)
        self.assertIn("^[a-z][a-z0-9_]{1,99}$", page_38)
        self.assertIn("project code already exists", page_38)
        self.assertIn("p_process_type=>'native_close_window'", page_38)
        self.assertNotIn("p_database_action=>'delete'", page_38)
        self.assertNotRegex(
            page_38,
            r"\b(update|insert|delete|merge)\s+(into\s+)?orac_(core|api)\.project_registry",
        )

    def test_f1042_project_form_has_no_audit_or_row_version_items(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "resources/db/apex/orac_apps/f1042.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        page_38 = _apex_page_sections(export_sql)[38]

        for forbidden_item in (
            "p38_created_by",
            "p38_created_on",
            "p38_updated_by",
            "p38_updated_on",
            "p38_row_version",
        ):
            self.assertNotIn(f"p_name=>'{forbidden_item}'", page_38)

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
        self.assertIn("orac_code.knowledge_tag_lov_v", export_sql)
        self.assertIn("orac_code.plugin_prerequisite_status_v", export_sql)
        capability_region_start = export_sql.index(
            "p_plug_name=>'document conversion capability'"
        )
        capability_region_end = export_sql.index(
            "wwv_flow_imp_page.create_page_plug(", capability_region_start
        )
        capability_region = export_sql[capability_region_start:capability_region_end]
        self.assertIn("p_function_body_language=>'plsql'", capability_region)
        self.assertIn("orac_dropbox.drop_box_admin_api.create_location", export_sql)
        self.assertIn("orac_dropbox.drop_box_admin_api.update_location", export_sql)
        self.assertIn("orac_dropbox.drop_box_admin_api.set_enabled", export_sql)
        self.assertIn("orac_dropbox.drop_box_admin_api.delete_location", export_sql)
        self.assertIn("orac_code.rag_usage_scope_lov_v", export_sql)
        self.assertIn("total_job_count", export_sql)
        self.assertIn("p_name=>'drop location form'", export_sql)
        self.assertIn("p_name=>'drop location detail'", export_sql)
        self.assertIn("p_name=>'job detail'", export_sql)
        self.assertIn("p_name=>'activity'", export_sql)
        self.assertIn("p_list_item_link_text=>'activity'", export_sql)
        self.assertIn(
            'p_column_linktext=>\'<span role="img" aria-label="edit"', export_sql
        )
        self.assertIn("p_column_linktext=>'view activity'", export_sql)
        self.assertIn("view_activity_location_id", export_sql)
        self.assertIn("p5_drop_location_id", export_sql)
        self.assertIn("toggle_location", export_sql)
        self.assertIn("p2_target_plugin_key", export_sql)
        self.assertIn("p2_target_project_key", export_sql)
        self.assertIn("eligible project is selected", export_sql)
        self.assertIn("eligible plugin is selected", export_sql)
        self.assertIn(
            "p_page_template_options=>'#default#:js-dialog-class-t-drawer--pulloutend'",
            export_sql,
        )
        self.assertIn("p_dialog_width=>'1200'", export_sql)
        classification_item_start = export_sql.index("p_name=>'p2_classification_tags'")
        classification_item_end = export_sql.index(
            "wwv_flow_imp_page.create_page_item(", classification_item_start
        )
        classification_item = export_sql[
            classification_item_start:classification_item_end
        ]
        self.assertNotIn("p_begin_on_new_line=>'n'", classification_item)
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
            "ingestion notes",
            "post-processing / future use",
        ):
            self.assertIn(f"p_plug_name=>'{region}'", page_two)

        ordered_tokens = (
            "p_name=>'p2_location_code'",
            "p_name=>'p2_display_name'",
            "p_name=>'p2_path'",
            "p_name=>'p2_enabled_yn'",
            "p_name=>'p2_target_scope_type'",
            "p_name=>'p2_target_plugin_key'",
            "p_name=>'p2_target_project_key'",
            "p_name=>'p2_classification_tags'",
            "p_name=>'p2_ingestion_notes'",
            "p_name=>'p2_allowed_extensions'",
            "p_name=>'p2_ignore_patterns'",
            "p_name=>'p2_recursive_yn'",
            "p_name=>'p2_move_processed_yn'",
            "p_name=>'p2_processed_path'",
            "p_name=>'p2_failed_path'",
            "p_name=>'p2_max_file_size_mb'",
            "p_name=>'p2_stability_seconds'",
        )
        positions = [page_two.index(token) for token in ordered_tokens]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("${orac_home}/", page_two)

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
        profile_start = page_two.index("p_name=>'p2_classification_tags'")
        profile_end = page_two.find(
            "wwv_flow_imp_page.create_page_item", profile_start + 1
        )
        profile_text = page_two[
            profile_start : profile_end if profile_end != -1 else len(page_two)
        ]
        self.assertIn("p_display_as=>'native_shuttle'", profile_text)
        self.assertIn("orac_code.knowledge_tag_lov_v", profile_text)
        self.assertIn("display_value d", profile_text)
        self.assertIn("return_value r", profile_text)
        self.assertIn("order by sort_order, return_value", profile_text)
        self.assertNotIn("p_display_as=>'native_text_field'", profile_text)
        self.assertIn("descriptive tags", profile_text)
        self.assertNotIn("p_name=>'p2_profile_description'", page_two)
        self.assertNotIn("p_name=>'p2_profile_default_instruction'", page_two)
        self.assertNotIn("p_plug_name=>'audit / metadata'", page_two)
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

        scope_type_text = _apex_component_block(
            PAGE_ITEM_BLOCK_RE,
            page_two,
            "p_name=>'p2_target_scope_type'",
        )
        project_text = _apex_component_block(
            PAGE_ITEM_BLOCK_RE,
            page_two,
            "p_name=>'p2_target_project_key'",
        )
        plugin_text = _apex_component_block(
            PAGE_ITEM_BLOCK_RE,
            page_two,
            "p_name=>'p2_target_plugin_key'",
        )

        self.assertIn("p_prompt=>'project'", project_text)
        self.assertIn("scope.project_display_name d", project_text)
        self.assertIn("scope.scope_key r", project_text)
        self.assertIn("scope.scope_key = :p2_target_project_key", project_text)
        self.assertIn("eligible.return_value = scope.knowledge_scope_id", project_text)
        self.assertNotIn("display_value d", project_text)

        self.assertIn("p_prompt=>'plugin'", plugin_text)
        self.assertIn("max(scope.plugin_name) d", plugin_text)
        self.assertIn("group by scope.scope_key", plugin_text)
        self.assertIn("scope.scope_key r", plugin_text)
        self.assertIn("scope.scope_key = :p2_target_plugin_key", plugin_text)
        self.assertIn("eligible.return_value = scope.knowledge_scope_id", plugin_text)
        self.assertNotIn("display_value d", plugin_text)

        for target_text in (project_text, plugin_text):
            self.assertIn("p_display_as=>'native_select_list'", target_text)
            self.assertIn("orac_code.knowledge_scope_registry_v", target_text)
            self.assertIn("orac_code.rag_usage_scope_lov_v", target_text)
            self.assertIn("p_lov_display_extra=>'no'", target_text)
            self.assertIn("p_begin_on_new_line=>'n'", target_text)
            self.assertIn("p_colspan=>6", target_text)
            self.assertIn("p_grid_column=>7", target_text)
            self.assertNotIn("native_text_field", target_text)

        self.assertIn("p_lov_display_extra=>'no'", scope_type_text)
        self.assertIn("p_colspan=>6", scope_type_text)

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
        self.assertIn("p_button_execute_validations=>'n'", page_two)
        self.assertIn("p_button_name=>'save'", page_two)
        self.assertIn("p_button_action=>'submit'", page_two)
        self.assertIn("p_button_name=>'delete'", page_two)
        # Danger styling is an explicit maintenance-dialog UX contract.
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
        self.assertIn("p_validation_name=>'eligible project is selected'", page_two)
        self.assertIn("p_validation_name=>'eligible plugin is selected'", page_two)
        self.assertIn("from orac_code.rag_usage_scope_lov_v", page_two)
        self.assertIn("select an eligible project", page_two)
        self.assertIn("select an eligible plugin", page_two)
        self.assertEqual(
            page_two.count("p_when_button_pressed=>wwv_flow_imp.id(34600200000000302)"),
            2,
        )
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

    def test_drop_box_page_two_shows_only_selected_target(self) -> None:
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

        self.assertIn("p_name=>'scope target visibility'", page_two)
        self.assertIn("p_triggering_element=>'p2_target_scope_type'", page_two)
        visibility_start = page_two.index("p_name=>'scope target visibility'")
        visibility_end = page_two.index("p_name=>'normalize case fields'")
        visibility = page_two[visibility_start:visibility_end]

        self.assertNotIn("p_action=>'native_javascript_code'", visibility)
        self.assertEqual(visibility.count("p_action=>'native_hide'"), 2)
        self.assertEqual(visibility.count("p_action=>'native_clear'"), 2)
        self.assertEqual(visibility.count("p_action=>'native_show'"), 2)
        self.assertIn("p_affected_elements=>'p2_target_project_key'", visibility)
        self.assertIn("p_affected_elements=>'p2_target_plugin_key'", visibility)
        self.assertIn("p_client_condition_expression=>'project'", visibility)
        self.assertIn("p_client_condition_expression=>'plugin'", visibility)
        self.assertEqual(visibility.count("p_execute_on_page_init=>'n'"), 2)
        self.assertEqual(visibility.count("p_execute_on_page_init=>'y'"), 4)

    def test_drop_box_target_views_show_type_and_descriptor_separately(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "plugins/drop_box/apex/f10020.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        pages = _apex_page_sections(export_sql)
        page_one = pages[1]
        page_three = pages[3]

        self.assertIn("target_display_name", page_one)
        self.assertIn("scope.project_display_name", page_one)
        self.assertIn("scope.plugin_name", page_one)
        self.assertIn("p_db_column_name=>'target_scope_type'", page_one)
        self.assertIn("p_column_label=>'target scope type'", page_one)
        self.assertIn("p_db_column_name=>'target_display_name'", page_one)
        self.assertIn("p_column_label=>'project / plugin'", page_one)
        self.assertNotIn("p_db_column_name=>'target_scope_key'", page_one)
        self.assertNotIn("target_scope_type || ':'", page_one)

        self.assertIn("<dt>target scope type</dt>", page_three)
        self.assertIn("scope.project_display_name", page_three)
        self.assertIn("scope.plugin_name", page_three)
        self.assertIn("target_display_name", page_three)
        self.assertNotIn("target_scope_type || ':'", page_three)

    def test_drop_box_page_two_tag_lov_and_field_behaviour(self) -> None:
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
        self.assertIn("from orac_code.knowledge_tag_lov_v", page_two)
        self.assertIn(
            "json_arrayagg(return_value order by sort_order, return_value",
            page_two,
        )
        self.assertIn("where return_value in (", page_two)
        self.assertNotIn("tag_code r", page_two)

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

    def test_drop_box_lifecycle_buckets_are_exhaustive_and_mutually_exclusive(
        self,
    ) -> None:
        """Every valid status/linkage combination must map to exactly one bucket."""
        constraint_sql = (
            PROJECT_ROOT
            / "plugins/drop_box/db/schema/constraint_other/drp_job_retry_status_ck.sql"
        ).read_text(encoding="utf-8")
        constrained_statuses = set(
            re.findall(
                r"'([a-z_]+)'", constraint_sql[constraint_sql.index("check (") :]
            )
        )
        self.assertEqual(constrained_statuses, set(DROP_BOX_STATUSES))
        core_cases = (
            ("null_link", False, False, None, None),
            ("broken_link", True, False, None, None),
            ("core_queued", True, True, "QUEUED", "N"),
            ("core_processing", True, True, "PROCESSING", "N"),
            ("core_retry_wait", True, True, "RETRY_WAIT", "N"),
            ("core_completed_searchable", True, True, "COMPLETED", "Y"),
            ("core_completed_not_searchable", True, True, "COMPLETED", "N"),
            ("core_failed", True, True, "FAILED", "N"),
            ("core_null_state", True, True, None, None),
        )
        counts = {
            "AWAITING_HANDOFF": 0,
            "PREREQUISITE_DEFERRED": 0,
            "CONVERSION_RETRY": 0,
            "CORE_IN_PROGRESS": 0,
            "SEARCHABLE": 0,
            "FAILED_ATTENTION": 0,
            "SKIPPED": 0,
        }

        for drop_box_status in DROP_BOX_STATUSES:
            for (
                case_name,
                request_id_present,
                core_row_present,
                core_status,
                searchable,
            ) in core_cases:
                with self.subTest(
                    drop_box_status=drop_box_status,
                    core_case=case_name,
                ):
                    bucket = _expected_lifecycle_bucket(
                        drop_box_status,
                        request_id_present=request_id_present,
                        core_row_present=core_row_present,
                        core_status=core_status,
                        searchable=searchable,
                    )
                    if drop_box_status.startswith("skipped_"):
                        expected = "SKIPPED"
                    elif drop_box_status in {"failed", "quarantined"}:
                        expected = "FAILED_ATTENTION"
                    elif drop_box_status == "deferred_prerequisite":
                        expected = "PREREQUISITE_DEFERRED"
                    elif drop_box_status == "conversion_retry_wait":
                        expected = "CONVERSION_RETRY"
                    elif drop_box_status in {"queued", "processing"}:
                        expected = "AWAITING_HANDOFF"
                    else:
                        expected = {
                            "null_link": "FAILED_ATTENTION",
                            "broken_link": "FAILED_ATTENTION",
                            "core_queued": "CORE_IN_PROGRESS",
                            "core_processing": "CORE_IN_PROGRESS",
                            "core_retry_wait": "CORE_IN_PROGRESS",
                            "core_completed_searchable": "SEARCHABLE",
                            "core_completed_not_searchable": "FAILED_ATTENTION",
                            "core_failed": "FAILED_ATTENTION",
                            "core_null_state": "FAILED_ATTENTION",
                        }[case_name]
                    self.assertEqual(bucket, expected)
                    counts[bucket] += 1

        self.assertEqual(sum(counts.values()), len(DROP_BOX_STATUSES) * len(core_cases))
        self.assertTrue(all(count > 0 for count in counts.values()))

    def test_drop_box_page_one_implements_approved_lifecycle_precedence(
        self,
    ) -> None:
        export_sql = (
            (PROJECT_ROOT / "plugins/drop_box/apex/f10020.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        page_one = _apex_page_sections(export_sql)[1]
        precedence_tokens = (
            "job.status_code in (''skipped_duplicate'', ''skipped_disallowed_type'', ''skipped_too_large'')",
            "job.status_code in (''failed'', ''quarantined'')",
            "job.status_code = ''deferred_prerequisite''",
            "job.status_code = ''conversion_retry_wait''",
            "job.status_code in (''queued'', ''processing'')",
            "job.knowledge_ingestion_request_id is null",
            "or core.ingestion_request_id is null",
            "core.searchable_yn = ''y''",
            "core.status_code in (''queued'', ''processing'', ''retry_wait'')",
            "else ''failed_attention''",
        )

        positions = [page_one.index(token) for token in precedence_tokens]
        self.assertEqual(positions, sorted(positions))
        for count_column in (
            "total_job_count",
            "awaiting_handoff_count",
            "prerequisite_deferred_count",
            "conversion_retry_count",
            "core_in_progress_count",
            "searchable_count",
            "failed_attention_count",
            "skipped_count",
        ):
            self.assertRegex(
                page_one,
                rf"count\(distinct .*?\) {count_column}",
            )
        self.assertIn("p_column_label=>'failed / attention'", page_one)
        self.assertIn(
            "includes historical drop box failures, broken core correlation, core failures, and completed requests that are not searchable. a count does not necessarily indicate an unresolved current incident.",
            page_one,
        )
        self.assertNotIn("latest_job_status", export_sql)
        self.assertNotIn("latest job status", export_sql)
        acceptance_sql = (
            (
                PROJECT_ROOT
                / "plugins/drop_box/db/acceptance/drop_box_lifecycle_rollup.sql"
            )
            .read_text(encoding="utf-8")
            .lower()
        )
        for count_column in (
            "total_job_count",
            "awaiting_handoff_count",
            "prerequisite_deferred_count",
            "conversion_retry_count",
            "core_in_progress_count",
            "searchable_count",
            "failed_attention_count",
            "skipped_count",
        ):
            self.assertRegex(
                acceptance_sql,
                rf"(?s)count\(distinct .*?\) {count_column}",
            )
        self.assertIn("drop_box_lifecycle_rollup_ok", acceptance_sql)

    def test_drop_box_admin_app_never_renders_raw_operational_errors(self) -> None:
        export_sql = (
            (PROJECT_ROOT / "plugins/drop_box/apex/f10020.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        relevant_pages = "\n".join(
            _apex_page_sections(export_sql)[page_id] for page_id in (1, 3, 4, 5)
        )

        for forbidden in (
            "job.error_message",
            "core.last_error_message",
            "substr(job.error_message",
            "dbms_lob.substr(core.last_error_message",
            "effective_instruction",
            "effective_profile_instruction",
        ):
            self.assertNotIn(forbidden, relevant_pages)
        for required in (
            "error_summary_redacted",
            "event_message_redacted",
            "drop_box_error_summary_redacted",
            "core_error_summary_redacted",
            "review restricted logs",
        ):
            self.assertIn(required, relevant_pages)
        self.assertNotIn("p_escape_on_http_output=>'n'", relevant_pages)
        self.assertNotRegex(
            relevant_pages,
            r"p_db_column_name=>'(?:source_filename|source_path|[a-z_]*error[a-z_]*)'.*?p_column_html_expression=>",
        )

    def test_drop_box_activity_page_uses_current_job_and_core_status_views(
        self,
    ) -> None:
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
        self.assertIn("from orac_dropbox.drop_job_admin_v job", activity_page)
        self.assertIn(
            "left join orac_code.knowledge_ingestion_requests_v core",
            activity_page,
        )
        self.assertIn(
            "on core.ingestion_request_id = job.knowledge_ingestion_request_id",
            activity_page,
        )
        self.assertIn(
            "job.drop_location_id = to_number(:p5_drop_location_id)", activity_page
        )
        self.assertIn("p_button_name=>'back_to_locations'", activity_page)
        self.assertIn("p_button_image_alt=>'back to locations'", activity_page)
        self.assertIn("p_button_action=>'redirect_page'", activity_page)
        self.assertIn(
            "p_button_redirect_url=>'f?p=&app_id.:1:&app_session.::&debug.:::'",
            activity_page,
        )
        self.assertNotIn("drop_job_event_admin_v evt", activity_page)
        for token in (
            "location_code",
            "location_display_name",
            "drop_job_id",
            "source_filename",
            "source_path",
            "core_request_id",
            "drop_box_state",
            "core_state",
            "drop_box_detected_on",
            "drop_box_stable_on",
            "drop_box_started_on",
            "drop_box_updated_on",
            "drop_box_completed_on",
            "core_accepted_on",
            "core_claimed_on",
            "core_latest_event_on",
            "core_completed_on",
            "document_id",
            "document_version_id",
            "chunk_count",
            "embedded_chunk_count",
            "searchable_yn",
            "drop_box_error_summary_redacted",
            "core_error_summary_redacted",
        ):
            self.assertIn(token, activity_page)
        self.assertIn(
            "left join orac_code.knowledge_ingestion_requests_v core", activity_page
        )
        self.assertNotIn("knowledge_chunks_v", activity_page)
        self.assertNotIn("knowledge_chunk_embeddings_v", activity_page)
        self.assertNotIn("core.last_error_message", activity_page)
        self.assertNotIn("job.error_message", activity_page)
        self.assertNotIn("event_type", activity_page)
        self.assertNotIn("event_message", activity_page)
        self.assertNotIn("handed off - core processing", activity_page)
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
        self.assertIn("from orac_api.plugin_registry_v", view_sql)
        self.assertNotIn("from orac_code.plugin_registry_v", view_sql)
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
        self.assertIn(
            "grant execute on orac_code.apex_return_nav_api to orac_apx_pub;",
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
