"""Static checks for the P1-06 authorised retrieval database boundary."""

# Author: Clive Bostock
# Date: 13-Aug-2026
# Description: Verifies audit, package, grant, and locator-exclusion assets.

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "resources" / "db" / "schema"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_retrieval_package_requires_principal_scope_and_audit():
    spec = _text(SCHEMA / "orac_code/package_spec/knowledge_retrieval_api.sql")
    body = _text(SCHEMA / "orac_code/package_body/knowledge_retrieval_api.sql")
    assert "p_username" in spec
    assert "p_scope_type" in spec and "p_scope_key" in spec
    assert "rag_usage_authorization_api.authorization_result" in body
    assert "write_event(" in body
    assert "pragma autonomous_transaction" in body
    assert body.index("write_event(", body.index("if l_authorized <>")) < body.index(
        "open p_content_rows"
    )


def test_retrieval_audit_is_append_only_and_content_free():
    table = _text(SCHEMA / "orac_core/table/knowledge_retrieval_events.sql")
    trigger = _text(SCHEMA / "orac_core/trigger/kn_retev_bud.sql")
    assert "retrieved_content" not in table
    assert "storage_key" not in table and "content_uri" not in table
    assert "before update or delete" in trigger


def test_runtime_grants_only_the_authorised_retrieval_package():
    grants = _text(SCHEMA / "orac_code/grant/knowledge_retrieval_api_access.sql")
    revokes = _text(SCHEMA / "orac_code/grant/zz_p1_06_retrieval_revokes.sql")
    assert "grant execute on orac_code.knowledge_retrieval_api to orac" in grants
    assert "knowledge_searchable_chunks_v from orac" in revokes
    assert "knowledge_artefact_api from orac" in revokes
    assert "knowledge_ingestion_api from orac_plugin" in revokes
    assert "orac_apx_pub" not in grants


def test_plugin_bridge_has_no_direct_ingestion_or_retrieval_package_access():
    plugin_repository = _text(ROOT / "plugins/drop_box/repository.py")
    plugin_service = _text(ROOT / "plugins/drop_box/service.py")
    assert "knowledge_ingestion_api" not in plugin_repository
    assert "knowledge_retrieval_api" not in plugin_repository
    assert "core_handoff_available" not in plugin_service


def test_native_searchable_view_does_not_project_raw_locator():
    view = _text(SCHEMA / "orac_code/view/knowledge_native_searchable_chunks_v.sql")
    assert "ver.content_uri" not in view


def test_database_bounds_large_lobs_before_opening_content_cursor():
    body = _text(SCHEMA / "orac_code/package_body/knowledge_retrieval_api.sql")
    assert "c_max_legacy_chars" in body
    assert "c_max_chunk_chars" in body
    assert "c_max_metadata_chars" in body
    assert "retrieval_limit_exceeded" in body
    assert body.index("coalesce(l_legacy_chars") < body.index("open p_content_rows")
    assert body.index("coalesce(l_chunk_chars") < body.index("open p_content_rows")
    assert "l_include_raw_metadata = 'true'" in body


def test_p1_07_policy_audit_is_allowlisted_and_reauthorised():
    spec = _text(SCHEMA / "orac_code/package_spec/knowledge_retrieval_api.sql")
    body = _text(SCHEMA / "orac_code/package_body/knowledge_retrieval_api.sql")
    checks = _text(SCHEMA / "orac_core/constraint_other/kn_retev_checks.sql")
    comments = _text(SCHEMA / "orac_core/comment/knowledge_retrieval_events.sql")
    assert "procedure record_policy_decision" in spec
    policy_body = body[body.index("procedure record_policy_decision") :]
    assert "resolve_identity(" in policy_body
    assert "materialisation_policy_not_authorised" in policy_body
    assert "json_object(" in policy_body
    assert "p_detail_json" not in spec
    assert "materialisation_policy" in checks
    assert "prompts" in comments and "storage keys" in comments


def test_p1_07_chunk_context_and_classification_projection_are_controlled():
    body = _text(SCHEMA / "orac_code/package_body/knowledge_retrieval_api.sql")
    members = _text(SCHEMA / "orac_code/view/knowledge_retrieval_members_v.sql")
    assert "chunk_context" in body
    assert "l_context_before not between 0 and 8" in body
    assert "l_context_after not between 0 and 8" in body
    assert "classification_tags_json" in members
    assert "knowledge_document_version_tags_v" in members


def test_p1_07_recompiles_package_after_business_view_changes():
    recompile = _text(
        SCHEMA / "orac_code/post_install/knowledge_retrieval_api_recompile.sql"
    )
    controller = _text(SCHEMA / "orac_code/schemaController.xml")
    assert "recompile_orac_code_knowledge_retrieval_api_p1_07" in recompile
    assert "compile specification" in recompile
    assert "compile body" in recompile
    assert '<includeall path="post_install"' in controller


