"""Tests for committed knowledge ingestion fixtures."""
# Author: Clive Bostock
# Date: 13-Jul-2026
# Description: Ensures live ingestion fixtures stay isolated from product docs.

from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_SENTENCE = "ORAC_INGESTION_FIXTURE_20260713_LUMEN_PATHWAY"


class KnowledgeFixtureTests(unittest.TestCase):
    """Tests the committed knowledge fixture location."""

    def test_fixture_sentence_lives_under_knowledge_fixtures_only(self) -> None:
        fixture_path = PROJECT_ROOT / "tests" / "fixtures" / "knowledge" / "drop_box_fixture.md"
        self.assertIn(FIXTURE_SENTENCE, fixture_path.read_text(encoding="utf-8"))

        product_docs = [
            *PROJECT_ROOT.glob("*.md"),
            *PROJECT_ROOT.joinpath("docs").rglob("*.md"),
            *PROJECT_ROOT.joinpath("plugins").rglob("README.md"),
        ]
        product_hits = [
            path
            for path in product_docs
            if FIXTURE_SENTENCE in path.read_text(encoding="utf-8", errors="ignore")
        ]
        self.assertEqual(product_hits, [])


if __name__ == "__main__":
    unittest.main()
