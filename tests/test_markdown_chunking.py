"""Tests for deterministic structure-aware Markdown chunking."""

# Author: Clive Bostock
# Date: 24-Jul-2026
# Description: Verifies block preservation, spans, overlap, and synthetic metadata.

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


class MarkdownChunkingTests(unittest.TestCase):
    """Tests core_markdown_blocks version one."""

    def test_repeated_runs_preserve_unicode_code_point_spans(self) -> None:
        text = "# Héading 😀\n\nFirst paragraph.\n\nSecond 𐐷 paragraph.\n"
        first = chunk_markdown(text, chunk_size_tokens=5, overlap_tokens=0)
        second = chunk_markdown(text, chunk_size_tokens=5, overlap_tokens=0)

        self.assertEqual(first, second)
        for chunk in first:
            if chunk.metadata_json is None:
                self.assertEqual(
                    chunk.text,
                    text[chunk.span_start : chunk.span_end],
                )

    def test_fenced_code_is_kept_whole_when_it_fits(self) -> None:
        text = "```python\nprint('one')\nprint('two')\n```\n"
        chunks = chunk_markdown(text, chunk_size_tokens=20, overlap_tokens=0)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].text, text)

    def test_oversized_table_repeats_header_with_source_metadata(self) -> None:
        text = "| A | B |\n|---|---|\n| one | two |\n| three | four |\n"
        chunks = chunk_markdown(text, chunk_size_tokens=8, overlap_tokens=0)

        self.assertGreaterEqual(len(chunks), 2)
        metadata = json.loads(chunks[0].metadata_json or "{}")
        self.assertIn("repeated_table_header", metadata["synthetic_parts"])
        self.assertTrue(chunks[0].text.startswith("| A | B |\n|---|---|\n"))

    def test_overlap_uses_complete_blocks(self) -> None:
        text = "alpha beta\n\ncharlie delta\n\necho foxtrot\n"
        chunks = chunk_markdown(text, chunk_size_tokens=4, overlap_tokens=2)
        self.assertEqual(len(chunks), 2)
        self.assertIn("charlie delta", chunks[0].text)
        self.assertIn("charlie delta", chunks[1].text)


if __name__ == "__main__":
    unittest.main()
