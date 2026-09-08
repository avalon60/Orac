"""Behavioural quality checks for the authorised semantic knowledge corpus."""

# Author: Clive Bostock
# Date: 2026-09-01
# Description: Evaluates paraphrase overlap, lexical precision, and negatives.

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
from orac_core.knowledge.retrieval import KnowledgeRetrievalService  # noqa: E402
from orac_core.knowledge.scope import KnowledgeScope  # noqa: E402


pytestmark = pytest.mark.skipif(
    os.environ.get("ORAC_RUN_KNOWLEDGE_QUALITY") != "1",
    reason="set ORAC_RUN_KNOWLEDGE_QUALITY=1 after authorised corpus ingestion",
)

PARAPHRASES = (
    "What is John Elder's AI OS?",
    "Explain John Elder's AI operating system.",
    "What does Elder mean by AI-OS?",
    "Describe Elder's proposed AI architecture.",
)


def _service() -> KnowledgeRetrievalService:
    """Build the production service with the configured pinned profile."""
    config = ConfigManager(
        config_file_path=PROJECT_ROOT / "resources/config/orac.ini"
    )
    return KnowledgeRetrievalService(
        embedding_provider=knowledge_embedding_provider(config)
    )


def _principal() -> str:
    """Return the explicitly authorised evaluation principal."""
    principal = os.environ.get("ORAC_KNOWLEDGE_QUALITY_PRINCIPAL", "").strip()
    if not principal:
        pytest.fail("ORAC_KNOWLEDGE_QUALITY_PRINCIPAL is required")
    return principal


def test_ai_os_paraphrases_return_overlapping_bounded_evidence() -> None:
    """Natural paraphrases should converge on materially overlapping chunks."""
    service = _service()
    result_sets: list[set[int]] = []
    for query in PARAPHRASES:
        outcome = service.retrieve(
            query,
            principal_username=_principal(),
            scope=KnowledgeScope("PROJECT", "ORAC_CORE"),
            max_selected_chunks=6,
        )
        assert outcome.status == "grounded"
        assert 1 <= len(outcome.results) <= 6
        result_sets.append({result.chunk_id for result in outcome.results})

    baseline = result_sets[0]
    assert all(baseline & candidates for candidates in result_sets[1:])


def test_exact_names_remain_strong_and_negative_query_does_not_ground() -> None:
    """Lexical identity survives hybrid fusion and absent evidence stays absent."""
    service = _service()
    exact = service.retrieve(
        "John Elder AI-OS",
        principal_username=_principal(),
        scope=KnowledgeScope("PROJECT", "ORAC_CORE"),
        max_selected_chunks=6,
    )
    negative = service.retrieve(
        "Explain mitochondrial ribosome assembly in Antarctic krill.",
        principal_username=_principal(),
        scope=KnowledgeScope("PROJECT", "ORAC_CORE"),
        max_selected_chunks=6,
    )

    assert exact.status == "grounded"
    assert any(result.lexical_score > 0 for result in exact.results)
    assert negative.status == "no_evidence"
