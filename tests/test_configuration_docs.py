"""Tests for canonical configuration and documentation coverage."""
# Author: Clive Bostock
# Date: 06-Jun-2026
# Description: Verifies orac.ini coverage and local links in canonical docs.

from __future__ import annotations

from collections import Counter
from configparser import ConfigParser
from pathlib import Path
import re
from urllib.parse import unquote


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "resources/config/orac.ini"
CONFIG_DOC_PATH = PROJECT_ROOT / "docs/configuration.md"
CANONICAL_DOC_PATHS = (
    PROJECT_ROOT / "README.md",
    PROJECT_ROOT / "docs/README.md",
    PROJECT_ROOT / "docs/installation.md",
    CONFIG_DOC_PATH,
    PROJECT_ROOT / "docs/plugins.md",
    PROJECT_ROOT / "docs/home-assistant.md",
    PROJECT_ROOT / "docs/retrieval.md",
    PROJECT_ROOT / "docs/voice-pipeline.md",
    PROJECT_ROOT / "docs/apex-administration.md",
    PROJECT_ROOT / "docs/backup-restore.md",
    PROJECT_ROOT / "plugins/README.md",
    PROJECT_ROOT / "plugins/home_assistant/README.md",
)
SECTION_HEADING_PATTERN = re.compile(r"^## `\[([^]]+)]`$")
PARAMETER_HEADING_PATTERN = re.compile(r"^### `([^`]+)`$")
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^]]*]\(([^)]+)\)")
HTML_LINK_PATTERN = re.compile(r"(?:href|src)=['\"]([^'\"]+)['\"]")


def _configured_parameters() -> set[tuple[str, str]]:
    """Return fully qualified parameters from the shipped Orac INI file."""
    parser = ConfigParser(
        interpolation=None,
        inline_comment_prefixes=(";", "#"),
    )
    parser.optionxform = str
    parser.read(CONFIG_PATH, encoding="utf-8")
    return {
        (section, key)
        for section in parser.sections()
        for key in parser[section]
    }


def _documented_parameters() -> list[tuple[str, str]]:
    """Return parameters declared under configuration section headings."""
    parameters: list[tuple[str, str]] = []
    current_section: str | None = None
    for line in CONFIG_DOC_PATH.read_text(encoding="utf-8").splitlines():
        section_match = SECTION_HEADING_PATTERN.match(line)
        if section_match:
            current_section = section_match.group(1)
            continue

        parameter_match = PARAMETER_HEADING_PATTERN.match(line)
        if parameter_match and current_section is not None:
            parameters.append((current_section, parameter_match.group(1)))
    return parameters


def _local_link_target(source: Path, raw_target: str) -> Path | None:
    """Resolve one local Markdown link target, ignoring URLs and anchors."""
    target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
    if not target or target.startswith(("#", "http://", "https://", "mailto:")):
        return None
    path_part = unquote(target.split("#", maxsplit=1)[0])
    return (source.parent / path_part).resolve()


def test_configuration_reference_matches_shipped_ini() -> None:
    """Every shipped INI parameter appears exactly once in the reference."""
    configured = _configured_parameters()
    documented = _documented_parameters()
    counts = Counter(documented)

    duplicates = sorted(parameter for parameter, count in counts.items() if count > 1)
    missing = sorted(configured - set(documented))
    stale = sorted(set(documented) - configured)

    assert duplicates == []
    assert missing == []
    assert stale == []


def test_canonical_documentation_links_resolve() -> None:
    """Local Markdown and HTML links in canonical documentation resolve."""
    missing: list[str] = []
    for source in CANONICAL_DOC_PATHS:
        text = source.read_text(encoding="utf-8")
        raw_targets = (
            MARKDOWN_LINK_PATTERN.findall(text)
            + HTML_LINK_PATTERN.findall(text)
        )
        for raw_target in raw_targets:
            target = _local_link_target(source, raw_target)
            if target is not None and not target.exists():
                missing.append(f"{source.relative_to(PROJECT_ROOT)} -> {raw_target}")

    assert missing == []
