"""Validate Orac guardrail document structure and local references."""
# Author: Clive Bostock
# Date: 25-May-2026
# Description: Validates guardrail document naming and local references.
# Purpose: Detect lightweight guardrail documentation drift.
# Usage: poetry run python scripts/check_guardrails.py

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys


ALLOWED_TOP_LEVEL_ASSETS = {"table-abbreviations.csv"}
BACKUP_SUFFIXES = (".bak", ".tmp", ".swp")
GUARDRAIL_DIR = Path("docs/agent-guardrails")
GUARDRAIL_FILE_PATTERN = re.compile(r"^\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
PLAIN_GUARDRAIL_REF_PATTERN = re.compile(
    r"docs/agent-guardrails/[A-Za-z0-9_./ -]+?\.(?:md|csv)"
)


@dataclass(frozen=True)
class GuardrailReference:
    """Represents one local guardrail documentation reference."""

    source: Path
    raw: str
    target: Path


def default_project_root() -> Path:
    """Return the project root inferred from this script location."""
    return Path(__file__).resolve().parent.parent


def build_parser() -> argparse.ArgumentParser:
    """Build the command line parser."""
    parser = argparse.ArgumentParser(
        description="Validate Orac guardrail document structure and references.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=default_project_root(),
        help="Project root. Default: inferred from the script location.",
    )
    return parser


def is_ignored_link_target(target: str) -> bool:
    """Return whether a Markdown link target should not be validated."""
    cleaned = target.strip()
    if not cleaned:
        return True
    lowered = cleaned.lower()
    if cleaned.startswith("#"):
        return True
    if lowered.startswith(("http://", "https://", "mailto:")):
        return True
    if "@" in cleaned and "/" not in cleaned:
        return True
    return False


def normalise_markdown_link_target(target: str) -> str:
    """Return the path portion of a Markdown link target."""
    cleaned = target.strip().strip("<>")
    if not cleaned:
        return ""
    cleaned = cleaned.split()[0]
    return cleaned.split("#", 1)[0]


def is_guardrail_path(path: Path, root: Path) -> bool:
    """Return whether path is inside the guardrail documentation directory."""
    try:
        path.resolve().relative_to((root / GUARDRAIL_DIR).resolve())
    except ValueError:
        return False
    return True


def resolve_reference(raw: str, *, source: Path, root: Path) -> Path | None:
    """Resolve a local guardrail reference to an absolute path."""
    if is_ignored_link_target(raw):
        return None

    cleaned = normalise_markdown_link_target(raw)
    if not cleaned:
        return None

    if cleaned.startswith(str(GUARDRAIL_DIR)):
        return (root / cleaned).resolve()

    if cleaned.startswith(("/", "\\")):
        return None

    suffix = Path(cleaned).suffix.lower()
    if suffix not in {".md", ".csv"}:
        return None

    resolved = (source.parent / cleaned).resolve()
    if not is_guardrail_path(resolved, root):
        return None
    return resolved


def extract_local_references(
    text: str,
    *,
    source: Path,
    root: Path,
) -> list[GuardrailReference]:
    """Extract practical local guardrail references from Markdown text."""
    references: list[GuardrailReference] = []
    seen: set[tuple[Path, str, Path]] = set()

    def add_reference(raw: str) -> None:
        target = resolve_reference(raw, source=source, root=root)
        if target is None:
            return
        key = (source.resolve(), raw, target)
        if key in seen:
            return
        seen.add(key)
        references.append(GuardrailReference(source=source, raw=raw, target=target))

    for match in PLAIN_GUARDRAIL_REF_PATTERN.finditer(text):
        if "://" in text[max(0, match.start() - 64) : match.start()]:
            continue
        add_reference(match.group(0))

    for match in MARKDOWN_LINK_PATTERN.finditer(text):
        add_reference(match.group(1))

    return references


def invalid_top_level_file_reasons(path: Path) -> list[str]:
    """Return reasons a top-level guardrail file name is invalid."""
    name = path.name
    lowered_name = name.lower()
    suffix = path.suffix.lower()
    reasons: list[str] = []

    if name.startswith("."):
        reasons.append("leading dotfile")
    if "untitled" in lowered_name:
        reasons.append("contains 'untitled'")
    if name.endswith("~") or suffix in BACKUP_SUFFIXES:
        reasons.append("backup or temporary suffix")
    if not path.suffix:
        reasons.append("no extension")

    if reasons:
        return reasons

    if name in ALLOWED_TOP_LEVEL_ASSETS:
        return []
    if suffix == ".md":
        if not GUARDRAIL_FILE_PATTERN.fullmatch(name):
            reasons.append("markdown file must match NN-kebab-case.md")
        return reasons

    reasons.append("unsupported top-level guardrail asset")
    return reasons


def validate_guardrail_tree(root: Path) -> list[str]:
    """Validate guardrail directory shape and top-level file names."""
    issues: list[str] = []
    guardrail_dir = root / GUARDRAIL_DIR
    if not guardrail_dir.is_dir():
        return [f"{GUARDRAIL_DIR}: directory does not exist"]

    for path in sorted(guardrail_dir.iterdir(), key=lambda item: item.name.lower()):
        if path.is_dir():
            continue
        reasons = invalid_top_level_file_reasons(path)
        if reasons:
            joined_reasons = "; ".join(reasons)
            issues.append(
                f"{path.relative_to(root)}: invalid guardrail file ({joined_reasons})"
            )

    return issues


def validate_references(root: Path) -> list[str]:
    """Validate local guardrail references from AGENTS.md and guardrail docs."""
    issues: list[str] = []
    sources = [root / "AGENTS.md"]
    guardrail_dir = root / GUARDRAIL_DIR
    if guardrail_dir.is_dir():
        sources.extend(sorted(guardrail_dir.rglob("*.md")))

    for source in sources:
        if not source.exists():
            issues.append(f"{source.relative_to(root)}: referenced source file is missing")
            continue
        text = source.read_text(encoding="utf-8", errors="replace")
        for reference in extract_local_references(text, source=source, root=root):
            if not reference.target.exists():
                source_name = source.relative_to(root)
                try:
                    target_name = reference.target.relative_to(root)
                except ValueError:
                    target_name = reference.target
                issues.append(
                    f"{source_name}: broken guardrail reference "
                    f"'{reference.raw}' -> {target_name}"
                )

    return issues


def run_checks(root: Path) -> list[str]:
    """Run all guardrail drift checks and return issue lines."""
    resolved_root = root.resolve()
    issues: list[str] = []
    issues.extend(validate_guardrail_tree(resolved_root))
    issues.extend(validate_references(resolved_root))
    return issues


def main(argv: list[str] | None = None) -> int:
    """Run the guardrail checker CLI."""
    args = build_parser().parse_args(argv)
    issues = run_checks(args.root)
    for issue in issues:
        print(issue)
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
