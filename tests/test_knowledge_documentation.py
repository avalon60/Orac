"""Regression contracts for the implemented knowledge lifecycle documentation."""

# Author: Clive Bostock
# Date: 22-Aug-2026
# Description: Prevents lifecycle, security, and deferred-scope documentation drift.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CATALOGUE_PATH = "docs/pending_work/p2-01-binary-multimodal-use-case-catalogue.md"
TAXONOMY_PATH = "docs/pending_work/p2-02-controlled-capability-taxonomy.md"
MASTER_PLAN_PATH = "docs/pending_work/orac_document_materialisation_enhancements_plan.md"
USE_CASE_IDS = (
    "UC-PDF-SCAN",
    "UC-PDF-VISUAL",
    "UC-IMAGE-TECHNICAL",
    "UC-SPREADSHEET-VISUAL",
    "UC-PRESENTATION-VISUAL",
    "UC-AUDIO-SPEECH",
    "UC-VIDEO-TEMPORAL",
    "UC-OFFICE-ORIGINAL",
)
CATALOGUE_FIELDS = (
    "Use-case ID",
    "Title",
    "Status",
    "Priority",
    "User outcome",
    "Insufficiency trigger",
    "Source media",
    "Material characteristics",
    "Authoritative source",
    "Required selection granularity",
    "Typical payload",
    "Proposed hard bound",
    "Expansion risks",
    "Existing content classification",
    "Sensitivity-policy status",
    "Preferred deterministic processing",
    "Candidate provider class",
    "Candidate backend",
    "Fallback",
    "Rejection conditions",
    "Provenance requirement",
    "Audit requirement",
    "Current support",
    "Representative fixture",
    "Evidence",
    "Notes for P2-02",
)
CAPABILITY_CODES = (
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
)
CAPABILITY_CLASSES = (
    "PRIMARY_TEXT_REASONING",
    "DETERMINISTIC_INSPECTION",
    "DETERMINISTIC_TRANSFORMATION",
    "DETERMINISTIC_CALCULATION",
    "SPECIALIST_INTERPRETATION",
)
EVIDENCE_STATES = (
    "UNASSESSED",
    "API_DECLARED",
    "MODEL_METADATA_VERIFIED",
    "BOUNDED_PROBE_VERIFIED",
    "REJECTED",
)
TAXONOMY_FIELDS = (
    "Capability code",
    "Display name",
    "Capability class",
    "Behaviour",
    "Accepted representation",
    "Required characteristics",
    "Output evidence",
    "Authority",
    "Selection contract",
    "Provenance contract",
    "Bound dimensions",
    "Locality requirement",
    "Fallback",
    "Evidence status",
    "Related use cases",
    "Deferred behaviour",
    "P2-03 metadata note",
)


def _read(relative_path: str) -> str:
    """Return one repository document as normalised lower-case text."""
    return " ".join(
        (PROJECT_ROOT / relative_path).read_text(encoding="utf-8").lower().split()
    )


def _read_raw(relative_path: str) -> str:
    """Return one repository document without normalising its structure."""
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def _catalogue_sections(catalogue: str) -> dict[str, str]:
    """Return the bounded Markdown section owned by every required use case."""
    positions = {
        use_case_id: catalogue.index(f"### {use_case_id} ")
        for use_case_id in USE_CASE_IDS
    }
    ordered = sorted(positions.items(), key=lambda item: item[1])
    sections: dict[str, str] = {}
    for index, (use_case_id, start) in enumerate(ordered):
        end = ordered[index + 1][1] if index + 1 < len(ordered) else len(catalogue)
        sections[use_case_id] = catalogue[start:end]
    return sections


def _taxonomy_sections(taxonomy: str) -> dict[str, str]:
    """Return the bounded taxonomy record owned by every capability code."""
    matches = list(
        re.finditer(
            r"^### `([a-z][a-z0-9_]*)` — .+$",
            taxonomy,
            flags=re.MULTILINE,
        )
    )
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        code = match.group(1)
        assert code not in sections, f"duplicate taxonomy record for {code}"
        end = matches[index + 1].start() if index + 1 < len(matches) else len(taxonomy)
        sections[code] = taxonomy[match.start():end]
    return sections


def test_core_guides_define_authority_and_read_only_reconciliation() -> None:
    """Core guides describe implemented authority without promising repair."""
    ingestion = _read("docs/document-ingestion.md")
    maintenance = _read("docs/knowledge-maintenance.md")
    configuration = _read("docs/configuration.md")

    for phrase in (
        "raw original",
        "extraction clob",
        "normalised output set",
        "chunk set and chunks",
        "retrieval and materialisation",
        "reconciliation",
    ):
        assert phrase in ingestion
    for phrase in (
        "strictly read-only",
        "ready",
        "blocked",
        "incomplete",
        "separately approved",
        "never deletes",
    ):
        assert phrase in maintenance
    for key in (
        "max_database_rows",
        "max_filesystem_entries",
        "max_hashed_bytes",
        "max_elapsed_seconds",
        "max_report_items_per_reason",
        "max_report_bytes",
    ):
        assert key in configuration
    assert "implemented p1-09 read-only inventory" in ingestion
    assert "future p1-09 inventory" not in ingestion


def test_plugin_guides_match_core_ownership_and_failure_boundaries() -> None:
    """Drop Box documentation keeps Core ownership and recovery limits explicit."""
    lifecycle = _read("plugins/drop_box/docs/drop-box-data-lifecycle.md")
    operator = _read("plugins/drop_box/docs/drop-box.md")

    for phrase in (
        "raw original and canonical markdown",
        "primary, manifest, or table",
        "database failure after managed promotion",
        "stale temporary entries",
        "no behavioural authority",
        "separately authorised",
    ):
        assert phrase in lifecycle
    assert "raw-binary model submission and model-capability routing are phase 2" in lifecycle
    assert "uppercase `doc_class` reference codes" in lifecycle
    assert "narrow administrative bypass" not in lifecycle
    assert "bin/orac-knowledge.sh reconcile" in operator
    assert "do not delete, register, quarantine, rewrite, or recover" in operator


