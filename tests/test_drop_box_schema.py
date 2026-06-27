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

    def test_table_abbreviations_are_registered(self) -> None:
        text = (
            PROJECT_ROOT / "docs" / "agent-guardrails" / "table-abbreviations.csv"
        ).read_text(encoding="utf-8")

        self.assertIn("orac_dropbox,drop_location,drp_loc", text)
        self.assertIn("orac_dropbox,drop_job,drp_job", text)
        self.assertIn("orac_dropbox,drop_job_event,drp_jobe", text)

    def test_admin_api_validates_drop_location_configuration(self) -> None:
        package_body = (
            SCHEMA_ROOT / "package_body" / "drop_box_admin_api.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("procedure create_location", package_body)
        self.assertIn("procedure update_location", package_body)
        self.assertIn("procedure set_enabled", package_body)
        self.assertIn("regexp_like(coalesce(p_location_code", package_body)
        self.assertIn("target scope type must be plugin or project", package_body)
        self.assertIn("processing profile must be lowercase", package_body)
        self.assertIn("enabled drop locations require a source path", package_body)
        self.assertIn("source path must be an absolute filesystem path", package_body)
        self.assertIn("duplicate active source paths are not allowed", package_body)
        self.assertIn("row_version = p_row_version", package_body)

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
        ):
            self.assertIn(token, job_view)

        self.assertIn("event_type", event_view)
        self.assertIn("event_message", event_view)

    def test_disabled_example_seed_rows_use_safe_placeholders(self) -> None:
        seed_sql = (SCHEMA_ROOT / "seed_data" / "drop_location_examples.sql").read_text(
            encoding="utf-8"
        ).lower()

        self.assertIn("'ha_conclusions'", seed_sql)
        self.assertIn("'orac_architecture_notes'", seed_sql)
        self.assertIn("'/__orac_dropbox_examples__/home_assistant_conclusions'", seed_sql)
        self.assertIn("'/__orac_dropbox_examples__/orac_architecture_notes'", seed_sql)
        self.assertIn("'n'", seed_sql)
        self.assertNotIn("/home/clive", seed_sql)
        self.assertNotIn("/mnt/orac-drop", seed_sql)


if __name__ == "__main__":
    unittest.main()
