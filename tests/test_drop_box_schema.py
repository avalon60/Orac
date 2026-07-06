"""Static tests for the drop-box plugin database and runtime boundary."""
# Author: Clive Bostock
# Date: 27-Jun-2026
# Description: Verifies DDL constraints, grants, varchar2 semantics, and DML boundaries.

from __future__ import annotations

from pathlib import Path
import re
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "drop_box"
SCHEMA_ROOT = PLUGIN_ROOT / "db" / "schema"


class DropBoxSchemaTests(unittest.TestCase):
    """Static checks for drop-box schema assets."""

    def test_all_new_varchar2_columns_use_character_semantics(self) -> None:
        pattern = re.compile(r"varchar2\(\s*\d+\s*\)", re.IGNORECASE)
        for path in SCHEMA_ROOT.rglob("*.sql"):
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIsNone(pattern.search(text))

    def test_status_check_constraint_lists_phase_one_statuses(self) -> None:
        text = (SCHEMA_ROOT / "constraint_other" / "drp_job_status_ck.sql").read_text(
            encoding="utf-8"
        )
        for status in (
            "queued",
            "processing",
            "handed_off",
            "completed",
            "failed",
            "quarantined",
            "skipped_duplicate",
            "skipped_disallowed_type",
            "skipped_too_large",
        ):
            self.assertIn(f"'{status}'", text)

    def test_grants_are_narrow_and_only_to_approved_consumers(self) -> None:
        grant_text = "\n".join(
            path.read_text(encoding="utf-8").lower()
            for path in (SCHEMA_ROOT / "grant").glob("*.sql")
        )

        self.assertIn("grant execute on orac_dropbox.drop_box_api to orac_plugin", grant_text)
        self.assertIn("grant select on orac_dropbox.drop_location_runtime_v to orac_plugin", grant_text)
        self.assertIn("grant execute on orac_dropbox.drop_box_admin_api to orac_apx_pub", grant_text)
        self.assertIn("grant read on orac_dropbox.drop_location_admin_v to orac_apx_pub", grant_text)
        self.assertIn("grant read on orac_dropbox.drop_location_summary_admin_v to orac_apx_pub", grant_text)
        self.assertIn("grant read on orac_dropbox.drop_job_admin_v to orac_apx_pub", grant_text)
        self.assertIn("grant read on orac_dropbox.drop_job_event_admin_v to orac_apx_pub", grant_text)
        self.assertNotIn("grant all", grant_text)
        self.assertNotIn(" to orac_core", grant_text)
        self.assertNotIn(" to orac_api", grant_text)
        self.assertNotIn(" to orac_code", grant_text)

    def test_python_runtime_contains_no_raw_orac_dropbox_dml(self) -> None:
        forbidden = (
            "insert into orac_dropbox.",
            "update orac_dropbox.",
            "delete from orac_dropbox.",
            "merge into orac_dropbox.",
            "truncate table orac_dropbox.",
        )
        for path in PLUGIN_ROOT.glob("*.py"):
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(path=path):
                for token in forbidden:
                    self.assertNotIn(token, text)

    def test_package_copies_effective_instruction_from_drop_location(self) -> None:
        package_text = (SCHEMA_ROOT / "package_body" / "drop_box_api.sql").read_text(
            encoding="utf-8"
        ).lower()

        self.assertIn("loc.processing_instruction", package_text)
        self.assertIn("loc.target_scope_type", package_text)
        self.assertIn("loc.target_scope_key", package_text)
        self.assertIn("loc.processing_profile", package_text)
        self.assertIn("join orac_dropbox.drop_processing_profile prf", package_text)
        self.assertIn("prf.active_yn = 'y'", package_text)
        self.assertIn("prf.default_instruction", package_text)
        self.assertIn("effective_processing_profile", package_text)
        self.assertIn("effective_profile_instruction", package_text)
        self.assertIn("drop location is missing an active processing profile", package_text)

    def test_table_abbreviations_are_registered(self) -> None:
        text = (
            PROJECT_ROOT / "docs" / "agent-guardrails" / "table-abbreviations.csv"
        ).read_text(encoding="utf-8")

        self.assertIn("orac_dropbox,drop_location,drp_loc", text)
        self.assertIn("orac_dropbox,drop_job,drp_job", text)
        self.assertIn("orac_dropbox,drop_job_event,drp_jobe", text)
        self.assertIn("orac_dropbox,drop_processing_profile,drp_prf", text)

    def test_admin_api_validates_drop_location_configuration(self) -> None:
        package_spec = (
            SCHEMA_ROOT / "package_spec" / "drop_box_admin_api.sql"
        ).read_text(encoding="utf-8").lower()
        package_body = (
            SCHEMA_ROOT / "package_body" / "drop_box_admin_api.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("procedure delete_location", package_spec)
        self.assertIn("p_drop_location_id", package_spec)
        self.assertIn("p_row_version", package_spec)
        self.assertIn("procedure create_location", package_body)
        self.assertIn("procedure update_location", package_body)
        self.assertIn("procedure set_enabled", package_body)
        self.assertIn("procedure delete_location", package_body)
        self.assertIn("regexp_like(coalesce(p_location_code", package_body)
        self.assertIn("target scope type must be plugin or project", package_body)
        self.assertIn("processing profile must be a lowercase profile code", package_body)
        self.assertIn("from orac_dropbox.drop_processing_profile prf", package_body)
        self.assertIn("prf.active_yn = 'y'", package_body)
        self.assertIn("processing profile is unknown or inactive", package_body)
        self.assertIn("enabled drop locations require a source path", package_body)
        self.assertIn("source path must be an absolute filesystem path", package_body)
        self.assertIn("duplicate active source paths are not allowed", package_body)
        self.assertIn("row_version = p_row_version", package_body)
        self.assertIn("from orac_dropbox.drop_job job", package_body)
        self.assertIn("job.drop_location_id = p_drop_location_id", package_body)
        self.assertIn("has job history and cannot be deleted", package_body)
        self.assertIn("delete from orac_dropbox.drop_location", package_body)

    def test_admin_views_expose_required_inspection_fields(self) -> None:
        location_view = (SCHEMA_ROOT / "view" / "drop_location_admin_v.sql").read_text(
            encoding="utf-8"
        ).lower()
        job_view = (SCHEMA_ROOT / "view" / "drop_job_admin_v.sql").read_text(
            encoding="utf-8"
        ).lower()
        event_view = (SCHEMA_ROOT / "view" / "drop_job_event_admin_v.sql").read_text(
            encoding="utf-8"
        ).lower()
        summary_view = (
            SCHEMA_ROOT / "view" / "drop_location_summary_admin_v.sql"
        ).read_text(encoding="utf-8").lower()

        for token in (
            "location_code",
            "display_name",
            "path",
            "target_scope_type",
            "target_scope_key",
            "processing_instruction",
            "ignore_patterns",
            "stability_seconds",
        ):
            self.assertIn(token, location_view)

        for token in (
            "source_filename",
            "status_code",
            "detected_on",
            "stable_on",
            "source_size_bytes",
            "source_hash",
            "error_message",
            "document_id",
            "effective_processing_profile",
            "effective_profile_instruction",
            "effective_instruction",
        ):
            self.assertIn(token, job_view)

        self.assertIn("event_type", event_view)
        self.assertIn("event_message", event_view)
        for token in (
            "event_ts",
            "drop_job_id",
            "location_code",
            "location_display_name",
            "source_filename",
            "source_path",
        ):
            self.assertIn(token, event_view)

        for token in (
            "orac-expected-columns: total_job_count, example_type",
            "total_job_count",
            "example_type",
            "recent_job_count",
            "latest_job_status",
            "last_processed_on",
            "toggle_label",
            "example_label",
        ):
            self.assertIn(token, summary_view)

    def test_processing_profile_reference_table_constraints_and_views(self) -> None:
        table_sql = (SCHEMA_ROOT / "table" / "drop_processing_profile.sql").read_text(
            encoding="utf-8"
        ).lower()
        job_table_sql = (SCHEMA_ROOT / "table" / "drop_job.sql").read_text(
            encoding="utf-8"
        ).lower()
        alter_sql = (
            SCHEMA_ROOT / "table" / "drop_job_effective_profile_instruction.sql"
        ).read_text(encoding="utf-8").lower()
        pk_sql = (SCHEMA_ROOT / "constraint_pk" / "drp_prf_pk.sql").read_text(
            encoding="utf-8"
        ).lower()
        checks_sql = (SCHEMA_ROOT / "constraint_other" / "drp_prf_checks.sql").read_text(
            encoding="utf-8"
        ).lower()
        fk_sql = (SCHEMA_ROOT / "constraint_fk" / "drp_loc_profile_fk.sql").read_text(
            encoding="utf-8"
        ).lower()
        lov_view = (SCHEMA_ROOT / "view" / "drop_processing_profile_lov_v.sql").read_text(
            encoding="utf-8"
        ).lower()
        runtime_view = (
            SCHEMA_ROOT / "view" / "drop_processing_profile_runtime_v.sql"
        ).read_text(encoding="utf-8").lower()
        config_error_view = (
            SCHEMA_ROOT / "view" / "drop_location_config_error_v.sql"
        ).read_text(encoding="utf-8").lower()
        grants = "\n".join(
            path.read_text(encoding="utf-8").lower()
            for path in (SCHEMA_ROOT / "grant").glob("*.sql")
        )

        for pattern in (
            r"profile_code\s+varchar2\(100 char\)\s+not null",
            r"display_name\s+varchar2\(200 char\)\s+not null",
            r"description\s+varchar2\(1000 char\)\s+not null",
            r"default_instruction\s+clob\s+not null",
            r"active_yn\s+varchar2\(1 char\)\s+default 'y'\s+not null",
            r"system_yn\s+varchar2\(1 char\)\s+default 'n'\s+not null",
            r"sort_order\s+number default 100\s+not null",
            r"created_by\s+varchar2\(128 char\)[\s\S]*?not null",
            r"created_on\s+timestamp with time zone default systimestamp\s+not null",
            r"updated_by\s+varchar2\(128 char\)[\s\S]*?not null",
            r"updated_on\s+timestamp with time zone default systimestamp\s+not null",
            r"row_version\s+number default 1\s+not null",
        ):
            self.assertRegex(table_sql, pattern)
        self.assertNotIn("created_at", table_sql)
        self.assertNotIn("updated_at", table_sql)

        self.assertIn("drp_prf_pk", pk_sql)
        self.assertIn("drp_prf_active_ck", checks_sql)
        self.assertIn("drp_prf_system_ck", checks_sql)
        self.assertIn("drp_prf_code_ck", checks_sql)
        self.assertIn("^[a-z][a-z0-9_]{1,99}$", checks_sql)
        self.assertIn("drop_location", fk_sql)
        self.assertIn("drop_processing_profile", fk_sql)
        self.assertIn("effective_profile_instruction clob", job_table_sql)
        self.assertIn("effective_profile_instruction", alter_sql)
        self.assertIn("where active_yn = 'y'", lov_view)
        self.assertIn("display_label", lov_view)
        self.assertIn("where active_yn = 'y'", runtime_view)
        self.assertIn("processing profile is inactive", config_error_view)
        self.assertIn("grant read on orac_dropbox.drop_processing_profile_lov_v to orac_apx_pub", grants)
        self.assertIn("grant read on orac_dropbox.drop_processing_profile_admin_v to orac_apx_pub", grants)
        self.assertIn("grant select on orac_dropbox.drop_processing_profile_runtime_v to orac_plugin", grants)
        self.assertIn("grant select on orac_dropbox.drop_location_config_error_v to orac_plugin", grants)

    def test_plugin_audit_triggers_own_local_maintenance_columns(self) -> None:
        trigger_dir = SCHEMA_ROOT / "trigger"
        for trigger_name in ("drp_loc_biu", "drp_job_biu", "drp_prf_biu"):
            with self.subTest(trigger=trigger_name):
                trigger_sql = (trigger_dir / f"{trigger_name}.sql").read_text(
                    encoding="utf-8"
                ).lower()
                self.assertIn("--liquibase formatted sql", trigger_sql)
                self.assertIn("--changeset", trigger_sql)
                self.assertIn("before insert or update", trigger_sql)
                self.assertIn("sys_context('apex$session', 'app_user')", trigger_sql)
                self.assertIn("sys_context('userenv', 'proxy_user')", trigger_sql)
                self.assertIn("sys_context('userenv', 'session_user')", trigger_sql)
                self.assertIn(":new.row_version := nvl(:old.row_version, 1) + 1", trigger_sql)

        package_text = "\n".join(
            path.read_text(encoding="utf-8").lower()
            for path in (SCHEMA_ROOT / "package_body").glob("drop_box*.sql")
        )
        self.assertNotIn("row_version   = row_version + 1", package_text)
        self.assertNotIn("row_version = row_version + 1", package_text)
        self.assertNotIn("updated_on    = systimestamp", package_text)
        self.assertNotIn("updated_by    = coalesce", package_text)

    def test_hard_object_liquibase_files_use_formatted_sql_preconditions(self) -> None:
        for folder in (
            "table",
            "index",
            "constraint_pk",
            "constraint_uc",
            "constraint_fk",
            "constraint_other",
        ):
            for path in (SCHEMA_ROOT / folder).glob("*.sql"):
                text = path.read_text(encoding="utf-8").lower()
                with self.subTest(path=path):
                    self.assertTrue(text.startswith("--liquibase formatted sql"))
                    self.assertIn("--changeset", text)
                    self.assertIn("--preconditions", text)
                    self.assertNotIn("execute immediate", text)
                    self.assertNotRegex(text, r"(?m)^declare\s*$")
                    self.assertNotIn("runonchange:true", text)

        controller_dir = PLUGIN_ROOT / "db" / "liquibase" / "controllers"
        for path in controller_dir.glob("*.xml"):
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertNotIn("<sqlFile", text)

    def test_processing_profile_seed_data_contains_required_profiles(self) -> None:
        seed_sql = (SCHEMA_ROOT / "seed_data" / "drop_processing_profiles.sql").read_text(
            encoding="utf-8"
        ).lower()

        for profile_code in (
            "raw_reference",
            "concise_knowledge_note",
            "implementation_decision_record",
            "technical_manual",
            "troubleshooting_note",
            "automation_rule_note",
        ):
            self.assertIn(profile_code, seed_sql)

        self.assertIn("invalid orac_dropbox.drop_location.processing_profile", seed_sql)
        self.assertIn("legacy compatibility profile", seed_sql)
        self.assertIn("active_yn", seed_sql)
        self.assertIn("system_yn", seed_sql)
        self.assertIn("default_instruction", seed_sql)

    def test_runtime_view_filters_locations_with_inactive_profiles(self) -> None:
        runtime_view = (SCHEMA_ROOT / "view" / "drop_location_runtime_v.sql").read_text(
            encoding="utf-8"
        ).lower()
        repository = (PLUGIN_ROOT / "repository.py").read_text(encoding="utf-8").lower()
        service = (PLUGIN_ROOT / "service.py").read_text(encoding="utf-8").lower()

        self.assertIn("join orac_dropbox.drop_processing_profile prf", runtime_view)
        self.assertIn("prf.active_yn = 'y'", runtime_view)
        self.assertIn("drop_location_config_error_v", repository)
        self.assertIn("load_configuration_errors", service)
        self.assertIn("location skipped because of configuration error", service)

    def test_disabled_example_seed_rows_use_safe_placeholders(self) -> None:
        seed_sql = (SCHEMA_ROOT / "seed_data" / "drop_location_examples.sql").read_text(
            encoding="utf-8"
        ).lower()

        self.assertIn("delete from orac_dropbox.drop_location", seed_sql)
        self.assertIn("location_code = 'ha_conclusions'", seed_sql)
        self.assertNotIn("select 'ha_conclusions'", seed_sql)
        self.assertIn("'orac_architecture_notes'", seed_sql)
        self.assertIn("when matched then", seed_sql)
        self.assertIn("where dst.enabled_yn = 'n'", seed_sql)
        self.assertIn("'/tmp/orac-dropbox-examples/orac_architecture_notes'", seed_sql)
        self.assertIn("'n'", seed_sql)
        self.assertNotIn("/home/clive", seed_sql)
        self.assertNotIn("/mnt/orac-drop", seed_sql)

    def test_readme_documents_scanner_operation_and_phase_one_limits(self) -> None:
        readme = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8").lower()

        for token in (
            "testing scanner operation",
            "/tmp/orac-dropbox-test/inbox",
            "bin/orac-plugin.sh service run drop_box",
            "bin/orac-plugin.sh service run drop_box --duration-seconds 90",
            "runtime filesystem namespace",
            "docker",
            "bind-mounted",
            "service lifecycle",
            "(drop_box, scanner)",
            "orac_code.plugin_service_api.set_service_policy",
            "orac_code.plugin_service_status_v",
            "effective_policy",
            "last_heartbeat_on",
            "foreground diagnostic",
            "not the normal operational start path",
            "scanner-test.md",
            "select location_code",
            "from orac_dropbox.drop_location",
            "from orac_dropbox.drop_job",
            "from orac_dropbox.drop_job_event",
            "testing with project docs",
            "cp docs/agent-guardrails/50-plugin-standards.md",
            "plugin-standards.md",
            "does not currently persist scanner-only skip observations",
            "missing paths",
            "ignored files",
            "unstable files",
            "disallowed extensions",
            "too-large files",
            "symlinks",
        ):
            self.assertIn(token, readme)

        self.assertIn("does not convert, summarise, chunk, embed, move", readme)
        self.assertIn("delete, or quarantine files", readme)


if __name__ == "__main__":
    unittest.main()
