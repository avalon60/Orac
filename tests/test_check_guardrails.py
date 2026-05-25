"""Tests for the guardrail drift checker script."""
# Author: Clive Bostock
# Date: 25-May-2026
# Description: Verifies guardrail structure and reference checking helpers.

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import textwrap


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHECKER_PATH = PROJECT_ROOT / "scripts/check_guardrails.py"
SPEC = importlib.util.spec_from_file_location("check_guardrails", CHECKER_PATH)
assert SPEC is not None
check_guardrails = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = check_guardrails
SPEC.loader.exec_module(check_guardrails)


def test_extracts_agents_style_plain_references() -> None:
    text = """
    - docs/agent-guardrails/00-project-principles.md
    - docs/agent-guardrails/table-abbreviations.csv
    """

    references = check_guardrails.extract_local_references(
        text,
        source=PROJECT_ROOT / "AGENTS.md",
        root=PROJECT_ROOT,
    )

    assert [reference.raw for reference in references] == [
        "docs/agent-guardrails/00-project-principles.md",
        "docs/agent-guardrails/table-abbreviations.csv",
    ]


def test_extracts_inline_code_references() -> None:
    text = "`docs/agent-guardrails/60-security-and-risk.md`"

    references = check_guardrails.extract_local_references(
        text,
        source=PROJECT_ROOT / "docs/agent-guardrails/50-plugin-standards.md",
        root=PROJECT_ROOT,
    )

    assert [reference.raw for reference in references] == [
        "docs/agent-guardrails/60-security-and-risk.md"
    ]


def test_extracts_markdown_local_links() -> None:
    source = PROJECT_ROOT / "docs/agent-guardrails/50-plugin-standards.md"
    text = "[context](70-context-management.md)"

    references = check_guardrails.extract_local_references(
        text,
        source=source,
        root=PROJECT_ROOT,
    )

    assert len(references) == 1
    assert references[0].raw == "70-context-management.md"
    assert references[0].target == (
        PROJECT_ROOT / "docs/agent-guardrails/70-context-management.md"
    ).resolve()


def test_ignores_external_markdown_links() -> None:
    text = textwrap.dedent(
        """
        [external](https://example.com/docs/agent-guardrails/missing.md)
        [mail](mailto:admin@example.com)
        [anchor](#local-section)
        """
    )

    references = check_guardrails.extract_local_references(
        text,
        source=PROJECT_ROOT / "docs/agent-guardrails/25-plsql-standards.md",
        root=PROJECT_ROOT,
    )

    assert references == []


def test_invalid_top_level_guardrail_names_are_reported(tmp_path: Path) -> None:
    guardrail_dir = tmp_path / "docs/agent-guardrails"
    guardrail_dir.mkdir(parents=True)
    for name in [
        "Untitled Document",
        "20-database-standards.md~",
        "draft.bak",
        "scratch.tmp",
        ".hidden.md",
        "extensionless",
    ]:
        (guardrail_dir / name).write_text("", encoding="utf-8")

    issues = check_guardrails.validate_guardrail_tree(tmp_path)

    assert len(issues) == 6
    assert any("Untitled Document" in issue for issue in issues)
    assert any("backup or temporary suffix" in issue for issue in issues)
    assert any("leading dotfile" in issue for issue in issues)
    assert any("no extension" in issue for issue in issues)


def test_valid_top_level_guardrail_names_are_allowed(tmp_path: Path) -> None:
    guardrail_dir = tmp_path / "docs/agent-guardrails"
    guardrail_dir.mkdir(parents=True)
    for name in [
        "00-project-principles.md",
        "10-architecture-boundaries.md",
        "70-context-management.md",
        "table-abbreviations.csv",
    ]:
        (guardrail_dir / name).write_text("# ok\n", encoding="utf-8")

    assert check_guardrails.validate_guardrail_tree(tmp_path) == []


def test_nested_guardrail_docs_do_not_need_numeric_names(tmp_path: Path) -> None:
    guardrail_dir = tmp_path / "docs/agent-guardrails"
    nested_dir = guardrail_dir / "frontend-nextjs/nextjs"
    nested_dir.mkdir(parents=True)
    (guardrail_dir / "35-frontend-nextjs-standards.md").write_text(
        "# ok\n",
        encoding="utf-8",
    )
    (nested_dir / "index.md").write_text("# nested\n", encoding="utf-8")
    (nested_dir / "async-patterns.md").write_text("# nested\n", encoding="utf-8")

    assert check_guardrails.validate_guardrail_tree(tmp_path) == []


def test_current_agents_guardrail_references_resolve() -> None:
    agents_path = PROJECT_ROOT / "AGENTS.md"
    references = check_guardrails.extract_local_references(
        agents_path.read_text(encoding="utf-8"),
        source=agents_path,
        root=PROJECT_ROOT,
    )

    assert references
    missing = [reference.raw for reference in references if not reference.target.exists()]
    assert missing == []
