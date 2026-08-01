"""Guard the Core managed store as the sole runtime physical-path authority."""

# Author: Clive Bostock
# Date: 26-Jul-2026
# Description: Prevents managed storage path and promotion logic from drifting.

from __future__ import annotations

from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STORE_MODULE = PROJECT_ROOT / "src" / "orac_core" / "knowledge" / "managed_store.py"
RUNTIME_ROOTS = (
    PROJECT_ROOT / "src" / "orac_core" / "knowledge",
    PROJECT_ROOT / "plugins" / "drop_box",
)
REPOSITORY_RUNTIME_ROOTS = (
    PROJECT_ROOT / "src",
    PROJECT_ROOT / "plugins",
)


def test_managed_store_is_the_only_runtime_physical_path_authority() -> None:
    """Reject shard construction, root joins, and promotion outside the store."""
    violations: list[str] = []
    forbidden = (
        re.compile(r"sha256/\{"),
        re.compile(r"_content_path"),
        re.compile(r"_managed_root"),
        re.compile(r"shutil\.move"),
        re.compile(r"os\.link"),
        re.compile(r"/\s*content_uri"),
    )
    for root in RUNTIME_ROOTS:
        for path in root.rglob("*.py"):
            if path == STORE_MODULE or "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in forbidden:
                if pattern.search(text):
                    violations.append(
                        f"{path.relative_to(PROJECT_ROOT)}: {pattern.pattern}"
                    )
    assert violations == []


def test_no_runtime_module_recreates_the_hash_shard_algorithm() -> None:
    """Search all Python runtime trees for managed-object shard construction."""
    violations: list[str] = []
    forbidden = (
        re.compile(r"""f["']sha256/"""),
        re.compile(r"""["']sha256/["']\s*\+"""),
        re.compile(r"\b(?:content_sha256|digest)\s*\[\s*(?:0\s*)?:\s*2\s*\]"),
        re.compile(r"\b(?:content_sha256|digest)\s*\[\s*2\s*:\s*4\s*\]"),
        re.compile(r"(?:/|joinpath\()[^\n]*content_uri"),
    )
    for root in REPOSITORY_RUNTIME_ROOTS:
        for path in root.rglob("*.py"):
            if path == STORE_MODULE or "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in forbidden:
                if pattern.search(text):
                    violations.append(
                        f"{path.relative_to(PROJECT_ROOT)}: {pattern.pattern}"
                    )
    assert violations == []


def test_database_code_does_not_resolve_physical_managed_paths() -> None:
    """Allow durable key validation but no filesystem path construction in SQL."""
    code_root = PROJECT_ROOT / "resources" / "db" / "schema" / "orac_code"
    violations: list[str] = []
    for path in code_root.rglob("*.sql"):
        text = path.read_text(encoding="utf-8").lower()
        for token in ("managed_root", "/var/knowledge", ".tmp/capture-"):
            if token in text:
                violations.append(f"{path.relative_to(PROJECT_ROOT)}: {token}")
    assert violations == []
