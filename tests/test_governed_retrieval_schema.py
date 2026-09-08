"""Static schema-contract tests for Phase 2A governed retrieval."""

# Author: Clive Bostock
# Date: 2026-08-29
# Description: Verifies capability governance and content-free durable audit wiring.

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "resources" / "db" / "schema"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_capability_definitions_do_not_self_grant_model_evidence() -> None:
    seed = _text(
        SCHEMA / "orac_core" / "migration" / "governed_retrieval_capabilities.sql"
    )
    assert "structured_tool_calling" in seed
    assert "streamed_structured_tool_calling" in seed
    assert "merge into orac_core.llm_capabilities" in seed
    assert "llm_model_capabilities" not in seed


def test_host_instruction_forbids_simulated_tool_results() -> None:
    """The live path must tell models not to imitate retrieval in text."""
    protocol = _text(ROOT / "src" / "orac_core" / "governed_retrieval" / "protocol.py")
    controller = _text(ROOT / "src" / "controller" / "orac.py")

    assert "must issue exactly" in protocol
    assert "never claim retrieval occurred" in protocol
    assert "unless an actual tool result appears" in protocol
    assert "governed_retrieval_system_instruction" in controller
    assert "+ instruction_tokens" in controller


def test_existing_audit_boundary_accepts_only_allowlisted_governed_metadata() -> None:
    checks = _text(SCHEMA / "orac_core" / "constraint_other" / "kn_retev_checks.sql")
    spec = _text(SCHEMA / "orac_code" / "package_spec" / "knowledge_retrieval_api.sql")
    body = _text(SCHEMA / "orac_code" / "package_body" / "knowledge_retrieval_api.sql")
    governed_spec = spec[spec.index("procedure record_governed_retrieval_event") :]
    assert "governed_retrieval" in checks
    assert "retrieval_domain" in checks
    assert "record_governed_retrieval_event" in spec
    assert "p_domain_code" in spec
    assert "p_tool_mode" in spec
    assert "p_stream_health_state" in spec
    for forbidden in (
        "p_query",
        "p_tool_arguments",
        "p_evidence_text",
        "p_reasoning",
        "p_discarded_text",
    ):
        assert forbidden not in governed_spec
    assert "'stream_health_state'" in body
    assert "'continuation_recovery_yn'" in body
    assert "write_event(" in body


def test_runtime_reads_current_evidence_without_model_name_conditions() -> None:
    context_manager = _text(ROOT / "src" / "model" / "context_manager.py")
    capability = _text(
        ROOT / "src" / "orac_core" / "governed_retrieval" / "capability.py"
    )
    assert "llm_current_model_evidence_v" in context_manager
    assert "structured_tool_calling" in capability
    assert "streaminghealthstate.suppressed" in capability
    assert "model_name" not in capability
    grant = _text(
        SCHEMA / "orac_code" / "grant" / "governed_retrieval_capability_access.sql"
    )
    assert "grant read on orac_code.llm_current_model_evidence_v to orac" in grant


def test_phase2c_catalogue_reuses_existing_least_privilege_packages() -> None:
    """Discovery adds package contracts without a new table or direct runtime view."""
    auth_spec = _text(
        SCHEMA / "orac_code" / "package_spec" / "rag_usage_authorization_api.sql"
    )
    auth_body = _text(
        SCHEMA / "orac_code" / "package_body" / "rag_usage_authorization_api.sql"
    )
    memory_spec = _text(
        SCHEMA / "orac_code" / "package_spec" / "conversation_memory_api.sql"
    )
    memory_body = _text(
        SCHEMA / "orac_code" / "package_body" / "conversation_memory_api.sql"
    )
    assert "open_authorised_project_domains" in auth_spec
    assert "privilege.expires_on > systimestamp" in auth_body
    assert "scope.scope_type = 'project'" in auth_body
    assert "usr.is_active = 'y'" in auth_body
    assert "has_retrievable_memory" in memory_spec
    assert "conversation.user_id = l_user_id" in memory_body
    assert "checkpoint.embedding_model = trim(p_embedding_model)" in memory_body
    assert not list(SCHEMA.rglob("*domain_descriptor*.sql"))


def test_phase2c_audit_extension_remains_content_free_and_bounded() -> None:
    """The optional telemetry document has a strict size and no content fields."""
    spec = _text(SCHEMA / "orac_code" / "package_spec" / "knowledge_retrieval_api.sql")
    body = _text(SCHEMA / "orac_code" / "package_body" / "knowledge_retrieval_api.sql")
    governed_spec = spec[spec.index("procedure record_governed_retrieval_event") :]
    assert "p_phase2c_detail_json" in spec
    assert "dbms_lob.getlength(p_phase2c_detail_json) > 8192" in body
    assert "p_phase2c_detail_json is json" in body
    for forbidden in (
        "p_query",
        "p_prompt",
        "p_evidence_text",
        "p_domain_description",
    ):
        assert forbidden not in governed_spec