def test_phase_two_remains_deferred_everywhere_it_is_advertised() -> None:
    """Phase 1 documentation cannot imply raw-binary model routing is available."""
    for relative_path in (
        "docs/document-ingestion.md",
        "docs/knowledge-materialisation-policy.md",
        "docs/knowledge-model-evidence.md",
        "docs/knowledge-retrieval.md",
        "plugins/drop_box/docs/drop-box-data-lifecycle.md",
    ):
        text = _read(relative_path)
        assert "raw binary" in text or "raw-binary" in text
        assert any(token in text for token in ("deferred", "does not", "never", "outside"))


def test_p2_01_catalogue_contract_is_complete() -> None:
    """Every initial use case exposes the complete planning-only contract."""
    catalogue_file = PROJECT_ROOT / CATALOGUE_PATH
    assert catalogue_file.is_file()
    catalogue = _read_raw(CATALOGUE_PATH)
    sections = _catalogue_sections(catalogue)

    assert set(sections) == set(USE_CASE_IDS)
    for use_case_id, section in sections.items():
        assert f"- **Use-case ID:** `{use_case_id}`" in section
        for field in CATALOGUE_FIELDS:
            assert f"- **{field}:**" in section, f"{use_case_id} is missing {field}"

    for status in ("CANDIDATE", "VALIDATED", "DEFERRED", "REJECTED"):
        assert f"`{status}`" in catalogue
    for priority in ("TIER_1", "TIER_2", "TIER_3"):
        assert f"`{priority}`" in catalogue


def test_p2_01_catalogue_preserves_phase_one_security_boundaries() -> None:
    """The catalogue cannot advertise planned binary behaviour as available."""
    catalogue = _read(CATALOGUE_PATH)

    for phrase in (
        "raw binary remains unavailable in phase 1",
        "final capability codes remain deferred to p2-02",
        "remote submission remains ineligible",
        "a model is never authoritative for arithmetic",
        "no runtime capability",
        "no fixture was added merely",
    ):
        assert phrase in catalogue

    for prohibited_claim in (
        "binary ingestion is available",
        "raw-original materialisation is available",
        "multimodal model submission is available",
        "remote processing is enabled",
        "phase 2 runtime capability is implemented",
    ):
        assert prohibited_claim not in catalogue


def test_p2_01_master_plan_records_documentation_only_resolution() -> None:
    """The master plan records P2-01 without completing later Phase 2 work."""
    master_plan = _read(MASTER_PLAN_PATH)

    for phrase in (
        "p2-01 completed: 22-aug-2026",
        "p2-01-binary-multimodal-use-case-catalogue.md",
        "no validated use cases",
        "no binary runtime support was enabled",
        "p2-03 through p2-10 remain not started",
    ):
        assert phrase in master_plan


def test_p2_02_taxonomy_has_one_complete_record_per_capability() -> None:
    """Every final capability code owns exactly one complete taxonomy record."""
    taxonomy_file = PROJECT_ROOT / TAXONOMY_PATH
    assert taxonomy_file.is_file()
    taxonomy = _read_raw(TAXONOMY_PATH)
    sections = _taxonomy_sections(taxonomy)

    assert tuple(sections) == CAPABILITY_CODES
    for capability_code, section in sections.items():
        assert f"- **Capability code:** `{capability_code}`" in section
        for field in TAXONOMY_FIELDS:
            assert f"- **{field}:**" in section, (
                f"{capability_code} is missing {field}"
            )


def test_p2_02_taxonomy_maps_use_cases_classes_and_evidence_states() -> None:
    """The taxonomy controls classes, evidence maturity, and every P2-01 case."""
    taxonomy = _read_raw(TAXONOMY_PATH)

    for use_case_id in USE_CASE_IDS:
        assert taxonomy.count(f"| `{use_case_id}` |") == 1
    for capability_class in CAPABILITY_CLASSES:
        assert f"- `{capability_class}`:" in taxonomy
    for evidence_state in EVIDENCE_STATES:
        assert f"- `{evidence_state}`:" in taxonomy


def test_p2_02_taxonomy_preserves_provider_and_phase_one_boundaries() -> None:
    """Capability semantics stay provider-neutral and planning-only."""
    taxonomy = _read(TAXONOMY_PATH)
    sections = _taxonomy_sections(_read_raw(TAXONOMY_PATH))

    assert set(sections) == set(CAPABILITY_CODES)
    for capability_code in sections:
        assert all(
            provider_name not in capability_code
            for provider_name in ("ollama", "lmstudio", "openai", "anthropic")
        )

    for phrase in (
        "mime acceptance is not behavioural capability evidence",
        "deterministic spreadsheet parsing and calculation remain authoritative",
        "`unmapped` content remains ineligible for remote processing",
        "raw-binary and multimodal runtime support remain unavailable",
        "p2-03 metadata implementation remains deferred",
        "a capability definition is not an enabled feature",
    ):
        assert phrase in taxonomy


def test_p2_02_master_plan_records_documentation_only_resolution() -> None:
    """The master plan completes P2-02 without completing later runtime work."""
    master_plan = _read(MASTER_PLAN_PATH)

    for phrase in (
        "p2-02 completed: 22-aug-2026",
        "p2-02-controlled-capability-taxonomy.md",
        "no runtime or database capability was enabled",
        "p2-03 through p2-10 remain not started",
    ):
        assert phrase in master_plan
