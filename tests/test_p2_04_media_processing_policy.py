"""Verify the P2-04 media-processing planning contract."""

# Author: Clive Bostock
# Date: 23-Aug-2026
# Description: Offline documentation and boundary tests for P2-04.

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = (
    PROJECT_ROOT / "docs" / "pending_work" / "p2-04-media-type-processing-policy.md"
)
ROUTING_PLAN_PATH = (
    PROJECT_ROOT
    / "docs"
    / "pending_work"
    / "p2-05-capability-aware-routing-and-fallback-plan.md"
)


def _read(path: Path) -> str:
    """Read a repository text file as UTF-8.

    Args:
        path: Repository path to read.

    Returns:
        File content.
    """
    return path.read_text(encoding="utf-8")


def test_every_media_family_has_one_controlled_default() -> None:
    """Require all supported families in the default matrix."""
    policy = _read(POLICY_PATH)
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


def test_safety_precedence_and_reason_codes_fail_closed() -> None:
    """Require deterministic safety gates before media defaults."""
    policy = _read(POLICY_PATH)
    precedence = policy.index("## 9. Decision precedence")
    defaults = policy.index("## 10. Media-family default matrix")
    assert precedence < defaults
    for reason_code in (
        "MED_SOURCE_IDENTITY_INVALID",
        "MED_SIGNATURE_MISMATCH",
        "MED_REPRESENTATION_UNSUPPORTED",
        "MED_CORRUPT_STRUCTURE",
        "MED_ENCRYPTED_CONTENT",
        "MED_ACTIVE_CONTENT",
        "MED_EXTERNAL_REFERENCE",
        "MED_EXPANSION_LIMIT",
        "MED_BOUND_UNKNOWN",
        "MED_UNBOUNDED_MEDIA",
    ):
        assert reason_code in policy


def test_policy_does_not_route_mime_to_a_provider_or_model() -> None:
    """Require provider/model-neutral policy output and relational separation."""
    policy = _read(POLICY_PATH)
    assert (
        "must not contain a provider code, `llm_id`, service endpoint, cost" in policy
    )

    media_table = _read(
        PROJECT_ROOT
        / "resources"
        / "db"
        / "schema"
        / "orac_core"
        / "table"
        / "llm_input_media_types.sql"
    )
    provider_inputs = _read(
        PROJECT_ROOT
        / "resources"
        / "db"
        / "schema"
        / "orac_core"
        / "table"
        / "llm_provider_inputs.sql"
    )
    model_inputs = _read(
        PROJECT_ROOT
        / "resources"
        / "db"
        / "schema"
        / "orac_core"
        / "table"
        / "llm_model_cap_inputs.sql"
    )
    assert "llm_id" not in media_table
    assert "capability_code" not in provider_inputs
    assert "llm_id" not in model_inputs


def test_deterministic_authority_and_deferred_boundaries_are_explicit() -> None:
    """Require spreadsheet authority and deferred Office/video behaviour."""
    policy = _read(POLICY_PATH)
    assert (
        "A specialist result is a separate attributed evidence item and cannot "
        "overwrite"
    ) in policy
    assert "Direct original interpretation remains `DEFERRED`" in policy
    assert "Temporal interpretation remains `DEFERRED`" in policy
    assert "deterministic calculation remains authoritative" in policy


def test_every_p2_01_use_case_maps_to_a_policy_branch() -> None:
    """Require complete P2-01 to P2-04 branch coverage."""
    policy = _read(POLICY_PATH)
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
        assert f"| `{use_case}` |" in policy


def test_bounds_are_dimension_qualified_and_phase_one_is_preserved() -> None:
    """Require controlled dimensions and unchanged Phase 1 text handling."""
    policy = _read(POLICY_PATH)
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
        assert f"`{dimension}`" in policy
    assert "Existing Phase 1 verification and normalisation" in policy
    assert "There is no universal maximum and no JSON limit set." in policy


def test_p2_05_plan_is_standalone_and_planning_only() -> None:
    """Require the next-stage plan without implementing routing."""
    plan = _read(ROUTING_PLAN_PATH)
    normalised_plan = " ".join(plan.split())
    assert "## Planning constraint" in plan
    assert "Implement P2-05 only after explicit implementation authorisation." in plan
    assert "## 5. Routing inputs and output" in plan
    assert "## 6. Eligibility gates" in plan
    assert "## 8. Fallback contract" in plan
    assert "## 14. Acceptance criteria" in plan
    assert "Do not implement P2-06 during that planning activity." in normalised_plan
