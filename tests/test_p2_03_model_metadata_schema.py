"""Verify the offline P2-03 controlled model metadata contract."""

# Author: Clive Bostock
# Date: 23-Aug-2026
# Description: Structural regression tests for P2-03 database metadata.

from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = PROJECT_ROOT / "resources" / "db" / "schema" / "orac_core"
API_ROOT = PROJECT_ROOT / "resources" / "db" / "schema" / "orac_api"
CODE_ROOT = PROJECT_ROOT / "resources" / "db" / "schema" / "orac_code"
SEED_PATH = CORE_ROOT / "migration" / "p2_03_metadata_seed.sql"

TABLES = {
    "llm_providers": "llm_prov",
    "llm_capabilities": "llm_cap",
    "llm_input_representations": "llm_inrep",
    "llm_input_media_types": "llm_mtype",
    "llm_provider_inputs": "llm_prvin",
    "llm_provider_input_limits": "llm_pilim",
    "llm_model_capabilities": "llm_modcap",
    "llm_model_cap_inputs": "llm_mcin",
    "llm_model_input_limits": "llm_milim",
}

CAPABILITY_CODES = {
    "text_reasoning",
    "container_inspection",
    "bounded_media_selection",
    "layout_extraction",
    "page_rendering",
    "ocr_text_extraction",
    "document_visual_interpretation",
    "technical_image_interpretation",
    "chart_visual_interpretation",
    "workbook_structured_extraction",
    "spreadsheet_calculation",
    "sheet_chart_rendering",
    "presentation_structured_extraction",
    "slide_rendering",
    "presentation_visual_interpretation",
    "audio_metadata_inspection",
    "speech_transcription",
    "speaker_diarisation",
    "audio_semantic_interpretation",
    "video_metadata_inspection",
    "subtitle_extraction",
    "keyframe_extraction",
    "video_temporal_interpretation",
}

REPRESENTATIONS = {
    "normalised_text_evidence",
    "verified_source_container",
    "verified_source_media",
    "inspection_metadata",
    "bounded_selection_manifest",
    "structured_derivative",
    "raster_image_derivative",
    "sheet_chart_render",
    "slide_render",
    "decoded_audio_selection",
    "time_aligned_text",
    "video_frame_selection",
    "video_clip_selection",
}


def _read(path: Path) -> str:
    """Read a repository text file as UTF-8.

    Args:
        path: Repository file to read.

    Returns:
        File content.
    """
    return path.read_text(encoding="utf-8")


def _seeded_call_values(sql: str, procedure: str) -> set[str]:
    """Return first string arguments passed to one seed procedure.

    Args:
        sql: Seed script content.
        procedure: Seed procedure name.

    Returns:
        Unique first string arguments.
    """
    pattern = rf"^\s*{re.escape(procedure)}\('([^']+)'"
    return set(re.findall(pattern, sql, flags=re.MULTILINE))


def test_physical_tables_and_abbreviations_are_registered() -> None:
    """Require every approved physical table and abbreviation."""
    abbreviations = _read(
        PROJECT_ROOT / "docs" / "agent-guardrails" / "table-abbreviations.csv"
    )
    for table_name, abbreviation in TABLES.items():
        assert (CORE_ROOT / "table" / f"{table_name}.sql").is_file()
        assert f"orac_core,{table_name},{abbreviation}" in abbreviations


def test_catalogues_seed_exact_contract_without_model_evidence() -> None:
    """Require exact provider, capability, and representation seeds."""
    seed_sql = _read(SEED_PATH)
    assert _seeded_call_values(seed_sql, "seed_provider") == {
        "ollama",
        "lmstudio",
    }
    assert "'openai'" not in seed_sql.lower()
    assert _seeded_call_values(seed_sql, "seed_capability") == CAPABILITY_CODES
    assert _seeded_call_values(seed_sql, "seed_representation") == REPRESENTATIONS
    assert (
        "seed_capability('video_temporal_interpretation', "
        "'Video temporal interpretation', 'SPECIALIST_INTERPRETATION', "
        "'DEFERRED'"
    ) in seed_sql
    assert "insert into orac_core.llm_model_capabilities" not in seed_sql
    assert "merge into orac_core.llm_model_capabilities" not in seed_sql


