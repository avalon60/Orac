"""Static tests for Core knowledge ingestion database assets."""

# Author: Clive Bostock
# Date: 12-Jul-2026
# Description: Verifies FK coverage, naming, and the documented Drop Box exception.

from __future__ import annotations

from pathlib import Path
import json
import re
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORE_SCHEMA = PROJECT_ROOT / "resources" / "db" / "schema" / "orac_core"
CORE_CODE_SCHEMA = PROJECT_ROOT / "resources" / "db" / "schema" / "orac_code"
CORE_API_SCHEMA = PROJECT_ROOT / "resources" / "db" / "schema" / "orac_api"
PLUGIN_BRIDGE_SCHEMA = PROJECT_ROOT / "resources" / "db" / "schema" / "orac_plugin"
ORAC_SCHEMA = PROJECT_ROOT / "resources" / "db" / "schema" / "orac"
DROP_BOX_SCHEMA = PROJECT_ROOT / "plugins" / "drop_box" / "db" / "schema"
DROP_BOX_MANIFEST = PROJECT_ROOT / "plugins" / "drop_box.json"


class KnowledgeSchemaTests(unittest.TestCase):
    """Tests static schema guardrails for knowledge ingestion."""

    def test_foreign_key_matrix_is_physical(self) -> None:
        text = (
            (CORE_SCHEMA / "constraint_fk" / "kn_knowledge_fks.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
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
        text = (
            (CORE_SCHEMA / "constraint_other" / "knowledge_scope_privilege_checks.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        self.assertIn("constraint kn_scope_ck1", text)
        self.assertIn("scope_type = 'project' and project_id is not null", text)
        self.assertIn("scope_type = 'plugin' and project_id is null", text)

    def test_new_relational_id_columns_have_fks_or_documented_exception(self) -> None:
        table_text = "\n".join(
            path.read_text(encoding="utf-8").lower()
            for path in (CORE_SCHEMA / "table").glob("knowledge_*.sql")
        )
        fk_text = "\n".join(
            path.read_text(encoding="utf-8").lower()
            for path in (CORE_SCHEMA / "constraint_fk").glob("*.sql")
        )
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
            "knowledge_scope_id",
            "knowledge_tag_id",
            "knowledge_document_version_tag_id",
        }
        for constraint_name in ("kn_docvtag_docver_fk", "kn_docvtag_tag_fk"):
            self.assertIn(f"constraint {constraint_name} foreign key", fk_text)
        for column_name in id_columns - parent_or_identity - deliberate_non_fk:
            self.assertRegex(
                fk_text,
                rf"foreign key \([^)]*\b{re.escape(column_name)}\b[^)]*\)",
                column_name,
            )

        drop_job_text = (
            (DROP_BOX_SCHEMA / "table" / "drop_job_knowledge_ingestion_request.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        comment_text = (
            (DROP_BOX_SCHEMA / "comment" / "drop_job.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        self.assertIn("knowledge_ingestion_request_id number", drop_job_text)
        self.assertIn("deliberately not physically foreign-keyed", comment_text)

    def test_orac_code_plugin_registry_view_exposes_canonical_pk(self) -> None:
        text = (
            (
                PROJECT_ROOT
                / "resources"
                / "db"
                / "schema"
                / "orac_code"
                / "view"
                / "plugin_registry_v.sql"
            )
            .read_text(encoding="utf-8")
            .lower()
        )
        self.assertIn("select plugin_registry_id", text)

    def test_searchable_chunks_view_exposes_scope_and_vector_metadata(self) -> None:
        view_sql = (
            (CORE_CODE_SCHEMA / "view" / "knowledge_searchable_chunks_v.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        grant_sql = (
            (CORE_CODE_SCHEMA / "grant" / "orac_code_consumer_view_access.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        synonym_sql = (
            (ORAC_SCHEMA / "synonym" / "knowledge_searchable_chunks_v.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertIn(
            "create or replace force view orac_code.knowledge_searchable_chunks_v",
            view_sql,
        )
        for token in (
            "target_scope_type",
            "target_scope_key",
            "source_object_id",
            "document_id",
            "document_version_id",
            "chunk_id",
            "chunk_text",
            "embedding_model_identifier",
            "embedding_dimensions",
            "embedding_vector",
            "req.status_code = 'completed'",
        ):
            self.assertIn(token, view_sql)
        self.assertIn(
            "grant read on orac_code.knowledge_searchable_chunks_v to orac;",
            grant_sql,
        )
        self.assertIn(
            "create or replace synonym orac.knowledge_searchable_chunks_v",
            synonym_sql,
        )

    def test_complete_request_invariant_is_fail_closed(self) -> None:
        package_sql = (
            (CORE_CODE_SCHEMA / "package_body" / "knowledge_ingestion_api.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        for token in (
            "cannot complete a knowledge request",
            "l_chunk_count = 0",
            "l_missing_embedding_count > 0",
            "l_bad_vector_count > 0",
            "l_expected_model_key <> l_model_key",
            "vector_dimension(rec.embedding_vector)",
            "empty or whitespace-only chunk",
        ):
            self.assertIn(token, package_sql)

    def test_legacy_source_rekey_is_audited_and_conservative(self) -> None:
        package_sql = (
            (CORE_CODE_SCHEMA / "package_body" / "knowledge_ingestion_api.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        for token in (
            "source_rekeyed",
            "ambiguous legacy drop box source",
            "drop_box:drop_job:%",
            "knowledge_scope_id = l_knowledge_scope_id",
            "add_event_for_source",
        ):
            self.assertIn(token, package_sql)

    def test_ingestion_validates_canonical_active_scope_before_writes(self) -> None:
        package_sql = (
            (CORE_CODE_SCHEMA / "package_body" / "knowledge_ingestion_api.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        validation_call = package_sql.index(
            "assert_canonical_scope(l_scope_type, l_scope_key);"
        )
        first_source_write = package_sql.index(
            "update orac_api.knowledge_source_objects_v"
        )
        self.assertLess(validation_call, first_source_write)
        for token in (
            "orac_code.knowledge_scope_api.scope_status",
            "orac_code.knowledge_scope_api.resolve_scope_id",
            "l_knowledge_scope_id",
            "unknown, inactive, or not runtime eligible",
        ):
            self.assertIn(token, package_sql)

    def test_raw_document_version_metadata_is_immutable_on_reuse(self) -> None:
        package_sql = (
            (CORE_CODE_SCHEMA / "package_body" / "knowledge_ingestion_api.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        trigger_sql = (
            (CORE_SCHEMA / "trigger" / "kn_knowledge_bu.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertIn(
            "l_content_uri <> 'sha256:' || l_content_sha256",
            package_sql,
        )
        self.assertIn("equivalent_storage_key(", package_sql)
        self.assertIn("immutable raw document-version metadata", package_sql)
        self.assertNotIn(
            "update orac_api.knowledge_document_versions_v",
            package_sql,
        )
        self.assertIn(
            "before update or delete on orac_core.knowledge_document_versions",
            trigger_sql,
        )
        for column_name in (
            "document_version_id",
            "document_id",
            "source_object_id",
            "content_sha256",
            "content_uri",
            "mime_type",
            "original_filename",
            "byte_size",
            "source_modified_on",
            "source_format_code",
            "created_by",
            "created_on",
        ):
            self.assertIn(
                f"updating('{column_name}')",
                trigger_sql,
            )
        self.assertIn("if deleting", trigger_sql)

    def test_tag_writes_use_tapi_and_plugin_validation_bridge(self) -> None:
        ingestion_sql = (
            (CORE_CODE_SCHEMA / "package_body" / "knowledge_ingestion_api.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        api_grants = (
            (CORE_API_SCHEMA / "grant" / "knowledge_tag_api_access.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        bridge_body = (
            (PLUGIN_BRIDGE_SCHEMA / "package_body" / "knowledge_tag_validation_api.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        drop_box_admin = (
            (DROP_BOX_SCHEMA / "package_body" / "drop_box_admin_api.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertIn(
            "orac_api.knowledge_document_version_tags_tapi.ins",
            ingestion_sql,
        )
        self.assertNotIn(
            "grant select, insert, update, delete on orac_api.knowledge_tags_v",
            api_grants,
        )
        self.assertIn("orac_code.knowledge_tag_lov_v", bridge_body)
        self.assertIn(
            "orac_plugin.knowledge_tag_validation_api.canonical_active_tags",
            drop_box_admin,
        )
        manifest = json.loads(DROP_BOX_MANIFEST.read_text(encoding="utf-8"))
        dependencies = manifest["database"]["schemas"][0][
            "bridge_api_dependencies"
        ]
        self.assertIn("knowledge_tag_validation", dependencies)
        self.assertFalse(
            (
                PLUGIN_BRIDGE_SCHEMA
                / "grant"
                / "knowledge_tag_validation_to_dropbox.sql"
            ).exists()
        )


if __name__ == "__main__":
    unittest.main()
