"""Unit tests for streamed text chunking."""

# Author: Clive Bostock
# Date: 2026-05-04
# Description: Verifies grammatical chunking of streamed Orac text deltas.

from __future__ import annotations

import unittest
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


from model.text_chunker import TextChunker


class TextChunkerTests(unittest.TestCase):
    """Verify streamed delta chunking behaviour."""

    def test_sentence_punctuation_emits_chunks(self) -> None:
        """Sentence stops should produce complete chunks."""
        chunker = TextChunker()

        chunks = chunker.add_delta("Hello there. How are you? Fine!")

        self.assertEqual(chunks, ["Hello there.", "How are you?", "Fine!"])
        self.assertIsNone(chunker.flush())

    def test_optional_boundaries_emit_chunks(self) -> None:
        """Semicolons, colons, and newlines should be supported."""
        chunker = TextChunker()

        chunks = chunker.add_delta("One: two; three\nfour")

        self.assertEqual(chunks, ["One:", "two;", "three"])
        self.assertEqual(chunker.flush(), "four")

    def test_decimal_does_not_split(self) -> None:
        """Decimal numbers should remain intact."""
        chunker = TextChunker()

        chunks = chunker.add_delta("Pi is about 3.14. Good.")

        self.assertEqual(chunks, ["Pi is about 3.14.", "Good."])

    def test_abbreviations_do_not_split(self) -> None:
        """Common abbreviations should not end a chunk."""
        chunker = TextChunker()

        chunks = chunker.add_delta("Dr. Smith used e.g. one example. Done.")

        self.assertEqual(chunks, ["Dr. Smith used e.g. one example.", "Done."])

    def test_ellipses_do_not_split_mid_sequence(self) -> None:
        """Ellipses should not create several tiny chunks."""
        chunker = TextChunker()

        chunks = chunker.add_delta("Thinking... done.")

        self.assertEqual(chunks, ["Thinking... done."])

    def test_url_does_not_split(self) -> None:
        """URL-like tokens should not be split at their full stops."""
        chunker = TextChunker()

        chunks = chunker.add_delta("See https://example.com/path. Then continue.")

        self.assertEqual(chunks, ["See https://example.com/path. Then continue."])

    def test_flush_returns_remainder(self) -> None:
        """End-of-stream should flush any residual buffer."""
        chunker = TextChunker()

        self.assertEqual(chunker.add_delta("Partial answer"), [])
        self.assertEqual(chunker.flush(), "Partial answer")
        self.assertIsNone(chunker.flush())

    def test_max_buffer_forces_chunk(self) -> None:
        """Long text without punctuation should still be chunked."""
        chunker = TextChunker(max_buffer_chars=50)
        text = "alpha beta gamma delta epsilon zeta eta theta iota kappa"

        chunks = chunker.add_delta(text)

        self.assertTrue(chunks)
        self.assertLessEqual(len(chunks[0]), 50)
        self.assertEqual(chunker.flush(), "iota kappa")


if __name__ == "__main__":
    unittest.main()
