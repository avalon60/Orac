"""Verify the P2-05 capability-aware routing planning contract."""

# Author: Clive Bostock
# Date: 23-Aug-2026
# Description: Offline documentation and boundary tests for P2-05.
# Codex-assisted generated.
# Codex SDK reviewability guardrails followed.

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = (
    PROJECT_ROOT
    / "docs"
    / "pending_work"
    / "p2-05-capability-aware-routing-and-fallback-policy.md"
)
P2_06_PLAN_PATH = (
    PROJECT_ROOT
    / "docs"
    / "pending_work"
    / "p2-06-secure-binary-materialisation-plan.md"
)
P2_07_PLAN_PATH = (
    PROJECT_ROOT / "docs" / "pending_work" / "p2-07-specialist-model-adapters-plan.md"
)
MASTER_PLAN_PATH = (
    PROJECT_ROOT
    / "docs"
    / "pending_work"
    / "orac_document_materialisation_enhancements_plan.md"
)


def _read(path: Path) -> str:
    """Read a repository text file as UTF-8.

    Args:
        path: Repository path to read.

    Returns:
        File content.
    """
    return path.read_text(encoding="utf-8")


def test_every_media_family_maps_to_controlled_route_kinds() -> None:
    """Require complete P2-04 family coverage and controlled route kinds."""
    policy = _read(POLICY_PATH)
    for route_kind in (
        "DETERMINISTIC_PROCESSOR",
        "SPECIALIST_MODEL",
        "NORMALISED_EVIDENCE_FALLBACK",
        "PRIMARY_TEXT_COMPATIBILITY",
    ):
        assert f"`{route_kind}`" in policy
    for family in (
        "Markdown/CSV/JSON/plain text",
        "PDF",
        "Technical image",
        "Workbook",
        "Presentation",
        "Audio",
        "Video",
        "Office original",
    ):
        assert f"| {family} |" in policy
    for use_case in (
        "UC-PDF-SCAN",
        "UC-PDF-VISUAL",
        "UC-IMAGE-TECHNICAL",
        "UC-SPREADSHEET-VISUAL",
        "UC-PRESENTATION-VISUAL",
        "UC-AUDIO-SPEECH",
        "UC-VIDEO-TEMPORAL",
        "UC-OFFICE-ORIGINAL",
    ):
        assert f"`{use_case}`" in policy


def test_model_evidence_transport_and_adapter_fail_closed() -> None:
    """Require transport and registry facts to remain non-behavioural."""
    policy = _read(POLICY_PATH)
    for reason in (
        "RTE_MODEL_EVIDENCE_ABSENT",
        "RTE_MODEL_EVIDENCE_EXPIRED",
        "RTE_MODEL_EVIDENCE_REJECTED",
        "RTE_TRANSPORT_UNSUPPORTED",
        "RTE_ADAPTER_UNSUPPORTED",
    ):
        assert reason in policy
    assert "`API_DECLARED`, provider `LOCAL`, registry `TEXT`" in policy
    assert "adapter status is\n  `NOT_IMPLEMENTED`" in policy


def test_representation_mime_capabilities_and_limits_are_independent() -> None:
    """Require each compatibility and bound concern to be checked explicitly."""
    policy = _read(POLICY_PATH)
    assert "RTE_REQUIRED_CAPABILITY_MISSING" in policy
    assert "RTE_REPRESENTATION_UNSUPPORTED" in policy
    assert "RTE_MIME_UNSUPPORTED" in policy
    assert "RTE_LIMIT_MISSING" in policy
    assert "RTE_LIMIT_EXCEEDED" in policy
    assert "independent representation and MIME decisions" in policy
    for dimension in (
        "BYTES",
        "EXPANDED_BYTES",
        "MEMBERS",
        "PAGES",
        "OBJECTS",
        "PIXELS",
        "CELLS",
        "DURATION",
        "CHANNELS",
        "FRAMES",
        "INPUT_TOKENS",
        "OUTPUT_TOKENS",
        "OUTPUT_BYTES",
        "RETRIES",
        "ELAPSED_TIME",
    ):
        p2_04_policy = _read(
            PROJECT_ROOT
            / "docs"
            / "pending_work"
            / "p2-04-media-type-processing-policy.md"
        )
        assert f"`{dimension}`" in p2_04_policy


def test_routing_output_is_bounded_and_content_free() -> None:
    """Require the output contract to exclude content and locator fields."""
    policy = _read(POLICY_PATH)
    output_contract = policy[
        policy.index("## 6. Routing output contract") : policy.index(
            "## 7. Eligibility gates and reason codes"
        )
    ]
    assert "bounded safe audit fields" in output_contract
    assert "must not contain prompts, content, filenames, paths, managed keys" in (
        output_contract
    )
    assert "arbitrary URLs" in output_contract
    assert "unbounded media" in output_contract


