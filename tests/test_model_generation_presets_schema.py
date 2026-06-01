"""Static checks for model generation preset schema artifacts.

# Author: Clive Bostock
# Date: 2026-05-23
# Description: Verifies model generation preset DDL and seed conventions.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_ROOT = PROJECT_ROOT / "resources" / "db" / "schema"
CORE_ROOT = SCHEMA_ROOT / "orac_core"


class ModelGenerationPresetSchemaTests(unittest.TestCase):
    """Static tests for model preset database artifacts."""

    def test_table_uses_character_semantics_for_new_varchar2_columns(self) -> None:
        table_sql = (
            CORE_ROOT / "table" / "model_generation_presets.sql"
        ).read_text(encoding="utf-8")

        varchar2_declarations = re.findall(r"varchar2\([^)]*\)", table_sql)

        self.assertTrue(varchar2_declarations)
        for declaration in varchar2_declarations:
            self.assertRegex(declaration, r"varchar2\(\d+\s+char\)")

    def test_model_preset_table_excludes_runtime_context_and_stop_sequences(self) -> None:
        table_sql = (
            CORE_ROOT / "table" / "model_generation_presets.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertNotIn("num_ctx", table_sql)
        self.assertNotIn("stop_sequence", table_sql)
        self.assertNotIn("stop_sequences", table_sql)

    def test_seed_data_contains_required_system_presets(self) -> None:
        seed_sql = (
            CORE_ROOT / "seed_data" / "model_generation_presets.sql"
        ).read_text(encoding="utf-8")

        for preset_code in (
            "DEFAULT",
            "PRECISE",
            "PRECISE_DETAILED",
            "BALANCED",
            "CREATIVE",
            "CODING",
            "LONGFORM",
            "DETERMINISTIC_DEBUG",
        ):
            self.assertIn(f"'{preset_code}'", seed_sql)

    def test_personality_foreign_key_references_model_presets(self) -> None:
        fk_sql = (
            CORE_ROOT / "constraint_fk" / "orpers_model_preset_fk1.sql"
        ).read_text(encoding="utf-8").lower()
        personality_table_sql = (
            CORE_ROOT / "table" / "orac_personalities.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("model_preset_id       number", personality_table_sql)
        self.assertIn("foreign key (model_preset_id)", fk_sql)
        self.assertIn(
            "references orac_core.model_generation_presets (model_preset_id)",
            fk_sql,
        )


if __name__ == "__main__":
    unittest.main()
