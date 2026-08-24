"""Tests for canonical spreadsheet CSV chunking."""

# Author: Clive Bostock
# Date: 12-Aug-2026
# Description: Verifies record boundaries and worksheet row provenance.

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from orac_core.knowledge.csv_chunking import chunk_csv  # noqa: E402


class KnowledgeCsvChunkingTests(unittest.TestCase):
    """Tests CSV record grouping and canonical-input rejection."""

    def test_multiline_record_remains_whole(self) -> None:
        text = 'name,notes\nAda,"first line\nsecond line"\nGrace,compiler\n'

        chunks = chunk_csv(
            text,
            source_cell_range="B7:C9",
            chunk_size_tokens=4,
        )

        self.assertEqual("".join(chunk.text for chunk in chunks), text)
        self.assertTrue(any("first line\nsecond line" in chunk.text for chunk in chunks))
        metadata = [json.loads(chunk.metadata_json) for chunk in chunks]
        self.assertEqual(metadata[0]["source_row_start"], 7)
        self.assertEqual(metadata[-1]["source_row_end"], 9)
        self.assertEqual(metadata[-1]["source_cell_range"], "B9:C9")

    def test_rejects_noncanonical_or_invalid_csv(self) -> None:
        cases = (
            ("a,b\r\n1,2\r\n", "A1:B2"),
            ("a,b\n1,2", "A1:B2"),
            ('a,b\n"unterminated\n', "A1:B2"),
            ("a,b\n", "not-a-range"),
        )
        for text, source_range in cases:
            with self.subTest(text=repr(text), source_range=source_range):
                with self.assertRaises(ValueError):
                    chunk_csv(
                        text,
                        source_cell_range=source_range,
                        chunk_size_tokens=10,
                    )


if __name__ == "__main__":
    unittest.main()
