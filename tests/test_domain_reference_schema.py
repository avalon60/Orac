"""Verify the Core reference-domain catalogue DDL and deployment wiring."""
# Author: Clive Bostock
# Date: 02-Aug-2026
# Description: Validates the two-table Core reference-data catalogue.

from pathlib import Path
import re
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class DomainReferenceSchemaTests(unittest.TestCase):
    """Static checks for reference-domain tables and their dependencies."""

    def _read(self, relative_path: str) -> str:
        """Return a repository file as lowercase text.

        Args:
            relative_path: Repository-relative file path.

        Returns:
            Lowercase UTF-8 file contents.
        """
        path = PROJECT_ROOT / relative_path
        self.assertTrue(path.exists(), f"missing expected file: {relative_path}")
        return path.read_text(encoding="utf-8").lower()

    def test_table_abbreviations_are_registered(self) -> None:
        """Both table names have stable constraint-name abbreviations."""
        abbreviations = self._read(
            "docs/agent-guardrails/table-abbreviations.csv"
        )

        self.assertIn("orac_core,domain_codes,dom_codes", abbreviations)
        self.assertIn(
            "orac_core,domain_ref_values,dom_refval", abbreviations
        )

    def test_tables_keep_the_two_table_reference_model(self) -> None:
        """The catalogue has domain headers and directly described values."""
        domains = self._read(
            "resources/db/schema/orac_core/table/domain_codes.sql"
        )
        values = self._read(
            "resources/db/schema/orac_core/table/domain_ref_values.sql"
        )

        self.assertIn("create table orac_core.domain_codes", domains)
        self.assertIn("domain_code", domains)
        self.assertIn("display_name", domains)
        self.assertIn("system_required_yn", domains)
        self.assertIn("row_version", domains)

        self.assertIn("create table orac_core.domain_ref_values", values)
        self.assertIn("domain_code", values)
        self.assertIn("ref_value_code", values)
        self.assertIn("parent_domain_code", values)
        self.assertIn("parent_ref_value_code", values)
        self.assertIn("display_value", values)
        self.assertIn("description", values)
        self.assertIn("display_sequence", values)
        self.assertNotIn("lang_code", values)
        self.assertNotIn("flex_attribute", values)
        self.assertNotIn("ref_value_guid", values)

    def test_constraints_preserve_domain_ownership(self) -> None:
        """Reference values are unique within and linked to one domain."""
        primary_key_sql = self._read(
            "resources/db/schema/orac_core/constraint_pk/dom_refval_pk.sql"
        )
        foreign_key_sql = self._read(
            "resources/db/schema/orac_core/constraint_fk/"
            "dom_refval_dom_codes_fk1.sql"
        )
        parent_foreign_key_sql = self._read(
            "resources/db/schema/orac_core/constraint_fk/"
            "dom_refval_dom_refval_fk1.sql"
        )
        parent_pair_check_sql = self._read(
            "resources/db/schema/orac_core/constraint_other/"
            "dom_refval_ck4.sql"
        )
        self_parent_check_sql = self._read(
            "resources/db/schema/orac_core/constraint_other/"
            "dom_refval_ck5.sql"
        )
        parent_index_sql = self._read(
            "resources/db/schema/orac_core/index/"
            "dom_refval_dom_refval_fk1_idx.sql"
        )

        self.assertIn(
            "primary key (domain_code, ref_value_code)", primary_key_sql
        )
        self.assertIn(
            "references orac_core.domain_codes (domain_code)",
            foreign_key_sql,
        )
        self.assertIn(
            "foreign key (parent_domain_code, parent_ref_value_code)",
            parent_foreign_key_sql,
        )
        self.assertIn(
            "references orac_core.domain_ref_values "
            "(domain_code, ref_value_code)",
            parent_foreign_key_sql,
        )
        self.assertIn("parent_domain_code is null", parent_pair_check_sql)
        self.assertIn(
            "parent_ref_value_code is not null", parent_pair_check_sql
        )
        self.assertIn("domain_code <> parent_domain_code", self_parent_check_sql)
        self.assertIn("ref_value_code <> parent_ref_value_code", self_parent_check_sql)
        self.assertIn(
            "(parent_domain_code, parent_ref_value_code)", parent_index_sql
        )

    def test_api_layer_has_read_only_reference_projections(self) -> None:
        """The API layer can read but cannot yet mutate the catalogues."""
        domain_view = self._read(
            "resources/db/schema/orac_api/view/domain_codes_v.sql"
        )
        value_view = self._read(
            "resources/db/schema/orac_api/view/domain_ref_values_v.sql"
        )
        privilege_sql = self._read(
            "resources/db/schema/orac_api/privilege/"
            "domain_reference_core_access.sql"
        )
        grant_sql = self._read(
            "resources/db/schema/orac_api/grant/"
            "domain_reference_view_access.sql"
        )

        self.assertIn("from orac_core.domain_codes", domain_view)
        self.assertIn("from orac_core.domain_ref_values", value_view)
        for column_name in (
            "domain_code",
            "display_name",
            "description",
            "active_yn",
            "system_required_yn",
            "created_by",
            "created_on",
            "updated_by",
            "updated_on",
            "row_version",
        ):
            with self.subTest(view="domain_codes_v", column=column_name):
                self.assertIn(column_name, domain_view)

        for column_name in (
            "domain_code",
            "ref_value_code",
            "parent_domain_code",
            "parent_ref_value_code",
            "display_value",
            "description",
            "display_sequence",
            "icon",
            "color",
            "active_yn",
            "system_required_yn",
            "created_by",
            "created_on",
            "updated_by",
            "updated_on",
            "row_version",
        ):
            with self.subTest(
                view="domain_ref_values_v", column=column_name
            ):
                self.assertIn(column_name, value_view)

        self.assertNotIn("select *", domain_view)
        self.assertNotIn("select *", value_view)
        self.assertIn(
            "grant select on orac_core.domain_codes to orac_api "
            "with grant option",
            privilege_sql,
        )
        self.assertIn(
            "grant select on orac_core.domain_ref_values to orac_api "
            "with grant option",
            privilege_sql,
        )
        self.assertNotIn("grant insert", privilege_sql)
        self.assertNotIn("grant update", privilege_sql)
        self.assertNotIn("grant delete", privilege_sql)
        self.assertIn(
            "grant read on orac_api.domain_codes_v to orac_code "
            "with grant option",
            grant_sql,
        )
        self.assertIn(
            "grant read on orac_api.domain_ref_values_v to orac_code "
            "with grant option",
            grant_sql,
        )
        self.assertNotIn("to orac_apx_pub", grant_sql)

    def test_code_layer_exposes_domain_specific_reference_views(self) -> None:
        """CODE exposes historical semantics and an active-only LOV."""
        semantic_view = self._read(
            "resources/db/schema/orac_code/view/doc_class_v.sql"
        )
        lov_view = self._read(
            "resources/db/schema/orac_code/view/doc_class_lov_v.sql"
        )
        grant_sql = self._read(
            "resources/db/schema/orac_code/grant/doc_class_access.sql"
        )

        self.assertIn(
            "create or replace force view orac_code.doc_class_v",
            semantic_view,
        )
        self.assertIn(
            "ref.ref_value_code doc_class_code", semantic_view
        )
        for column_name in (
            "display_value",
            "description",
            "display_sequence",
            "icon",
            "color",
            "domain_active_yn",
            "active_yn",
            "system_required_yn",
        ):
            with self.subTest(view="doc_class_v", column=column_name):
                self.assertIn(column_name, semantic_view)
        self.assertIn("from orac_api.domain_codes_v dom", semantic_view)
        self.assertIn(
            "join orac_api.domain_ref_values_v ref", semantic_view
        )
        self.assertIn("where dom.domain_code = 'doc_class'", semantic_view)
        self.assertNotIn("where dom.active_yn = 'y'", semantic_view)

        self.assertIn(
            "create or replace force view orac_code.doc_class_lov_v",
            lov_view,
        )
        self.assertIn("doc_class_code return_value", lov_view)
        self.assertIn("from orac_code.doc_class_v", lov_view)
        self.assertIn("domain_active_yn = 'y'", lov_view)
        self.assertIn("active_yn = 'y'", lov_view)
        self.assertNotIn("order by", lov_view)

        self.assertIn(
            "grant read on orac_code.doc_class_v to orac_apx_pub",
            grant_sql,
        )
        self.assertIn(
            "grant read on orac_code.doc_class_lov_v to orac_apx_pub",
            grant_sql,
        )

    def test_context_selector_uses_domain_specific_reference_view(self) -> None:
        """The legacy context selector derives from the DOC_CLASS LOV."""
        knowledge_tag_lov = self._read(
            "resources/db/schema/orac_code/view/knowledge_tag_lov_v.sql"
        )

        self.assertNotIn("orac_api.domain_codes_v", knowledge_tag_lov)
        self.assertNotIn("orac_api.domain_ref_values_v", knowledge_tag_lov)
        self.assertIn("orac_code.doc_class_lov_v", knowledge_tag_lov)
        self.assertNotIn("order by", knowledge_tag_lov)

    def test_business_api_validates_the_fixed_active_domain(self) -> None:
        """Classification assignment fixes DOC_CLASS and checks both flags."""
        ingestion_api = self._read(
            "resources/db/schema/orac_code/package_body/"
            "knowledge_ingestion_api.sql"
        )

        self.assertIn("from orac_api.domain_codes_v dom", ingestion_api)
        self.assertIn(
            "join orac_api.domain_ref_values_v ref", ingestion_api
        )
        self.assertIn("where dom.domain_code = 'doc_class'", ingestion_api)
        self.assertIn("dom.active_yn = 'y'", ingestion_api)
        self.assertIn("ref.active_yn = 'y'", ingestion_api)

    def test_liquibase_controllers_wire_reference_access_in_order(self) -> None:
        """Core objects, API privileges, views and outgoing grants are ordered."""
        product_controller = self._read(
            "resources/db/schema/productController.xml"
        )
        api_controller = self._read(
            "resources/db/schema/orac_api/schemaController.xml"
        )
        code_controller = self._read(
            "resources/db/schema/orac_code/schemaController.xml"
        )
        recompile_sql = self._read(
            "resources/db/schema/orac_code/post_install/"
            "reference_domain_lov_views.sql"
        )

        self.assertLess(
            product_controller.index("orac_core/schemaController.xml".lower()),
            product_controller.index("orac_api/schemaController.xml".lower()),
        )
        self.assertLess(
            product_controller.index("orac_api/schemaController.xml".lower()),
            product_controller.index("orac_code/schemaController.xml".lower()),
        )
        self.assertLess(
            api_controller.index('path="privilege"'),
            api_controller.index('path="view"'),
        )
        self.assertLess(
            api_controller.index('path="view"'),
            api_controller.index('path="grant"'),
        )
        self.assertLess(
            code_controller.index('path="view"'),
            code_controller.index('path="grant"'),
        )
        self.assertLess(
            code_controller.index('path="grant"'),
            code_controller.index('path="post_install"'),
        )
        self.assertIn("alter view orac_code.doc_class_lov_v compile", recompile_sql)
        self.assertIn("alter view orac_code.timezone_lov_v compile", recompile_sql)

    def test_system_rows_and_audit_metadata_are_protected(self) -> None:
        """Triggers protect identifiers and system rows while auditing updates."""
        domain_trigger = self._read(
            "resources/db/schema/orac_core/trigger/dom_codes_bud.sql"
        )
        value_trigger = self._read(
            "resources/db/schema/orac_core/trigger/dom_refval_bud.sql"
        )

        for trigger_sql in (domain_trigger, value_trigger):
            self.assertIn("before update or delete", trigger_sql)
            self.assertIn("system_required_yn = 'y'", trigger_sql)
            self.assertIn("cannot be unprotected", trigger_sql)
            self.assertIn(":new.updated_on := systimestamp", trigger_sql)
            self.assertIn(":new.row_version :=", trigger_sql)

    def test_legacy_runner_includes_reference_domain_assets(self) -> None:
        """The SQLcl recovery runner reaches every new object component."""
        run_all = self._read("resources/db/schema/orac_core/run_all.sql")
        expected_includes = (
            "@table/domain_codes.sql",
            "@table/domain_ref_values.sql",
            "@index/dom_codes_pk.sql",
            "@index/dom_refval_pk.sql",
            "@index/dom_refval_dom_refval_fk1_idx.sql",
            "@constraint_pk/dom_codes_pk.sql",
            "@constraint_pk/dom_refval_pk.sql",
            "@constraint_fk/dom_refval_dom_codes_fk1.sql",
            "@constraint_fk/dom_refval_dom_refval_fk1.sql",
            "@constraint_other/dom_codes_ck1.sql",
            "@constraint_other/dom_refval_ck3.sql",
            "@constraint_other/dom_refval_ck4.sql",
            "@constraint_other/dom_refval_ck5.sql",
            "@comment/domain_codes.sql",
            "@comment/domain_ref_values.sql",
            "@annotation/domain_codes.sql",
            "@annotation/domain_ref_values.sql",
            "@trigger/dom_codes_bud.sql",
            "@trigger/dom_refval_bud.sql",
            "@seed_data/document_classifications.sql",
            "@seed_data/timezones.sql",
        )

        for include in expected_includes:
            with self.subTest(include=include):
                self.assertIn(include, run_all)

    def test_timezone_domains_are_seeded_with_one_parent_per_value(self) -> None:
        """The curated 38-value timezone list is grouped by six terminal values."""
        seed_sql = self._read(
            "resources/db/schema/orac_core/seed_data/timezones.sql"
        )

        self.assertIn("'timezone_group' domain_code", seed_sql)
        self.assertIn("'timezone' domain_code", seed_sql)
        for group_code in (
            "africa",
            "asia",
            "europe",
            "global",
            "north_america",
            "oceania",
        ):
            with self.subTest(group_code=group_code):
                self.assertIn(f"'{group_code}'", seed_sql)

        timezone_source = re.search(
            r"--changeset clive:seed_orac_core_timezone_values.*?using \((.*?)\) src",
            seed_sql,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(timezone_source)
        assert timezone_source is not None
        self.assertEqual(
            38,
            len(
                re.findall(
                    r"(?:select|union all select) '\S+'",
                    timezone_source.group(1),
                )
            ),
        )
        self.assertIn("'europe/london'", timezone_source.group(0))
        self.assertIn("dst.parent_domain_code = 'timezone_group'", seed_sql)

    def test_timezone_views_follow_semantic_and_lov_contracts(self) -> None:
        """Timezone and grouping views preserve hierarchy and selector rules."""
        group_view = self._read(
            "resources/db/schema/orac_code/view/timezone_group_v.sql"
        )
        group_lov = self._read(
            "resources/db/schema/orac_code/view/timezone_group_lov_v.sql"
        )
        timezone_view = self._read(
            "resources/db/schema/orac_code/view/timezone_v.sql"
        )
        timezone_lov = self._read(
            "resources/db/schema/orac_code/view/timezone_lov_v.sql"
        )
        grant_sql = self._read(
            "resources/db/schema/orac_code/grant/timezone_access.sql"
        )

        self.assertIn("where dom.domain_code = 'timezone_group'", group_view)
        self.assertIn("from orac_code.timezone_group_v", group_lov)
        self.assertIn("where dom.domain_code = 'timezone'", timezone_view)
        self.assertIn(
            "ref.parent_domain_code = 'timezone_group'", timezone_view
        )
        self.assertIn("timezone_group_code", timezone_view)
        self.assertIn("timezone_group_display_value", timezone_view)
        self.assertIn("from orac_code.timezone_v", timezone_lov)
        self.assertIn("timezone_group_domain_active_yn = 'y'", timezone_lov)
        self.assertIn("timezone_group_active_yn = 'y'", timezone_lov)
        self.assertNotIn("timezone_group_code", timezone_lov)
        for column_name in (
            "return_value",
            "display_value",
            "description",
            "display_sequence",
            "icon",
            "color",
        ):
            with self.subTest(column=column_name):
                self.assertIn(column_name, timezone_lov)

        self.assertIn(
            "grant read on orac_code.timezone_v to orac_apx_pub", grant_sql
        )
        self.assertIn(
            "grant read on orac_code.timezone_lov_v to orac_apx_pub",
            grant_sql,
        )
        self.assertNotIn("timezone_group_v to orac_apx_pub", grant_sql)

    def test_apex_and_preference_metadata_use_timezone_lov(self) -> None:
        """Both selectors use the domain-specific active-only timezone LOV."""
        apex_export = self._read("resources/db/apex/orac_apps/f1042.sql")
        preference_seed = self._read(
            "resources/db/schema/orac_core/seed_data/"
            "prfdfn_preference_catalog.sql"
        )

        self.assertIn("from timezone_lov_v", apex_export)
        self.assertIn("from orac_code.timezone_lov_v", preference_seed)
        self.assertNotIn("from timezones_v", apex_export)
        self.assertNotIn("orac_api.timezones_v", preference_seed)

    def test_legacy_timezone_table_path_is_removed(self) -> None:
        """No source DDL, grants, or table abbreviation retain TIMEZONES."""
        legacy_paths = (
            "resources/db/schema/orac_core/table/timezones.sql",
            "resources/db/schema/orac_api/view/timezones_v.sql",
            "resources/db/schema/orac_apx_pub/synonym/timezones_v.sql",
            "resources/db/schema/orac/synonym/timezones.sql",
        )
        for relative_path in legacy_paths:
            with self.subTest(path=relative_path):
                self.assertFalse((PROJECT_ROOT / relative_path).exists())

        abbreviations = self._read(
            "docs/agent-guardrails/table-abbreviations.csv"
        )
        self.assertNotIn("orac_core,timezones,tmzone", abbreviations)

    def test_document_classification_domain_is_seeded(self) -> None:
        """The fixed DOC_CLASS domain owns the supported classifications."""
        seed_sql = self._read(
            "resources/db/schema/orac_core/seed_data/"
            "document_classifications.sql"
        )

        self.assertIn("'doc_class' domain_code", seed_sql)
        for ref_value_code in (
            "raw_reference",
            "concise_knowledge_note",
            "implementation_decision_record",
            "technical_manual",
            "troubleshooting_note",
            "automation_rule_note",
        ):
            with self.subTest(ref_value_code=ref_value_code):
                self.assertIn(f"'{ref_value_code}'", seed_sql)
        self.assertNotIn("processing_profile_code", seed_sql)

    def test_strong_fit_application_domains_are_seeded(self) -> None:
        """Shared application code lists are owned by reference domains."""
        seed_sql = self._read(
            "resources/db/schema/orac_core/seed_data/"
            "application_reference_domains.sql"
        )
        expected_values = {
            "PREF_VALUE_TYPE": ("string", "number", "boolean", "json"),
            "PREF_CONTROL_TYPE": ("text", "slider", "display_only"),
            "PREF_LOV_TYPE": ("static", "sql"),
            "LLM_CONTEXT_POLICY": ("app", "model", "hybrid"),
            "USER_ALIAS_TYPE": ("email", "oauth", "os"),
            "VECTOR_DISTANCE_METRIC": ("COSINE", "L2", "MANHATTAN"),
        }

        for domain_code, ref_values in expected_values.items():
            with self.subTest(domain_code=domain_code):
                self.assertIn(f"'{domain_code.lower()}'", seed_sql)
                for ref_value in ref_values:
                    self.assertIn(f"'{ref_value.lower()}'", seed_sql)

    def test_strong_fit_consumers_use_fixed_domain_reference_pairs(self) -> None:
        """Physical consumers qualify values and constrain their domains."""
        expected_pairs = {
            "preference_definitions.sql": (
                "pref_value_type", "pref_control_type", "pref_lov_type"
            ),
            "llm_registry.sql": ("llm_context_policy",),
            "user_synonyms.sql": ("user_alias_type",),
            "message_embeddings.sql": ("vector_distance_metric",),
        }

        for table_file, prefixes in expected_pairs.items():
            table_sql = self._read(
                f"resources/db/schema/orac_core/table/{table_file}"
            )
            for prefix in prefixes:
                with self.subTest(table=table_file, prefix=prefix):
                    self.assertIn(f"{prefix}_domain_code", table_sql)
                    self.assertIn(f"{prefix}_ref_value_code", table_sql)

        knowledge_sql = self._read(
            "resources/db/schema/orac_core/table/knowledge_ingestion.sql"
        )
        self.assertIn("vector_distance_metric_domain_code", knowledge_sql)
        self.assertIn("vector_distance_metric_ref_value_code", knowledge_sql)

        user_preferences = self._read(
            "resources/db/schema/orac_core/table/user_preferences.sql"
        )
        user_preferences_fk = self._read(
            "resources/db/schema/orac_core/constraint_fk/"
            "user_pref_prfdfn_fk1.sql"
        )
        self.assertNotIn("value_type", user_preferences)
        self.assertIn("foreign key (pref_key)", user_preferences_fk)

    def test_application_code_views_and_apex_lovs_use_domain_catalogue(self) -> None:
        """Domain-specific views provide the stable APEX selector contract."""
        view_names = (
            "pref_value_type",
            "pref_control_type",
            "pref_lov_type",
            "llm_context_policy",
            "user_alias_type",
            "vector_distance_metric",
        )
        for view_name in view_names:
            semantic = self._read(
                f"resources/db/schema/orac_code/view/{view_name}_v.sql"
            )
            lov = self._read(
                f"resources/db/schema/orac_code/view/{view_name}_lov_v.sql"
            )
            with self.subTest(view=view_name):
                self.assertIn("orac_api.domain_ref_values_v", semantic)
                self.assertIn(f"from orac_code.{view_name}_v", lov)
                self.assertIn("return_value", lov)
                self.assertIn("domain_active_yn = 'y'", lov)
                self.assertIn("active_yn = 'y'", lov)

        apex_export = self._read("resources/db/apex/orac_apps/f1042.sql")
        for lov_view in view_names[:-1]:
            with self.subTest(apex_lov=lov_view):
                self.assertIn(f"from {lov_view}_lov_v", apex_export)

    def test_annotation_stage_follows_comments(self) -> None:
        """Structured table metadata installs after human-readable comments."""
        controller = self._read(
            "resources/db/schema/orac_core/schemaController.xml"
        )
        annotation_sql = self._read(
            "resources/db/schema/orac_core/annotation/"
            "knowledge_document_version_tags.sql"
        )

        self.assertLess(
            controller.index('path="comment"'),
            controller.index('path="annotation"'),
        )
        self.assertIn("code_set_ref 'codes:doc_class'", annotation_sql)
        self.assertIn(
            "rel_basis 'constraint:kn_docvtag_dom_refval_fk1'",
            annotation_sql,
        )


if __name__ == "__main__":
    unittest.main()