def test_controlled_domains_and_evidence_states_are_separate() -> None:
    """Require controlled classes, states, locality, limits, and operators."""
    seed_sql = _read(SEED_PATH)
    assert len(re.findall(r"seed_value\('CAPABILITY_CLASS'", seed_sql)) == 5
    assert len(re.findall(r"seed_value\('CAPABILITY_EVIDENCE_STATE'", seed_sql)) == 5
    for domain_code in (
        "CAPABILITY_LIFECYCLE",
        "PROVIDER_METADATA_STATUS",
        "PROCESSING_LOCALITY",
        "ADAPTER_SUPPORT_STATUS",
        "MIME_MATCH_KIND",
        "LIMIT_DIMENSION",
        "LIMIT_UNIT",
        "BOUND_OPERATOR",
    ):
        assert f"seed_domain('{domain_code}'" in seed_sql

    provider_checks = _read(CORE_ROOT / "constraint_other" / "llm_prvin_checks.sql")
    model_checks = _read(CORE_ROOT / "constraint_other" / "llm_modcap_checks.sql")
    assert "('API_DECLARED', 'REJECTED')" in provider_checks
    assert "'API_DECLARED'" not in model_checks
    assert "'MODEL_METADATA_VERIFIED'" in model_checks
    assert "'BOUNDED_PROBE_VERIFIED'" in model_checks
    assert "'REJECTED'" in model_checks

    corrections = _read(CORE_ROOT / "migration" / "p2_03_z_metadata_corrections.sql")
    assert "ref_value_code = 'UNMAPPED'" in corrections
    assert "active_yn = 'N'" in corrections


def test_registry_provider_integrity_is_preconditioned_and_additive() -> None:
    """Require reviewed-provider integrity and unique model identity."""
    provider_fk = _read(CORE_ROOT / "constraint_fk" / "llm_reg_llm_prov_fk1.sql")
    provider_unique = _read(CORE_ROOT / "constraint_uc" / "llm_reg_uk2.sql")
    registry_table = _read(CORE_ROOT / "table" / "llm_registry.sql")
    registry_view = _read(API_ROOT / "view" / "llm_registry_v.sql")

    assert "where not exists" in provider_fk
    assert "foreign key (provider)" in provider_fk
    assert "references orac_core.llm_providers (provider_code)" in provider_fk
    assert "unique (provider, model)" in provider_unique
    assert "modify provider not null" in registry_table
    select_clause = registry_view.split("select", maxsplit=1)[1].split(
        "from orac_core.llm_registry", maxsplit=1
    )[0]
    expected_columns = (
        "llm_id",
        "name",
        "provider",
        "model",
        "llm_context_policy_ref_value_code context_policy",
        "max_context_tokens",
        "is_enabled",
        "properties",
        "created_on",
        "created_by",
        "updated_on",
        "updated_by",
        "row_version",
    )
    positions = [select_clause.index(column) for column in expected_columns]
    assert positions == sorted(positions)


def test_evidence_identity_transition_and_input_rules_are_enforced() -> None:
    """Require exact identity, maturity, rejection, and positive-parent rules."""
    model_table = _read(CORE_ROOT / "table" / "llm_model_capabilities.sql")
    model_checks = _read(CORE_ROOT / "constraint_other" / "llm_modcap_checks.sql")
    model_trigger = _read(CORE_ROOT / "trigger" / "llm_modcap_biu.sql")
    input_trigger = _read(CORE_ROOT / "trigger" / "llm_mcin_biu.sql")

    for required_column in (
        "llm_id",
        "provider_code",
        "model_identity",
        "model_revision",
        "source_reference",
        "checked_on",
        "reviewed_by",
        "provenance",
        "fixture_identity",
        "probe_identity",
        "acceptance_criteria_ref",
        "rejection_reason",
    ):
        assert required_column in model_table
    assert "fixture_identity is not null" in model_checks
    assert "acceptance_criteria_ref is not null" in model_checks
    assert "rejection_reason is not null" in model_checks
    assert "provider = :new.provider_code" in model_trigger
    assert "model = :new.model_identity" in model_trigger
    assert "cannot be downgraded" in model_trigger
    assert "update orac_core.llm_model_cap_inputs" in model_trigger
    assert "current positive behavioural evidence" in input_trigger


def test_mime_representation_limits_and_json_boundaries_are_relational() -> None:
    """Require independent MIME/representation FKs and bounded JSON."""
    provider_fks = _read(CORE_ROOT / "constraint_fk" / "llm_prvin_fks.sql")
    model_input_fks = _read(CORE_ROOT / "constraint_fk" / "llm_mcin_fks.sql")
    media_checks = _read(CORE_ROOT / "constraint_other" / "llm_mtype_checks.sql")
    registry_checks = _read(
        CORE_ROOT / "constraint_other" / "llm_reg_ck3_p203_reserved.sql"
    )

    assert "representation_code" in provider_fks
    assert "media_type" in provider_fks
    assert "representation_code" in model_input_fks
    assert "media_type" in model_input_fks
    assert "llm_id" not in _read(CORE_ROOT / "table" / "llm_input_media_types.sql")
    assert "TYPE_WILDCARD" in media_checks
    assert "regexp_like(media_type" in media_checks
    assert "json_serialize" in _read(
        CORE_ROOT / "constraint_other" / "llm_prov_checks.sql"
    )
    assert "<= 8192" in _read(CORE_ROOT / "constraint_other" / "llm_modcap_checks.sql")
    for reserved_key in (
        "capabilities",
        "modality",
        "mime_types",
        "evidence_state",
        "locality",
        "limits",
        "model_revision",
    ):
        assert f"$.{reserved_key}" in registry_checks


