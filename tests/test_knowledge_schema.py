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
        deliberate_non_fk = {"ingestion_event_id", "target_id"}
        parent_or_identity = {
            "source_object_id",
            "ingestion_request_id",
            "document_id",
            "document_version_id",
            "extraction_id",
            "chunk_set_id",
            "chunk_id",
            "embedding_model_id",
            "chunk_vector_embedding_id",
            "embedding_profile_id",
            "reembedding_run_id",
            "knowledge_scope_id",
            "artefact_id",
            "retrieval_event_id",
        }
        for constraint_name in (
            "kn_docvtag_kn_docver_fk1",
            "kn_docvtag_dom_refval_fk1",
        ):
            self.assertRegex(
                fk_text,
                rf"constraint {constraint_name}\s+foreign key",
            )
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

    def test_native_searchable_chunks_view_uses_the_active_profile(self) -> None:
        view_sql = (
            (CORE_CODE_SCHEMA / "view" / "knowledge_native_searchable_chunks_v.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertIn(
            "create or replace force view orac_code.knowledge_native_searchable_chunks_v",
            view_sql,
        )
        for token in (
            "knowledge_searchable_chunk_content_v",
            "knowledge_embedding_activations_v",
            "knowledge_embedding_profiles_v",
            "knowledge_chunk_vector_embeddings_v",
            "embedding_text_sha256 = chunk.chunk_content_sha256",
            "vector_dimension_count(emb.embedding_vector) = model.dimensions",
            "profile.storage_layout_code",
        ):
            self.assertIn(token, view_sql)
        self.assertNotIn("model.dimensions = 768", view_sql)
        self.assertNotIn("knowledge_chunk_embeddings_v", view_sql)

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
            "vector_dimension_count(rec.embedding_vector) <> rec.dimensions",
            "knowledge_embedding_activations_v",
            "p_embedding_profile_id in number",
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
        conflict_start = package_sql.index("l_conflicting_fields := null;")
        conflict_end = package_sql.index("exception", conflict_start)
        conflict_sql = package_sql[conflict_start:conflict_end]
        conflicting_fields = (
            "source_object_id",
            "content_uri",
            "mime_type",
            "original_filename",
            "byte_size",
            "source_modified_on",
            "source_format_code",
        )
        previous_position = -1
        for field_name in conflicting_fields:
            call = f"append_conflicting_field(l_conflicting_fields, '{field_name}')"
            position = conflict_sql.index(call)
            self.assertGreater(position, previous_position)
            previous_position = position
        self.assertIn(
            "'conflicting fields: ' || l_conflicting_fields || '.'",
            conflict_sql,
        )
        self.assertIn(
            "'conflicting fields: source_modified_on.'",
            package_sql,
        )
        for value_expression in (
            "|| l_existing_content_uri",
            "|| l_existing_mime_type",
            "|| l_existing_original_filename",
            "|| l_existing_byte_size",
            "|| l_existing_source_modified_on",
            "|| l_existing_source_format_code",
        ):
            self.assertNotIn(value_expression, conflict_sql)
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

    def test_document_classifications_use_domain_reference_keys(self) -> None:
        """Classifications use the fixed DOC_CLASS composite reference."""
        table_sql = (
            (CORE_SCHEMA / "table" / "knowledge_document_version_tags.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        primary_key_sql = (
            (CORE_SCHEMA / "constraint_pk" / "kn_docvtag_pk.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        foreign_key_sql = (
            (CORE_SCHEMA / "constraint_fk" / "kn_docvtag_dom_refval_fk1.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        check_sql = (
            (CORE_SCHEMA / "constraint_other" / "kn_docvtag_ck1.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        index_sql = (
            (CORE_SCHEMA / "index" / "kn_docvtag_dom_refval_fk1_idx.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        self.assertIn(
            "default on null 'doc_class' not null",
            " ".join(table_sql.split()),
        )
        self.assertIn("doc_class_ref_value_code", table_sql)
        self.assertNotIn("knowledge_tag_id", table_sql)
        self.assertNotIn("knowledge_document_version_tag_id", table_sql)
        self.assertIn(
            "primary key (document_version_id, doc_class_domain_code, "
            "doc_class_ref_value_code)",
            " ".join(primary_key_sql.split()),
        )
        self.assertIn(
            "foreign key (doc_class_domain_code, doc_class_ref_value_code)",
            " ".join(foreign_key_sql.split()),
        )
        self.assertIn(
            "references orac_core.domain_ref_values (domain_code, ref_value_code)",
            " ".join(foreign_key_sql.split()),
        )
        self.assertIn("doc_class_domain_code = 'doc_class'", check_sql)
        self.assertIn(
            "(doc_class_domain_code, doc_class_ref_value_code)",
            " ".join(index_sql.split()),
        )
        self.assertFalse((CORE_SCHEMA / "table" / "knowledge_tags.sql").exists())

    def test_normalised_artefacts_are_atomic_and_own_chunk_lineage(self) -> None:
        """Managed output sets enforce identity, completeness, and lineage."""
        table_sql = (
            (CORE_SCHEMA / "table" / "knowledge_artefacts.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        migration_sql = (
            (CORE_SCHEMA / "migration" / "knowledge_chunk_set_artefact_lineage.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        foreign_key_sql = (
            (CORE_SCHEMA / "constraint_fk" / "kn_artf_fks.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        package_sql = (
            (CORE_CODE_SCHEMA / "package_body" / "knowledge_artefact_api.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        searchable_sql = (
            (CORE_CODE_SCHEMA / "view" / "knowledge_searchable_chunk_content_v.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        for column in (
            "artefact_id",
            "extraction_id",
            "artefact_role_code",
            "content_sha256",
            "storage_key",
            "member_ordinal",
            "metadata_json",
        ):
            self.assertIn(column, table_sql)
        self.assertIn("metadata_json     json", table_sql)
        self.assertIn("source_artefact_id number", migration_sql)
        self.assertIn(
            "source_artefact_key number generated always as "
            "(nvl(source_artefact_id, -1)) virtual",
            " ".join(migration_sql.split()),
        )
        self.assertIn("source_artefact_key", migration_sql)
        self.assertIn(
            "foreign key (extraction_id, source_artefact_id)",
            " ".join(foreign_key_sql.split()),
        )
        self.assertIn(
            "references orac_core.knowledge_artefacts (extraction_id, artefact_id)",
            " ".join(foreign_key_sql.split()),
        )
        self.assertIn("savepoint knowledge_artefact_set_registration", package_sql)
        self.assertIn("rollback to knowledge_artefact_set_registration", package_sql)
        self.assertIn("member.byte_size <> l_expected_byte_size", package_sql)
        self.assertIn("assert_complete_set(p_extraction_id)", package_sql)
        self.assertIn("artset.complete_yn = 'y'", searchable_sql)
        self.assertIn("chs.source_artefact_id is null", searchable_sql)
        self.assertIn("not exists", searchable_sql)

    def test_knowledge_migration_api_is_runtime_only_and_data_neutral(self) -> None:
        """P1-05 uses a narrow API and never runs data migration at deployment."""
        package_spec = (
            (CORE_CODE_SCHEMA / "package_spec" / "knowledge_migration_api.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        package_body = (
            (CORE_CODE_SCHEMA / "package_body" / "knowledge_migration_api.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        grant_sql = (
            (CORE_CODE_SCHEMA / "grant" / "knowledge_migration_api_access.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        trigger_sql = (
            (CORE_SCHEMA / "trigger" / "kn_knowledge_bu.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        for name in (
            "open_backfill_candidates",
            "open_raw_locator_candidates",
            "backfill_extraction",
            "migrate_raw_locator",
        ):
            self.assertIn(name, package_spec)
        self.assertNotIn("commit;", package_body)
        self.assertIn(
            "grant execute on orac_code.knowledge_migration_api to orac;",
            grant_sql,
        )
        self.assertNotIn("orac_plugin", grant_sql)
        self.assertIn("called_from_migration_api", trigger_sql)
        self.assertIn("'sha256:' || :old.content_sha256", trigger_sql)
        self.assertIn("updating('content_uri')", trigger_sql)

    def test_reconciliation_api_is_read_only_runtime_only_and_bounded(self) -> None:
        """P1-09 exposes only bounded read inventories to the ORAC runtime."""
        package_spec = (
            (CORE_CODE_SCHEMA / "package_spec" / "knowledge_reconciliation_api.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        package_body = (
            (CORE_CODE_SCHEMA / "package_body" / "knowledge_reconciliation_api.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        grant_sql = (
            (CORE_CODE_SCHEMA / "grant" / "knowledge_reconciliation_api_access.sql")
            .read_text(encoding="utf-8")
            .lower()
        )

        for procedure in (
            "open_registered_references",
            "open_lineage_inventory",
        ):
            self.assertIn(procedure, package_spec)
            self.assertIn(procedure, package_body)
        for forbidden in (
            "insert into",
            "update orac_",
            "delete from",
            "merge into",
            "commit;",
            "autonomous_transaction",
            "orac_core.",
        ):
            self.assertNotIn(forbidden, package_body)
        self.assertIn("c_max_inventory_rows", package_body)
        self.assertIn("order by reference_kind, reference_id", package_body)
        self.assertIn("order by lineage_kind, lineage_id", package_body)
        self.assertIn(
            "grant execute on orac_code.knowledge_reconciliation_api to orac;",
            grant_sql,
        )
        self.assertNotIn("orac_plugin", grant_sql)
        self.assertNotIn("orac_apx_pub", grant_sql)

    def test_tag_writes_use_tapi_and_plugin_validation_bridge(self) -> None:
        ingestion_sql = (
            (CORE_CODE_SCHEMA / "package_body" / "knowledge_ingestion_api.sql")
            .read_text(encoding="utf-8")
            .lower()
        )
        api_grants = (
            (
                CORE_API_SCHEMA
                / "grant"
                / "knowledge_document_version_tags_api_access.sql"
            )
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
            "knowledge_tags_v",
            api_grants,
        )
        self.assertIn(
            "grant read on orac_api.knowledge_document_version_tags_v "
            "to orac_code with grant option;",
            api_grants,
        )
        self.assertNotIn("tag_code", ingestion_sql)
        self.assertNotIn("tag_code", bridge_body)
        self.assertIn("doc_class_ref_value_code", ingestion_sql)
        self.assertIn("domain_code = 'doc_class'", ingestion_sql)
        self.assertIn("orac_code.knowledge_tag_lov_v", bridge_body)
        self.assertIn(
            "orac_plugin.knowledge_tag_validation_api.canonical_active_tags",
            drop_box_admin,
        )
        manifest = json.loads(DROP_BOX_MANIFEST.read_text(encoding="utf-8"))
        dependencies = manifest["database"]["schemas"][0]["bridge_api_dependencies"]
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
