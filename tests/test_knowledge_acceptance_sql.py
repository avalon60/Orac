"""Static contracts for the rollback-only knowledge lifecycle acceptance script."""

# Author: Clive Bostock
# Date: 15-Aug-2026
# Description: Keeps P1-10 Oracle acceptance isolated from Liquibase deployment.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = (
    PROJECT_ROOT
    / "resources"
    / "db"
    / "acceptance"
    / "knowledge_materialisation_lifecycle.sql"
)


def test_acceptance_script_is_rollback_only_and_controller_excluded() -> None:
    """The runtime acceptance fixture cannot become a deployment changeset."""
    text = SCRIPT.read_text(encoding="utf-8").lower()
    compact = " ".join(text.split())

    assert "whenever sqlerror exit failure rollback" in text
    assert text.count("rollback;") >= 3
    assert "commit;" not in text
    assert "--changeset" not in text
    for forbidden in (
        "create table",
        "alter table",
        "drop table",
        "grant ",
        "revoke ",
        "delete from",
        "truncate table",
    ):
        assert forbidden not in compact

    controller_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore").lower()
        for path in (PROJECT_ROOT / "resources" / "db" / "schema").rglob("*")
        if path.is_file() and path.suffix.lower() in {".xml", ".sql"}
    )
    assert SCRIPT.name.lower() not in controller_text
    assert "resources/db/acceptance" not in controller_text


def test_acceptance_script_covers_phase_one_lineage_decisions() -> None:
    """The SQL fixture exercises the API outcomes that static DDL tests cannot."""
    text = SCRIPT.read_text(encoding="utf-8").lower()

    for token in (
        "knowledge_artefact_api.register_output_set",
        "knowledge_artefact_api.assert_complete_set",
        "knowledge_ingestion_api.create_chunk_set",
        "legacy null-source chunk-set creation is not idempotent",
        "artefact-backed null chunk source was accepted",
        "cross-extraction chunk source was accepted",
        "incomplete spreadsheet set was accepted",
        "manifest and table members shared a chunk set",
        "distinct table members shared a chunk set",
        "metadata member was accepted as a chunk source",
        "p1_10_knowledge_lifecycle_ok",
    ):
        assert token in text
    for expected_error in ("-20523", "-20513", "-20432", "-20433"):
        assert expected_error in text
