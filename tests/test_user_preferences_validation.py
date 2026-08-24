"""Static checks for user preference validation integration."""
# Author: Clive Bostock
# Date: 2026-06-25
# Description: Verifies preference validation remains package-authoritative.
# Codex-assisted modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from pathlib import Path
import re
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_ROOT = PROJECT_ROOT / "resources" / "db" / "schema"
APEX_ROOT = PROJECT_ROOT / "resources" / "db" / "apex"
API_ROOT = SCHEMA_ROOT / "orac_api"
CORE_ROOT = SCHEMA_ROOT / "orac_core"
CODE_ROOT = SCHEMA_ROOT / "orac_code"
APP_1042_EXPORT = APEX_ROOT / "orac_apps" / "f1042.sql"
API_USER_PREFERENCE_REVOKES = (
    API_ROOT / "grant" / "user_preferences_consumer_access.sql"
)
API_VIEW_GRANT_FILES = (
    API_ROOT / "grant" / "orac_api_consumer_view_access.sql",
    API_ROOT / "grant" / "orac_tapi_consumer_access.sql",
)
PREFERENCE_PRIVILEGE_RECOMPILE = (
    CODE_ROOT / "grant" / "user_preferences_privilege_recompile.sql"
)


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
            "when :p6_pref_key = ''user_location'' "
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

    def test_f1042_page6_lov_ajax_submits_control_type(self) -> None:
        """Generic LOV AJAX calls should submit their per-request guard item."""
        export_sql = APP_1042_EXPORT.read_text(encoding="utf-8").lower()

        for item_name in (
            "p6_pref_value_select_list",
            "p6_pref_value_popup_lov",
        ):
            with self.subTest(item_name=item_name):
                item_match = re.search(
                    rf"p_name=>'{item_name}'.*?"
                    r"p_ajax_items_to_submit=>'(?P<items>[^']+)'",
                    export_sql,
                    re.DOTALL,
                )

                self.assertIsNotNone(item_match)
                submitted_items = item_match.group("items").split(",")
                self.assertIn("p6_pref_key", submitted_items)
                self.assertIn("p6_control_type", submitted_items)

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

    def test_f1042_page6_value_type_anchor_uses_definition_catalog(self) -> None:
        """Page 6 should anchor value type to the authoritative definition view."""
        export_sql = APP_1042_EXPORT.read_text(encoding="utf-8").lower()

        self.assertIn(
            "l_value_type      orac_api.preference_definitions_v.value_type%type",
            export_sql,
        )
        self.assertNotIn(
            "orac_api.user_preferences_v.value_type%type",
            export_sql,
        )

    def test_f1042_page6_save_process_is_request_scoped(self) -> None:
        """Only SAVE should execute the package-authoritative update process."""
        export_sql = APP_1042_EXPORT.read_text(encoding="utf-8").lower()
        process_start = export_sql.index(
            "p_process_name=>'process form user preferences'"
        )
        process_end = export_sql.index("p_process_name=>'close dialog'", process_start)
        process_sql = export_sql[process_start:process_end]

        self.assertIn("p_process_when=>'save'", process_sql)
        self.assertIn("p_process_when_type=>'request_in_condition'", process_sql)
        self.assertIn(
            "p_process_success_message=>'user preference updated.'",
            process_sql,
        )

        page6_match = re.search(
            r"prompt --application/pages/page_00006(?P<body>.*?)"
            r"prompt --application/pages/page_00007",
            export_sql,
            re.DOTALL,
        )
        self.assertIsNotNone(page6_match)
        self.assertNotIn("p_process_type=>'native_form_dml'", page6_match.group("body"))

    def test_user_preferences_api_view_grants_are_read_only(self) -> None:
        """Consumers should not receive direct DML on the API projection."""
        for grant_path in API_VIEW_GRANT_FILES:
            grant_sql = grant_path.read_text(encoding="utf-8").lower()
            with self.subTest(grant_path=grant_path):
                for grantee in ("orac_apx_pub", "orac", "orac_code"):
                    self.assertNotRegex(
                        grant_sql,
                        rf"grant\s+[^;]*(?:insert|update|delete)[^;]*"
                        rf"on\s+orac_api\.user_preferences_v\s+to\s+{grantee}",
                    )
                    self.assertRegex(
                        grant_sql,
                        rf"grant\s+select\s+on\s+orac_api\.user_preferences_v\s+"
                        rf"to\s+{grantee}",
                    )

    def test_user_preferences_api_view_upgrade_revokes_direct_dml(self) -> None:
        """Existing deployments should remove every legacy consumer DML grant."""
        revoke_sql = API_USER_PREFERENCE_REVOKES.read_text(
            encoding="utf-8"
        ).lower()

        for grantee in ("orac_apx_pub", "orac", "orac_code"):
            for privilege in ("insert", "update", "delete"):
                with self.subTest(grantee=grantee, privilege=privilege):
                    self.assertIn(
                        f"revoke {privilege} on orac_api.user_preferences_v "
                        f"from {grantee};",
                        revoke_sql,
                    )
                    self.assertIn(
                        f"grantee = '{grantee}' and privilege = '{privilege}'",
                        revoke_sql,
                    )
                    grant_option = (
                        " with grant option" if grantee == "orac_code" else ""
                    )
                    self.assertIn(
                        f"--rollback grant {privilege} on "
                        f"orac_api.user_preferences_v to {grantee}"
                        f"{grant_option};",
                        revoke_sql,
                    )

    def test_preference_objects_recompile_after_api_view_revokes(self) -> None:
        """Privilege migration should leave dependent preference objects valid."""
        recompile_sql = PREFERENCE_PRIVILEGE_RECOMPILE.read_text(
            encoding="utf-8"
        ).lower()

        expected_compiles = (
            "alter package orac_code.user_preferences_api compile;",
            "alter package orac_code.user_preferences_api compile body;",
            "alter package orac_code.orac_prefs_seed compile body;",
            "alter trigger orac_code.user_pref_v_iud compile;",
        )
        for compile_statement in expected_compiles:
            with self.subTest(compile_statement=compile_statement):
                self.assertIn(compile_statement, recompile_sql)

        self.assertEqual(4, recompile_sql.count("status = 'invalid'"))

    def test_weather_location_key_is_not_runtime_supported(self) -> None:
        """The retired location key should only remain in seed migration SQL."""
        retired_key = "weather" + "_location"
        checked_paths = (
            PROJECT_ROOT / "src/controller/orac.py",
            PROJECT_ROOT / "src/model/plugin_runtime.py",
            PROJECT_ROOT / "plugins/weather/plugin.py",
            CODE_ROOT / "package_body/preference_lov_api.sql",
            CODE_ROOT / "view/user_preferences_display_v.sql",
            APP_1042_EXPORT,
        )

        for path in checked_paths:
            with self.subTest(path=path):
                self.assertNotIn(
                    retired_key,
                    path.read_text(encoding="utf-8"),
                )

    def test_display_view_sources_value_type_from_preference_definition(self) -> None:
        """The display view should use metadata after value_type left user values."""
        display_view_sql = (
            CODE_ROOT / "view/user_preferences_display_v.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertNotIn("p.value_type", display_view_sql)
        self.assertIn("d.value_type", display_view_sql)
        for value_type in ("string", "number", "boolean", "json"):
            self.assertIn(
                f"when d.value_type = '{value_type}' then",
                display_view_sql,
            )

    def test_consumer_preference_view_access_is_read_only(self) -> None:
        """Consumer schemas should write preferences through the business API."""
        grant_sql = (
            CODE_ROOT / "grant/orac_code_consumer_view_access.sql"
        ).read_text(encoding="utf-8").lower()
        revoke_sql = (
            CODE_ROOT / "grant/user_preferences_consumer_access.sql"
        ).read_text(encoding="utf-8").lower()

        for grantee in ("orac_apx_pub", "orac"):
            self.assertIn(
                f"grant select on orac_code.user_preferences_v to {grantee};",
                grant_sql,
            )
            self.assertNotIn(
                "grant select, insert, update, delete on "
                f"orac_code.user_preferences_v to {grantee};",
                grant_sql,
            )
            for privilege in ("insert", "update", "delete"):
                self.assertIn(
                    f"revoke {privilege} on orac_code.user_preferences_v "
                    f"from {grantee};",
                    revoke_sql,
                )

    def test_preference_slider_metadata_constraints_are_authoritative(self) -> None:
        """Database metadata should reject invalid slider definitions."""
        control_check_sql = (
            CORE_ROOT / "constraint_other" / "prfdfn_ck2_pref_control_type.sql"
        ).read_text(encoding="utf-8").lower()
        slider_check_sql = (
            CORE_ROOT / "constraint_other" / "prfdfn_ck7.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("pref_control_type_domain_code = 'pref_control_type'", control_check_sql)
        self.assertIn("pref_control_type_ref_value_code <> 'slider'", slider_check_sql)
        self.assertIn("pref_value_type_ref_value_code = 'number'", slider_check_sql)
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
