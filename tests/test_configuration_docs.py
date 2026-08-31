"""Tests for canonical configuration and documentation coverage."""

# Author: Clive Bostock
# Date: 06-Jun-2026
# Description: Verifies orac.ini coverage and local links in canonical docs.

from __future__ import annotations

from collections import Counter
from configparser import ConfigParser
from pathlib import Path
import re
import sys
from urllib.parse import unquote

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from lib.config_mgr import ConfigManager  # noqa: E402

CONFIG_PATH = PROJECT_ROOT / "resources/config/orac.ini"
SHIPPED_CONFIG_PATHS = (
    CONFIG_PATH,
    PROJECT_ROOT / "resources/config/orac.ini.kokoro",
    PROJECT_ROOT / "resources/config/orac.ini.piper",
)
CONFIG_DOC_PATH = PROJECT_ROOT / "docs/configuration.md"
CONVERSATION_GUIDE_PATH = PROJECT_ROOT / "docs/conversation-context-memory-and-rag.md"
CANONICAL_DOC_PATHS = (
    PROJECT_ROOT / "README.md",
    PROJECT_ROOT / "docs/README.md",
    PROJECT_ROOT / "docs/installation.md",
    CONFIG_DOC_PATH,
    CONVERSATION_GUIDE_PATH,
    PROJECT_ROOT / "docs/conversational-memory.md",
    PROJECT_ROOT / "docs/governed-retrieval.md",
    PROJECT_ROOT / "docs/context-budgeting.md",
    PROJECT_ROOT / "docs/dialogue-routing.md",
    PROJECT_ROOT / "docs/plugins.md",
    PROJECT_ROOT / "docs/document-ingestion.md",
    PROJECT_ROOT / "plugins/home_assistant/docs/home-assistant.md",
    PROJECT_ROOT / "plugins/home_assistant/docs/home-assistant-data-lifecycle.md",
    PROJECT_ROOT / "plugins/drop_box/README.md",
    PROJECT_ROOT / "plugins/drop_box/docs/drop-box.md",
    PROJECT_ROOT / "plugins/drop_box/docs/drop-box-data-lifecycle.md",
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
CONVERSATION_GUIDE_SHIPPED_SETTINGS = (
    ("context", "enable_context_history"),
    ("context_budget", "enabled"),
    ("context_budget", "shadow_mode"),
    ("conversation_memory", "enabled"),
    ("governed_retrieval", "enabled"),
    ("governed_retrieval", "project_scope"),
    ("governed_retrieval", "domain_discovery_enabled"),
    ("governed_retrieval", "domain_discovery_shadow_mode"),
    ("knowledge", "enabled"),
    ("knowledge.dialogue", "enabled"),
    ("knowledge.retrieval", "enabled"),
    ("knowledge.materialisation", "enabled"),
    ("knowledge.model_evidence", "enabled"),
    ("knowledge.model_evidence", "min_effective_context_tokens"),
)


def _configured_parameters() -> set[tuple[str, str]]:
    """Return fully qualified parameters from the shipped Orac INI file."""
    parser = ConfigParser(
        interpolation=None,
        inline_comment_prefixes=(";", "#"),
    )
    parser.optionxform = str
    parser.read(CONFIG_PATH, encoding="utf-8")
    return {(section, key) for section in parser.sections() for key in parser[section]}


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


def test_shipped_profiles_use_explicit_dsn_credential_entry_keys() -> None:
    """Every shipped profile uses credential-store terminology."""
    for config_path in SHIPPED_CONFIG_PATHS:
        parser = ConfigParser(interpolation=None)
        parser.read(config_path, encoding="utf-8")

        assert parser.get("database", "dsn_credential_entry") == "orac-service"
        assert (
            parser.get("database", "plugin_dsn_credential_entry")
            == "orac-plugin"
        )
        assert not parser.has_option("database", "connection_name")
        assert not parser.has_option("database", "plugin_connection_name")


def test_dsn_credential_entry_environment_overrides(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Documented environment variables override both credential entries."""
    config_path = tmp_path / "orac.ini"
    config_path.write_text(
        "[database]\n"
        "dsn_credential_entry = file-core\n"
        "plugin_dsn_credential_entry = file-plugin\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "ORAC__DATABASE__DSN_CREDENTIAL_ENTRY",
        "environment-core",
    )
    monkeypatch.setenv(
        "ORAC__DATABASE__PLUGIN_DSN_CREDENTIAL_ENTRY",
        "environment-plugin",
    )

    config = ConfigManager(config_file_path=config_path)

    assert (
        config.config_value("database", "dsn_credential_entry")
        == "environment-core"
    )
    assert (
        config.config_value("database", "plugin_dsn_credential_entry")
        == "environment-plugin"
    )


def test_canonical_documentation_links_resolve() -> None:
    """Local Markdown and HTML links in canonical documentation resolve."""
    missing: list[str] = []
    for source in CANONICAL_DOC_PATHS:
        text = source.read_text(encoding="utf-8")
        raw_targets = MARKDOWN_LINK_PATTERN.findall(text) + HTML_LINK_PATTERN.findall(
            text
        )
        for raw_target in raw_targets:
            target = _local_link_target(source, raw_target)
            if target is not None and not target.exists():
                missing.append(f"{source.relative_to(PROJECT_ROOT)} -> {raw_target}")

    assert missing == []


def test_conversation_guide_status_matches_shipped_configuration() -> None:
    """The canonical guide reports exact current feature-switch values."""
    parser = ConfigParser(
        interpolation=None,
        inline_comment_prefixes=(";", "#"),
    )
    parser.read(CONFIG_PATH, encoding="utf-8")
    guide = CONVERSATION_GUIDE_PATH.read_text(encoding="utf-8").lower()

    for section, key in CONVERSATION_GUIDE_SHIPPED_SETTINGS:
        value = parser.get(section, key).strip().lower()
        assert f"`[{section}].{key} = {value}`" in guide


def test_conversation_guidance_rejects_known_stale_claims() -> None:
    """Canonical routes cannot reintroduce superseded rollout statements."""
    memory = (
        (PROJECT_ROOT / "docs/conversational-memory.md")
        .read_text(encoding="utf-8")
        .lower()
    )
    guide = CONVERSATION_GUIDE_PATH.read_text(encoding="utf-8").lower()
    materialisation = (
        (PROJECT_ROOT / "docs/knowledge-materialisation-policy.md")
        .read_text(encoding="utf-8")
        .lower()
    )
    model_evidence = (
        (PROJECT_ROOT / "docs/knowledge-model-evidence.md")
        .read_text(encoding="utf-8")
        .lower()
    )

    assert "the shipped default is disabled" not in memory
    assert "phase 2b remains deferred" not in memory
    assert "ships disabled" not in materialisation
    assert "the feature ships disabled" not in model_evidence
    assert "persisted history is therefore not rag by itself" in guide
    assert "takes precedence at runtime" in guide


def test_conversation_guide_is_discoverable_from_canonical_routes() -> None:
    """User and maintainer entry points link to the consolidated guide."""
    guide_link = "conversation-context-memory-and-rag.md"
    for relative_path in (
        "README.md",
        "docs/README.md",
        "docs/conversational-memory.md",
        "docs/governed-retrieval.md",
        "docs/context-budgeting.md",
        "docs/dialogue-routing.md",
    ):
        text = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        assert guide_link in text

    for relative_path in ("README.md", "docs/README.md"):
        text = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        assert "detailed-architecture.md" not in text