def test_limit_rows_are_dimension_operator_value_unit_records() -> None:
    """Require queryable provider and model-input bounds."""
    seed_sql = _read(SEED_PATH)
    assert len(re.findall(r"seed_value\('LIMIT_DIMENSION'", seed_sql)) == 15

    for abbreviation in ("llm_pilim", "llm_milim"):
        checks = _read(CORE_ROOT / "constraint_other" / f"{abbreviation}_checks.sql")
        fks = _read(CORE_ROOT / "constraint_fk" / f"{abbreviation}_fks.sql")
        assert "limit_dimension_domain_code = 'LIMIT_DIMENSION'" in checks
        assert "bound_operator_domain_code = 'BOUND_OPERATOR'" in checks
        assert "limit_unit_domain_code = 'LIMIT_UNIT'" in checks
        assert "limit_value >= 0" in checks
        assert fks.count("references orac_core.domain_ref_values") == 3


def test_comments_annotations_grants_and_rollback_are_governed() -> None:
    """Require documented objects, narrow grants, and safe rollback policy."""
    api_grants = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((API_ROOT / "grant").glob("llm_*_code_read.sql"))
    )
    core_privileges = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((API_ROOT / "privilege").glob("llm_*_core_access.sql"))
    )

    for table_name in TABLES:
        comments = _read(CORE_ROOT / "comment" / f"{table_name}.sql")
        annotations = _read(CORE_ROOT / "annotation" / f"{table_name}.sql")
        assert f"comment on table orac_core.{table_name}" in comments
        assert f"alter table orac_core.{table_name} annotations" in annotations
        assert f"grant read on orac_api.{table_name}_v to orac_code" in api_grants
        assert f"grant select, insert, update, delete on orac_core.{table_name}" in (
            core_privileges
        )
        assert f"grant execute on orac_api.{table_name}_tapi" not in api_grants

    corrections = _read(CORE_ROOT / "migration" / "p2_03_z_metadata_corrections.sql")
    assert corrections.count("--rollback update orac_core.domain_") == 2
    assert "system_required_yn = 'N'" not in corrections


def test_safe_projections_and_controller_reachability_are_complete() -> None:
    """Require API TAPIs, safe Code views, and recovery-runner reachability."""
    run_all = _read(CORE_ROOT / "run_all.sql")
    core_controller = _read(CORE_ROOT / "schemaController.xml")
    for path_name in (
        "table",
        "index",
        "constraint_pk",
        "constraint_uc",
        "constraint_other",
        "migration",
        "constraint_fk",
        "trigger",
        "comment",
        "annotation",
    ):
        assert f'path="{path_name}"' in core_controller

    for table_name, abbreviation in TABLES.items():
        assert f"@table/{table_name}.sql" in run_all
        assert f"@constraint_pk/{abbreviation}_pk.sql" in run_all
        assert (API_ROOT / "view" / f"{table_name}_v.sql").is_file()
        assert (API_ROOT / "package_spec" / f"{table_name}_tapi.sql").is_file()
        assert (API_ROOT / "package_body" / f"{table_name}_tapi.sql").is_file()

    for view_name in (
        "llm_provider_catalogue_v",
        "llm_capability_catalogue_v",
        "llm_provider_input_support_v",
        "llm_current_model_evidence_v",
        "llm_model_input_support_v",
        "llm_input_limits_v",
    ):
        assert (CODE_ROOT / "view" / f"{view_name}.sql").is_file()
        assert not (CODE_ROOT / "grant" / f"{view_name}.sql").exists()

    compatibility_recompile = _read(
        CODE_ROOT / "post_install" / "p2_03_llm_compatibility_recompile.sql"
    )
    for object_name in (
        "orac_api.llm_registry_tapi",
        "orac_code.llm_registry_probe_v",
        "orac_code.llm_usage_breakdown_v",
    ):
        assert object_name in compatibility_recompile


def test_phase_one_prompt_and_text_local_guards_remain_unchanged() -> None:
    """Require prompt-only connector and effective TEXT/LOCAL safeguards."""
    connector_abc = _read(PROJECT_ROOT / "src" / "model" / "orac_abc.py")
    model_submission = _read(
        PROJECT_ROOT / "src" / "orac_core" / "knowledge" / "model_submission.py"
    )
    assert "def send_prompt(" in connector_abc
    assert "prompt: str" in connector_abc
    assert "attachment" not in connector_abc
    assert "images" not in connector_abc
    assert 'model_type = "TEXT"' in model_submission
    assert 'model.model_type.strip().upper() != "TEXT"' in model_submission
    assert 'model.processing_locality.strip().upper() != "LOCAL"' in model_submission
