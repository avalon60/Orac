"""Bounded integration test for the configured knowledge embedding provider."""

# Author: Clive Bostock
# Date: 07-Sep-2026
# Description: Verifies corrected pathological chunks against local Ollama.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from lib.config_mgr import ConfigManager  # noqa: E402
from orac_core.knowledge.embeddings import knowledge_embedding_provider  # noqa: E402
from orac_core.knowledge.markdown_chunking import chunk_markdown  # noqa: E402


@pytest.mark.skipif(
    os.environ.get("ORAC_RUN_OLLAMA_INTEGRATION") != "1",
    reason="set ORAC_RUN_OLLAMA_INTEGRATION=1 for the bounded local probe",
)
def test_corrected_chunks_embed_with_configured_local_ollama() -> None:
    """Representative corrected chunks produce finite 768-value vectors."""
    config = ConfigManager(
        config_file_path=PROJECT_ROOT / "resources/config/orac.ini"
    )
    provider = knowledge_embedding_provider(config)
    content = (
        "# The AI Operating System\n\n"
        + "Chapter.1........Workflow.Index........Page.999\n" * 80
        + "\n"
        + "folder/workflows/code/data_memory/logs/orchestrator/principal::" * 80
    )
    chunks = chunk_markdown(
        content,
        chunk_size_tokens=config.int_config_value(
            "knowledge", "chunk_size_tokens", default=1536
        ),
        overlap_tokens=config.int_config_value(
            "knowledge", "chunk_overlap_tokens", default=192
        ),
        token_counter=provider.count_content_tokens,
        max_content_tokens=provider.document_content_token_limit,
    )

    representative = [chunks[0], chunks[len(chunks) // 2], chunks[-1]]
    for chunk in representative:
        provider.validate_document_text(chunk.text)
    vectors = provider.embed_texts([chunk.text for chunk in representative])

    assert len(vectors) == len(representative)
    assert all(len(vector) == 768 for vector in vectors)