def test_p1_08_model_submission_reuses_authorised_append_only_lifecycle():
    spec = _text(SCHEMA / "orac_code/package_spec/knowledge_retrieval_api.sql")
    body = _text(SCHEMA / "orac_code/package_body/knowledge_retrieval_api.sql")
    checks = _text(SCHEMA / "orac_core/constraint_other/kn_retev_checks.sql")
    comments = _text(SCHEMA / "orac_core/comment/knowledge_retrieval_events.sql")

    assert "procedure record_model_submission_decision" in spec
    submission_body = body[body.index("procedure record_model_submission_decision") :]
    assert "resolve_identity(" in submission_body
    assert "model_submission_not_authorised" in submission_body
    assert "operation_code = 'materialisation_policy'" in submission_body
    assert "event_type_code = 'outcome'" in submission_body
    assert "status_code = 'completed'" in submission_body
    assert "if l_existing_count = 1" in submission_body
    assert "'model_submission'" in submission_body
    assert "p_detail_json" not in spec
    assert "model_submission" in checks
    assert "model-submission" in comments


def test_p1_08_submission_audit_arguments_exclude_content_and_locators():
    spec = _text(SCHEMA / "orac_code/package_spec/knowledge_retrieval_api.sql")
    procedure = spec[
        spec.index("procedure record_model_submission_decision") : spec.index(
            "procedure record_outcome"
        )
    ]

    for forbidden in (
        "content",
        "prompt",
        "model_output",
        "filename",
        "content_uri",
        "storage_key",
        "sha256",
        "path",
        "url",
    ):
        assert forbidden not in procedure


def test_plugin_hybrid_entry_point_is_structurally_self_scoped():
    spec = _text(SCHEMA / "orac_code/package_spec/knowledge_retrieval_api.sql")
    body = _text(SCHEMA / "orac_code/package_body/knowledge_retrieval_api.sql")
    plugin_spec = spec[
        spec.index("procedure open_plugin_hybrid_candidates") : spec.index(
            "procedure record_policy_decision"
        )
    ]
    plugin_body = body[
        body.index("procedure open_plugin_hybrid_candidates") : body.index(
            "procedure record_policy_decision"
        )
    ]

    assert "p_plugin_id" in plugin_spec
    assert "p_username" in plugin_spec
    assert "p_scope_type" not in plugin_spec
    assert "p_scope_key" not in plugin_spec
    assert "knowledge_scope_id" not in plugin_spec
    assert "open_hybrid_candidates_internal(" in plugin_body
    assert "p_username, 'plugin', trim(p_plugin_id)" in " ".join(plugin_body.split())
    assert "rag_usage_authorization_api.authorization_result" in body


def test_plugin_search_audit_provenance_is_bounded_and_scope_validated():
    spec = _text(SCHEMA / "orac_code/package_spec/knowledge_retrieval_api.sql")
    body = _text(SCHEMA / "orac_code/package_body/knowledge_retrieval_api.sql")

    assert "p_selected_chunk_ids_json" in spec
    assert "p_selected_chunk_ids_json is not json" in body
    assert "l_selected_count > 64" in body
    assert "l_selected_count <> l_distinct_count" in body
    assert (
        "source_object.knowledge_scope_id = l_decision.knowledge_scope_id"
        in " ".join(body.split())
    )
    assert "'executing_plugin_id'" in body
    assert "'correlation_id'" in body
    assert "'document_version_id'" in body
    assert "'chunk_id'" in body
    outcome_spec = spec[spec.index("procedure record_outcome") :]
    for forbidden in ("query", "chunk_text", "filename", "source_locator"):
        assert forbidden not in outcome_spec


def test_plugin_and_apex_principals_receive_no_core_retrieval_grants():
    grant_text = "\n".join(
        _text(path) for path in (SCHEMA / "orac_code/grant").glob("*.sql")
    )
    protected_objects = (
        "knowledge_retrieval_api",
        "knowledge_native_searchable_chunks_v",
    )
    for line in grant_text.splitlines():
        if "grant " not in line or not any(name in line for name in protected_objects):
            continue
        assert " to orac_plugin" not in line
        assert " to orac_apx" not in line


def test_cross_project_search_derives_current_authority_before_global_ranking():
    """Automatic retrieval must not accept project identity from the caller."""
    spec = _text(SCHEMA / "orac_code/package_spec/knowledge_retrieval_api.sql")
    body = _text(SCHEMA / "orac_code/package_body/knowledge_retrieval_api.sql")
    checks = _text(SCHEMA / "orac_core/constraint_other/kn_retev_checks.sql")
    procedure_spec = spec[
        spec.index("procedure open_authorised_project_candidates") : spec.index(
            "procedure open_plugin_hybrid_candidates"
        )
    ]
    procedure_body = body[
        body.index("procedure open_authorised_project_candidates") : body.index(
            "procedure open_plugin_hybrid_candidates"
        )
    ]

    assert "p_username" in procedure_spec
    assert "p_scope_type" not in procedure_spec
    assert "p_scope_key" not in procedure_spec
    assert "rag_usage_privileges_v" in procedure_body
    assert "privilege.expires_on > systimestamp" in procedure_body
    assert "project.active_yn = 'y'" in procedure_body
    assert "knowledge_scope.scope_type = 'project'" in procedure_body
    assert "fetch exact first l_semantic_limit rows only" in procedure_body
    assert "fetch first l_lexical_limit rows only" in procedure_body
    assert "authorised_project_search" in checks
