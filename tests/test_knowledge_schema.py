"""Static tests for Core knowledge ingestion database assets."""
# Author: Clive Bostock
# Date: 12-Jul-2026
# Description: Verifies FK coverage, naming, and the documented Drop Box exception.

from __future__ import annotations

from pathlib import Path
import re
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORE_SCHEMA = PROJECT_ROOT / "resources" / "db" / "schema" / "orac_core"
DROP_BOX_SCHEMA = PROJECT_ROOT / "plugins" / "drop_box" / "db" / "schema"


class KnowledgeSchemaTests(unittest.TestCase):
    """Tests static schema guardrails for knowledge ingestion."""

    def test_foreign_key_matrix_is_physical(self) -> None:
        text = (CORE_SCHEMA / "constraint_fk" / "kn_knowledge_fks.sql").read_text(
            encoding="utf-8"
        ).lower()
        expected = {
            "kn_doc_kn_srcobj_fk1",
            "kn_doc_kn_docver_fk1",
            "kn_docver_kn_doc_fk1",
            "kn_docver_kn_srcobj_fk1",
            "kn_ingreq_kn_srcobj_fk1",
            "kn_ingreq_kn_doc_fk1",
            "kn_ingreq_kn_docver_fk1",
            "kn_ext_kn_docver_fk1",
            "kn_chset_kn_ext_fk1",
            "kn_chnk_kn_chset_fk1",
            "kn_chnkemb_kn_chnk_fk1",
            "kn_chnkemb_kn_embmod_fk1",
            "kn_inge_kn_ingreq_fk1",
        }
        for constraint_name in expected:
            self.assertRegex(
                text,
                rf"constraint {re.escape(constraint_name)}\s+foreign key",
            )

    def test_scope_xor_checks_are_present(self) -> None:
        text = (CORE_SCHEMA / "constraint_other" / "kn_knowledge_checks.sql").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn("constraint kn_srcobj_scope_ck", text)
        self.assertIn("constraint kn_doc_scope_ck", text)
        self.assertIn("target_scope_type in ('project', 'plugin')", text)

    def test_new_relational_id_columns_have_fks_or_documented_exception(self) -> None:
        table_text = "\n".join(
            path.read_text(encoding="utf-8").lower()
            for path in (CORE_SCHEMA / "table").glob("knowledge_*.sql")
        )
        fk_text = (CORE_SCHEMA / "constraint_fk" / "kn_knowledge_fks.sql").read_text(
            encoding="utf-8"
        ).lower()
        id_columns = set(re.findall(r"\b([a-z][a-z0-9_]*_id)\s+number\b", table_text))
        deliberate_non_fk = {"ingestion_event_id"}
        parent_or_identity = {
            "source_object_id",
            "ingestion_request_id",
            "document_id",
            "document_version_id",
            "extraction_id",
            "chunk_set_id",
            "chunk_id",
            "embedding_model_id",
            "chunk_embedding_id",
        }
        for column_name in id_columns - parent_or_identity - deliberate_non_fk:
            self.assertRegex(
                fk_text,
                rf"foreign key \([^)]*\b{re.escape(column_name)}\b[^)]*\)",
                column_name,
            )

        drop_job_text = (
            DROP_BOX_SCHEMA / "table" / "drop_job_knowledge_ingestion_request.sql"
        ).read_text(encoding="utf-8").lower()
        comment_text = (DROP_BOX_SCHEMA / "comment" / "drop_job.sql").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn("knowledge_ingestion_request_id number", drop_job_text)
        self.assertIn("deliberately not physically foreign-keyed", comment_text)

    def test_orac_code_plugin_registry_view_exposes_canonical_pk(self) -> None:
        text = (
            PROJECT_ROOT / "resources" / "db" / "schema" / "orac_code" / "view" / "plugin_registry_v.sql"
        ).read_text(encoding="utf-8").lower()
        self.assertIn("select plugin_registry_id", text)


if __name__ == "__main__":
    unittest.main()
