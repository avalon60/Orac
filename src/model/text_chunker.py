"""Streamed text chunking helpers for Orac."""

# Author: Clive Bostock
# Date: 2026-05-04
# Description: Provides grammatical text chunking for streamed LLM deltas.

from __future__ import annotations


DEFAULT_MAX_BUFFER_CHARS = 240

_BOUNDARY_CHARS = {".", "!", "?", ";", ":", "\n"}
_ABBREVIATIONS = {
    "mr",
    "mrs",
    "ms",
    "dr",
    "prof",
    "sr",
    "jr",
    "st",
    "vs",
    "etc",
    "e.g",
    "i.e",
}


class TextChunker:
    """Accumulate streamed text and emit speech-friendly chunks.

    The chunker is deliberately conservative around full stops because
    streamed LLM output commonly contains decimals, abbreviations,
    ellipses, and URLs. Any residual text is returned by ``flush()`` at
    end-of-stream.

    Args:
        max_buffer_chars: Maximum buffered characters before a forced
            chunk is emitted.
        include_optional_boundaries: Whether semicolon, colon, and
            newline boundaries are used in addition to sentence stops.
    """

    def __init__(
        self,
        max_buffer_chars: int = DEFAULT_MAX_BUFFER_CHARS,
        *,
        include_optional_boundaries: bool = True,
    ) -> None:
        self.max_buffer_chars = max(40, int(max_buffer_chars))
        self.include_optional_boundaries = include_optional_boundaries
        self._buffer = ""

    def add_delta(self, text: str) -> list[str]:
        """Add a streamed text delta and return completed chunks.

        Args:
            text: New text from the LLM stream.

        Returns:
            Completed grammatical chunks, if any.
        """
        if not text:
            return []

        self._buffer += str(text)
        chunks: list[str] = []

        while True:
            boundary = self._find_boundary()
            if boundary is None:
                break
            chunk = self._pop_chunk(boundary + 1)
            if chunk:
                chunks.append(chunk)

        while len(self._buffer) >= self.max_buffer_chars:
            split_at = self._find_forced_split()
            chunk = self._pop_chunk(split_at)
            if not chunk:
                break
            chunks.append(chunk)

        return chunks

    def flush(self) -> str | None:
        """Return and clear any remaining buffered text.

        Returns:
            The remaining buffered text, or ``None`` when empty.
        """
        chunk = self._buffer.strip()
        self._buffer = ""
        return chunk or None

    def reset(self) -> None:
        """Clear the current buffer."""
        self._buffer = ""

    def _find_boundary(self) -> int | None:
        """Return the next safe boundary index, if one exists."""
        for index, char in enumerate(self._buffer):
            if char not in _BOUNDARY_CHARS:
                continue
            if not self.include_optional_boundaries and char in {";", ":", "\n"}:
                continue
            if self._is_safe_boundary(index, char):
                return index
        return None

    def _is_safe_boundary(self, index: int, char: str) -> bool:
        """Return whether a punctuation mark can end a chunk."""
        if char == "\n":
            return True

        next_char = self._buffer[index + 1] if index + 1 < len(self._buffer) else ""
        if next_char and next_char not in " \t\r\n)]}\"'":
            return False

        if char == ".":
            prev_char = self._buffer[index - 1] if index > 0 else ""
            if prev_char.isdigit() and next_char.isdigit():
                return False
            if prev_char == "." or next_char == ".":
                return False
            if self._is_abbreviation_at(index):
                return False
            if self._is_url_at(index):
                return False

        return True

    def _is_abbreviation_at(self, index: int) -> bool:
        """Return whether a full stop appears in a known abbreviation."""
        start = self._buffer.rfind(" ", 0, index) + 1
        token = self._buffer[start:index + 1].strip("\"'()[]{}")
        token = token.rstrip(".").lower()
        return token in _ABBREVIATIONS

    def _is_url_at(self, index: int) -> bool:
        """Return whether a full stop appears inside a URL-like token."""
        start = max(
            self._buffer.rfind(" ", 0, index),
            self._buffer.rfind("\n", 0, index),
            self._buffer.rfind("\t", 0, index),
        ) + 1
        end_candidates = [
            pos for pos in (
                self._buffer.find(" ", index),
                self._buffer.find("\n", index),
                self._buffer.find("\t", index),
            )
            if pos != -1
        ]
        end = min(end_candidates) if end_candidates else len(self._buffer)
        token = self._buffer[start:end].strip("\"'()[]{}")
        lowered = token.lower()
        return (
            lowered.startswith("http://")
            or lowered.startswith("https://")
            or lowered.startswith("www.")
        )

    def _find_forced_split(self) -> int:
        """Find a readable forced split point within the buffer limit."""
        candidate = self._buffer.rfind(" ", 0, self.max_buffer_chars)
        if candidate >= max(20, self.max_buffer_chars // 2):
            return candidate + 1
        return self.max_buffer_chars

    def _pop_chunk(self, end_index: int) -> str:
        """Remove and return text up to ``end_index``."""
        chunk = self._buffer[:end_index].strip()
        self._buffer = self._buffer[end_index:].lstrip()
        return chunk
