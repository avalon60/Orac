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
CORE_ROOT = SCHEMA_ROOT / "orac_core"
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
            "when l_control_type in (''popup_lov'', ''select_one'') "
            "then ''p6_pref_value_popup_lov''",
            export_sql,
        )
        self.assertIn(
            "when l_control_type = ''select_list'' "
            "then ''p6_pref_value_select_list''",
            export_sql,
        )
        self.assertIn(
            "when l_control_type = ''slider'' "
            "then ''p6_pref_value_slider''",
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

    def test_f1042_page6_slider_is_metadata_driven(self) -> None:
        """Page 6 should render a generic slider from preference metadata."""
        export_sql = APP_1042_EXPORT.read_text(encoding="utf-8").lower()

        slider_item_match = re.search(
            r"p_name=>'p6_pref_value_slider'.*?p_display_as=>'native_hidden'",
            export_sql,
            re.DOTALL,
        )

        self.assertIsNotNone(slider_item_match)
        self.assertIn("p_region_name=>'orac_pref_slider_host'", export_sql)
        self.assertIn("orac-pref-slider-host-body", export_sql)
        self.assertNotIn("p_plug_source_type=>'native_static_content'", export_sql)
        self.assertIn("'output_as', 'html'", export_sql)
        self.assertIn(".orac-pref-slider {", export_sql)
        self.assertIn(".orac-pref-slider-input {", export_sql)
        self.assertIn("box-sizing: border-box;", export_sql)
        self.assertIn("width: 100%;", export_sql)
        self.assertIn(".orac-pref-slider-meta {", export_sql)
        self.assertIn(
            "grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);",
            export_sql,
        )
        self.assertIn(".orac-pref-slider-meta > :last-child {", export_sql)
        self.assertIn("justify-self: end;", export_sql)
        self.assertIn("p_name=>'p6_min_number'", export_sql)
        self.assertIn("p_name=>'p6_max_number'", export_sql)
        self.assertIn("p_name=>'p6_step_number'", export_sql)
        self.assertIn("p_name=>'p6_unit_label'", export_sql)
        self.assertIn("p_name=>'p6_display_min_label'", export_sql)
        self.assertIn("p_name=>'p6_display_max_label'", export_sql)
        self.assertIn("p_name=>'p6_display_value_format'", export_sql)
        self.assertIn("controltype === ''slider''", export_sql)
        self.assertIn(
            "p_client_condition_expression=>'($v(''p6_control_type'') || "
            "'''').tolowercase() === ''slider'''",
            export_sql,
        )
        self.assertIn("document.createelement(''input'')", export_sql)
        self.assertIn("input.type = ''range''", export_sql)
        self.assertIn("input.min = min", export_sql)
        self.assertIn("input.max = max", export_sql)
        self.assertIn("input.step = step", export_sql)
        self.assertIn("item.setvalue(input.value)", export_sql)
        self.assertIn("sliderhostbody.empty()", export_sql)
        self.assertIn("sliderhostregion.hide()", export_sql)
        self.assertIn("slideritem.setvalue('''')", export_sql)
        self.assertIn("p6_pref_value_slider := :p6_pref_value_number", export_sql)
        self.assertNotIn("slidernode.attr({", export_sql)
        self.assertNotIn("type: ''range'',", export_sql)
        self.assertNotIn("p6_tts_rate", export_sql)
        self.assertNotIn("p6_tts_pitch", export_sql)
        self.assertNotIn("p6_max_tokens", export_sql)

    def test_f1042_page6_javascript_actions_fit_import_buffer(self) -> None:
        """Page 6 JavaScript DA actions should fit APEX import VARCHAR2 buffers."""
        export_sql = APP_1042_EXPORT.read_text(encoding="utf-8")
        page6_match = re.search(
            r"prompt --application/pages/page_00006(?P<body>.*?)"
            r"prompt --application/pages/page_00007",
            export_sql,
            re.DOTALL,
        )

        self.assertIsNotNone(page6_match)
        page6_sql = page6_match.group("body")
        action_blocks = re.findall(
            r"p_action=>'NATIVE_JAVASCRIPT_CODE'.*?"
            r"p_attribute_01=>wwv_flow_string\.join\(wwv_flow_t_varchar2\("
            r"(?P<body>.*?)\)\)",
            page6_sql,
            re.DOTALL,
        )

        self.assertGreaterEqual(len(action_blocks), 3)
        for action_block in action_blocks:
            javascript = "\n".join(
                line.strip().removesuffix(",")[1:-1].replace("''", "'")
                for line in action_block.splitlines()
                if line.strip().startswith("'")
            )
            self.assertLessEqual(len(javascript), 3900)

    def test_f1042_page6_save_does_not_trust_render_metadata(self) -> None:
        """The save process should submit value only, not client metadata."""
        export_sql = APP_1042_EXPORT.read_text(encoding="utf-8").lower()
        process_start = export_sql.index(
            "p_process_name=>'process form user preferences'"
        )
        process_end = export_sql.index("p_process_name=>'close dialog'", process_start)
        process_sql = export_sql[process_start:process_end]

        self.assertIn("p6_pref_value_slider", process_sql)
        self.assertIn("orac_code.user_preferences_api.upd", process_sql)
        self.assertIn("l_control_type", process_sql)
        self.assertNotIn(":p6_control_type", process_sql)
        self.assertNotIn("p6_min_number", process_sql)
        self.assertNotIn("p6_max_number", process_sql)
        self.assertNotIn("p6_step_number", process_sql)
        self.assertNotIn("p6_unit_label", process_sql)

    def test_preference_slider_metadata_constraints_are_authoritative(self) -> None:
        """Database metadata should reject invalid slider definitions."""
        control_check_sql = (
            CORE_ROOT / "constraint_other" / "prfdfn_ck2_slider_control_type.sql"
        ).read_text(encoding="utf-8").lower()
        slider_check_sql = (
            CORE_ROOT / "constraint_other" / "prfdfn_ck7.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("'slider'", control_check_sql)
        self.assertIn("control_type <> 'slider'", slider_check_sql)
        self.assertIn("value_type = 'number'", slider_check_sql)
        self.assertIn("min_number is not null", slider_check_sql)
        self.assertIn("max_number is not null", slider_check_sql)
        self.assertIn("step_number is not null", slider_check_sql)
        self.assertIn("step_number > 0", slider_check_sql)

    def test_preference_api_reloads_metadata_for_numeric_step_validation(self) -> None:
        """Server-side validation should enforce min/max/step from metadata."""
        package_sql = (
            CODE_ROOT / "package_body" / "user_preferences_api.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("from orac_api.preference_definitions_v", package_sql)
        self.assertIn("l_pref_definition.step_number", package_sql)
        self.assertIn("mod(", package_sql)
        self.assertIn(
            "l_number_value - coalesce(l_pref_definition.min_number, 0)",
            package_sql,
        )
        self.assertIn("must be at least", package_sql)
        self.assertIn("must be at most", package_sql)
        self.assertIn("must align to step", package_sql)
        self.assertIn("has invalid slider metadata", package_sql)

    def test_seeded_slider_preferences_have_metadata(self) -> None:
        """Initial slider candidates should be numeric, bounded, and stepped."""
        seed_sql = (
            CORE_ROOT / "seed_data" / "prfdfn_preference_catalog.sql"
        ).read_text(encoding="utf-8").lower()

        for pref_key in ("tts_rate", "tts_pitch", "max_tokens"):
            with self.subTest(pref_key=pref_key):
                row_sql = self._seeded_row(seed_sql, pref_key)
                self.assertIn("'number'", row_sql)
                self.assertIn("'slider'", row_sql)

        self.assertIn("when 'tts_rate' then 0.05", seed_sql)
        self.assertIn("when 'tts_pitch' then 1", seed_sql)
        self.assertIn("when 'max_tokens' then 1", seed_sql)

    @staticmethod
    def _seeded_row(seed_sql: str, pref_key: str) -> str:
        """Return the seed row SQL for a preference key."""
        row_match = re.search(
            rf"select\s+'{re.escape(pref_key)}'.*?\n\s*from dual",
            seed_sql,
            re.DOTALL,
        )
        if row_match is None:
            raise AssertionError(f"Missing preference seed row for {pref_key}")

        return row_match.group(0)


if __name__ == "__main__":
    unittest.main()
