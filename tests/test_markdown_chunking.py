"""Tests for deterministic structure-aware Markdown chunking."""

# Author: Clive Bostock
# Date: 07-Sep-2026
# Description: Verifies provider-safe chunk accounting, structure, and provenance.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from orac_core.knowledge.markdown_chunking import chunk_markdown  # noqa: E402
from orac_core.knowledge.token_accounting import (  # noqa: E402
    ConservativeEmbeddingTokenCounter,
)


class MarkdownChunkingTests(unittest.TestCase):
    """Tests context-safe core_markdown_blocks version two."""

    def setUp(self) -> None:
        """Use the production conservative counter for every test."""
        self.counter = ConservativeEmbeddingTokenCounter()

    def _chunks(
        self,
        text: str,
        *,
        target: int,
        overlap: int = 0,
        hard_limit: int | None = None,
    ):
        """Chunk text using the production accounting contract."""
        return chunk_markdown(
            text,
            chunk_size_tokens=target,
            overlap_tokens=overlap,
            token_counter=self.counter.content_tokens,
            max_content_tokens=hard_limit,
        )

    def test_repeated_runs_preserve_unicode_code_point_spans(self) -> None:
        text = "# Héading 😀\n\nFirst paragraph.\n\nSecond 𐐷 paragraph.\n"
        first = self._chunks(text, target=24)
        second = self._chunks(text, target=24)

        self.assertEqual(first, second)
        for chunk in first:
            if chunk.metadata_json is None:
                self.assertEqual(
                    chunk.text,
                    text[chunk.span_start : chunk.span_end],
                )

    def test_fenced_code_is_kept_whole_when_it_fits(self) -> None:
        text = "```python\nprint('one')\nprint('two')\n```\n"
        chunks = self._chunks(text, target=64)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].text, text)

    def test_oversized_table_repeats_header_with_source_metadata(self) -> None:
        text = "| A | B |\n|---|---|\n| one | two |\n| three | four |\n"
        chunks = self._chunks(text, target=36)

        self.assertGreaterEqual(len(chunks), 2)
        metadata = json.loads(chunks[0].metadata_json or "{}")
        self.assertIn("repeated_table_header", metadata["synthetic_parts"])
        self.assertTrue(chunks[0].text.startswith("| A | B |\n|---|---|\n"))

    def test_overlap_uses_complete_blocks(self) -> None:
        text = "alpha beta\n\ncharlie delta\n\necho foxtrot\n"
        chunks = self._chunks(text, target=29, overlap=14)
        self.assertEqual(len(chunks), 2)
        self.assertIn("charlie delta", chunks[0].text)
        self.assertIn("charlie delta", chunks[1].text)

    def test_pathological_inputs_fit_prefixed_profile_budget(self) -> None:
        """Every corrected chunk fits after the production document prefix."""
        cases = (
            "Ordinary prose with several short sentences. " * 80,
            ("Chapter.1........Section.2........Page.999\n" * 100),
            "x" * 6000,
            ("path/to_value_name?x=1&y=2::segment..." * 160),
            "# Heading\n\n- first item\n- second item\n" * 100,
        )
        prefix = "search_document: "
        usable_limit = 1984
        content_limit = usable_limit - self.counter.input_tokens(prefix)
        for text in cases:
            with self.subTest(sample=text[:20]):
                chunks = self._chunks(
                    text,
                    target=1536,
                    overlap=192,
                    hard_limit=content_limit,
                )
                self.assertTrue(chunks)
                for chunk in chunks:
                    self.assertLessEqual(
                        self.counter.input_tokens(prefix + chunk.text),
                        usable_limit,
                    )

    def test_exact_hard_limit_and_just_over_limit_split(self) -> None:
        """The exact boundary fits and one byte over produces two chunks."""
        limit = 64
        exact = self._chunks("a" * limit, target=limit, hard_limit=limit)
        over = self._chunks("a" * (limit + 1), target=limit, hard_limit=limit)
        self.assertEqual(len(exact), 1)
        self.assertEqual(exact[0].token_count, limit)
        self.assertEqual(len(over), 2)

    def test_oversized_low_whitespace_text_has_no_loss(self) -> None:
        """Recursive code-point splitting neither drops nor duplicates source."""
        text = ("alpha_beta.gamma/delta?x=1&y=2;" * 100) + "tail"
        chunks = self._chunks(text, target=128, hard_limit=128)
        self.assertEqual("".join(chunk.text for chunk in chunks), text)
        self.assertLess(chunks[-1].token_count, 128)


if __name__ == "__main__":
    unittest.main()
