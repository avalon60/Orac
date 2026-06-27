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

    def test_grants_are_narrow_and_only_to_orac_plugin(self) -> None:
        grant_text = "\n".join(
            path.read_text(encoding="utf-8").lower()
            for path in (SCHEMA_ROOT / "grant").glob("*.sql")
        )

        self.assertIn("grant execute on orac_dropbox.drop_box_api to orac_plugin", grant_text)
        self.assertIn("grant select on orac_dropbox.drop_location_runtime_v to orac_plugin", grant_text)
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


if __name__ == "__main__":
    unittest.main()