def test_fallback_cannot_widen_policy_or_deterministic_authority() -> None:
    """Require non-widening fallback and deterministic calculation authority."""
    policy = _read(POLICY_PATH)
    assert "Every fallback step must retain or narrow" in policy
    assert "Fallback never substitutes model arithmetic" in policy
    assert "deterministic calculation remains authoritative" in policy
    assert "local-only decision cannot fall back to remote" in policy
    assert "optional specialist evidence" in policy
    assert "RTE_OPTIONAL_SPECIALIST_OMITTED" in policy


def test_locality_classification_and_observations_are_controlled() -> None:
    """Require explicit locality policy and dated observation vocabularies."""
    policy = _read(POLICY_PATH)
    assert "`DOC_CLASS` is content purpose, not sensitivity." in policy
    assert "Missing sensitivity/consent/locality policy fails closed." in policy
    for observation in ("Availability", "Health", "Quality", "Cost"):
        assert f"| {observation} |" in policy
    for field in (
        "observed timestamp",
        "expiry",
        "provenance",
        "evaluation profile",
        "immutable fingerprint",
    ):
        assert field in policy


def test_ordering_keeps_route_authority_stable_and_uses_candidate_tie_break() -> None:
    """Require model-neutral route authority and stable candidate ordering."""
    policy = _read(POLICY_PATH)
    ordering = policy.index("## 9. Deterministic candidate ordering")
    fallback = policy.index("## 12. Non-widening fallback contract")
    assert ordering < fallback
    assert "immutable requirement contract derived from P2-04" in policy
    assert "stable configured-candidate identity" in policy
    assert "database row, install, registration, filesystem, discovery" in policy
    assert "plugin candidate" in policy
    assert "never a route-kind identity" in policy


def test_specialist_route_authority_is_capability_based() -> None:
    """Keep concrete-model evidence as candidate eligibility evidence."""
    policy = _read(POLICY_PATH)
    assert "`SPECIALIST_MODEL` | Versioned capability-requirement identity" in policy
    assert "candidate eligibility input" in policy
    assert "RTE_NO_ELIGIBLE_MODEL" in policy
    assert "exact runtime-selected" in policy


def test_adapter_and_audit_plans_preserve_model_neutral_authority() -> None:
    """Require model-neutral adapters and synthetic P2-08 validation."""
    adapter_plan = _read(P2_07_PLAN_PATH)
    master_plan = _read(MASTER_PLAN_PATH)
    assert (
        "Concrete-model, model-evidence, route, use-case, and attachment "
        "identities are\nruntime admission inputs" in adapter_plan
    )
    assert "model-keyed adapter registration" in adapter_plan
    assert "P2-08 planning must not require an eligible" in adapter_plan
    assert "P2-08 planning and contract validation are not blocked" in master_plan


def test_routing_evaluation_cannot_prepare_or_invoke_a_provider() -> None:
    """Require explicit denial of side-effectful provider discovery paths."""
    policy = _read(POLICY_PATH)
    assert "must not construct a connector" in policy
    for forbidden_call in (
        "validate_or_prepare_model()",
        "list_models()",
        "Ollama `list`/`pull`",
        "LM Studio `/v1/models`",
        "inference endpoint",
    ):
        assert forbidden_call in policy

    provider_registry = _read(PROJECT_ROOT / "src" / "model" / "provider_registry.py")
    assert 'subprocess.run(["ollama", "pull", model_name]' in provider_registry
    assert "def validate_or_prepare_model(" in provider_registry


def test_deferred_boundaries_and_phase_one_remain_explicit() -> None:
    """Require deferred binary interpretation and Phase 1 compatibility."""
    policy = _read(POLICY_PATH)
    assert "Temporal interpretation remains `DEFERRED`" in policy
    assert "Direct original interpretation remains `DEFERRED`" in policy
    assert "Existing Phase 1 path unchanged" in policy
    assert "prompt-string-only" in policy
    assert "no eligible new specialist route" in policy


def test_p2_06_plan_is_standalone_secure_and_planning_only() -> None:
    """Require the next-stage secure materialisation planning handoff."""
    plan = _read(P2_06_PLAN_PATH)
    normalised_plan = " ".join(plan.split())
    assert "## Planning constraint" in plan
    assert "Implement P2-06 only after explicit implementation authorisation." in plan
    assert "## 5. Materialisation input contract" in plan
    assert "## 6. Output and attachment-handle contract" in plan
    assert "## 7. Required lifecycle" in plan
    assert "## 13. Tests" in plan
    assert "mode-`0600`" in plan
    assert "single-use" in plan
    assert "Do not implement P2-07 during that planning activity." in normalised_plan
