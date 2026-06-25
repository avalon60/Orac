"""Static checks for user preference validation integration."""
# Author: Clive Bostock
# Date: 2026-06-25
# Description: Verifies preference validation remains package-authoritative.

from __future__ import annotations

from pathlib import Path
import re
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_ROOT = PROJECT_ROOT / "resources" / "db" / "schema"
APEX_ROOT = PROJECT_ROOT / "resources" / "db" / "apex"
CODE_ROOT = SCHEMA_ROOT / "orac_code"
APP_1042_EXPORT = APEX_ROOT / "orac_apps" / "f1042.sql"


class UserPreferencesValidationTests(unittest.TestCase):
    """Verify APEX-aware preference validation stays on the package path."""

    def test_package_reports_apex_errors_from_authoritative_validation(self) -> None:
        """The preference API should add APEX errors from its validation path."""
        package_sql = (
            CODE_ROOT / "package_body" / "user_preferences_api.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("function report_validation_failure", package_sql)
        self.assertIn("apex_error.add_error", package_sql)
        self.assertIn("apex_error.c_inline_with_field_and_notif", package_sql)
        self.assertIn("apex_error.c_inline_in_notification", package_sql)
        self.assertIn("sys_context('apex$session', 'app_id')", package_sql)
        self.assertIn("return p_message;", package_sql)

    def test_package_api_accepts_optional_apex_page_item_context(self) -> None:
        """The public package API should keep callers backward compatible."""
        spec_sql = (
            CODE_ROOT / "package_spec" / "user_preferences_api.sql"
        ).read_text(encoding="utf-8").lower()
        body_sql = (
            CODE_ROOT / "package_body" / "user_preferences_api.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertGreaterEqual(
            spec_sql.count("p_apex_page_item_name in varchar2 default null"),
            3,
        )
        self.assertIn("function validate_preference_value", spec_sql)
        self.assertIn("p_apex_page_item_name  => p_apex_page_item_name", body_sql)

    def test_f1042_page6_passes_active_value_item_to_save_path(self) -> None:
        """App 1042 page 6 should identify the active value item for errors."""
        export_sql = APP_1042_EXPORT.read_text(encoding="utf-8").lower()

        self.assertIn("l_apex_page_item_name := case", export_sql)
        self.assertIn(
            "when :p6_pref_key = ''weather_location'' "
            "then ''p6_pref_value_search_term''",
            export_sql,
        )
        self.assertIn(
            "when :p6_control_type in (''popup_lov'', ''select_one'') "
            "then ''p6_pref_value_popup_lov''",
            export_sql,
        )
        self.assertIn(
            "when :p6_control_type = ''select_list'' "
            "then ''p6_pref_value_select_list''",
            export_sql,
        )
        self.assertIn(
            "when l_value_type = ''number'' then ''p6_pref_value_number''",
            export_sql,
        )
        self.assertIn(
            "when l_value_type = ''boolean'' then ''p6_pref_value_boolean''",
            export_sql,
        )
        self.assertIn(
            "when l_value_type in (''string'', ''json'') "
            "then ''p6_pref_value_text''",
            export_sql,
        )
        self.assertIn("p_apex_page_item_name => l_apex_page_item_name", export_sql)

    def test_f1042_page6_has_no_duplicate_page_validation_rules(self) -> None:
        """Page 6 should not duplicate preference validation as APEX rules."""
        export_sql = APP_1042_EXPORT.read_text(encoding="utf-8").lower()
        page6_match = re.search(
            r"prompt --application/pages/page_00006(?P<body>.*?)"
            r"prompt --application/pages/page_00007",
            export_sql,
            re.DOTALL,
        )

        self.assertIsNotNone(page6_match)
        page6_sql = page6_match.group("body")

        self.assertNotIn("wwv_flow_imp_page.create_page_validation", page6_sql)
        self.assertNotIn("validate_preference_value(", page6_sql)


if __name__ == "__main__":
    unittest.main()
