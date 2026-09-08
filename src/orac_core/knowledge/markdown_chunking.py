"""Deterministically split canonical Markdown into structure-aware chunks."""

# Author: Clive Bostock
# Date: 07-Sep-2026
# Description: Implements context-safe core Markdown chunking and provenance.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Callable

from .token_accounting import ConservativeEmbeddingTokenCounter
_ATX = re.compile(r" {0,3}#{1,6}(?:[ \t]+|$)")
_SETEXT = re.compile(r" {0,3}(?:=+|-+)[ \t]*$")
_FENCE = re.compile(r" {0,3}(`{3,}|~{3,})")
_LIST = re.compile(r" {0,3}(?:[-+*]|\d+[.)])[ \t]+")
_QUOTE = re.compile(r" {0,3}>")
_THEMATIC = re.compile(r" {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$")
_TABLE_DELIMITER = re.compile(
    r" {0,3}\|?[ \t]*:?-{3,}:?[ \t]*(?:\|[ \t]*:?-{3,}:?[ \t]*)+\|?[ \t]*$"
)
_HTML = re.compile(r" {0,3}</?[A-Za-z][^>]*>")


@dataclass(frozen=True)
class MarkdownChunk:
    """One emitted Markdown chunk with source-coordinate provenance."""

    chunk_no: int
    span_start: int
    span_end: int
    text: str
    token_count: int
    metadata_json: str | None = None


@dataclass(frozen=True)
class _Block:
    kind: str
    start: int
    end: int
    text: str
    auxiliary: tuple[str, ...] = ()

    def tokens(self, counter: Callable[[str], int]) -> int:
        """Return the configured conservative token estimate."""
        return counter(self.text)


def chunk_markdown(
    text: str,
    *,
    chunk_size_tokens: int,
    overlap_tokens: int,
    token_counter: Callable[[str], int] | None = None,
    max_content_tokens: int | None = None,
) -> list[MarkdownChunk]:
    """Split Markdown with stable zero-based half-open code-point offsets.

    ``chunk_size_tokens`` remains the desired target. ``max_content_tokens``
    is the hard provider-aware content ceiling after prefix, special-token,
    and safety-margin costs. Both use the supplied counter.
    """
    if chunk_size_tokens <= 0:
        raise ValueError("chunk_size_tokens must be positive")
    counter = token_counter or ConservativeEmbeddingTokenCounter().content_tokens
    hard_limit = max_content_tokens or chunk_size_tokens
    if hard_limit <= 0:
        raise ValueError("max_content_tokens must be positive")
    target = min(chunk_size_tokens, hard_limit)
    overlap_tokens = max(0, min(overlap_tokens, target - 1))
    blocks = _scan_blocks(text)
    expanded: list[_Block] = []
    for block in blocks:
        expanded.extend(_split_oversized(block, target, counter))
    groups: list[list[_Block]] = []
    current: list[_Block] = []
    for block in expanded:
        candidate = current + [block]
        if current and counter(_emit_group(candidate)) > target:
            groups.append(current)
            overlap: list[_Block] = []
            for prior in reversed(current):
                overlap_candidate = [prior] + overlap
                if counter(_emit_group(overlap_candidate)) > overlap_tokens:
                    break
                overlap = overlap_candidate
            current = overlap
        current.append(block)
    if current:
        groups.append(current)

    chunks: list[MarkdownChunk] = []
    for chunk_no, group in enumerate(groups, start=1):
        emitted = _emit_group(group)
        segments = [[block.start, block.end] for block in group]
        synthetic = [
            value
            for block in group
            for value in block.auxiliary
        ]
        metadata = None
        if synthetic or len(segments) > 1:
            metadata = json.dumps(
                {
                    "schema_version": 1,
                    "source_segments": segments,
                    "synthetic_parts": synthetic,
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        chunks.append(
            MarkdownChunk(
                chunk_no=chunk_no,
                span_start=min(block.start for block in group),
                span_end=max(block.end for block in group),
                text=emitted,
                token_count=counter(emitted),
                metadata_json=metadata,
            )
        )
    return chunks


def _emit_group(group: list[_Block]) -> str:
    """Render one group exactly as it will be persisted and embedded."""
    emitted = "\n\n".join(block.text.rstrip("\n") for block in group)
    if group and group[-1].text.endswith("\n"):
        emitted += "\n"
    return emitted


def _scan_blocks(text: str) -> list[_Block]:
    lines = list(re.finditer(r".*(?:\n|$)", text))
    if lines and lines[-1].group() == "":
        lines.pop()
    blocks: list[_Block] = []
    index = 0
    while index < len(lines):
        value = lines[index].group()
        stripped = value.rstrip("\n")
        if not stripped.strip():
            index += 1
            continue
        fence = _FENCE.match(stripped)
        if fence:
            marker = fence.group(1)
            end = index + 1
            closing = re.compile(rf" {{0,3}}{re.escape(marker[0])}{{{len(marker)},}}[ \t]*$")
            while end < len(lines):
                if closing.match(lines[end].group().rstrip("\n")):
                    end += 1
                    break
                end += 1
            blocks.append(_block("fenced_code", lines, index, end))
            index = end
            continue
        if index + 1 < len(lines) and _SETEXT.match(
            lines[index + 1].group().rstrip("\n")
        ):
            blocks.append(_block("heading", lines, index, index + 2))
            index += 2
            continue
        if _ATX.match(stripped) or _THEMATIC.match(stripped):
            blocks.append(_block("heading" if _ATX.match(stripped) else "thematic", lines, index, index + 1))
            index += 1
            continue
        if _TABLE_DELIMITER.match(
            lines[index + 1].group().rstrip("\n") if index + 1 < len(lines) else ""
        ) and "|" in stripped:
            end = index + 2
            while end < len(lines) and "|" in lines[end].group() and lines[end].group().strip():
                end += 1
            blocks.append(_block("table", lines, index, end))
            index = end
            continue
        if _LIST.match(stripped):
            end = index + 1
            while end < len(lines):
                next_line = lines[end].group().rstrip("\n")
                if not next_line.strip():
                    if end + 1 < len(lines) and (
                        _LIST.match(lines[end + 1].group())
                        or lines[end + 1].group().startswith((" ", "\t"))
                    ):
                        end += 1
                        continue
                    break
                if _LIST.match(next_line) or next_line.startswith((" ", "\t")):
                    end += 1
                    continue
                break
            blocks.append(_block("list", lines, index, end))
            index = end
            continue
        kind = (
            "blockquote" if _QUOTE.match(stripped)
            else "indented_code" if value.startswith(("    ", "\t"))
            else "html" if _HTML.match(stripped)
            else "paragraph"
        )
        end = index + 1
        while end < len(lines) and lines[end].group().strip():
            next_value = lines[end].group().rstrip("\n")
            if kind == "blockquote" and not _QUOTE.match(next_value):
                break
            if kind == "indented_code" and not lines[end].group().startswith(("    ", "\t")):
                break
            if kind == "paragraph" and (
                _ATX.match(next_value)
                or _FENCE.match(next_value)
                or _LIST.match(next_value)
                or _QUOTE.match(next_value)
                or _THEMATIC.match(next_value)
            ):
                break
            end += 1
        blocks.append(_block(kind, lines, index, end))
        index = end
    return blocks


def _block(kind: str, lines: list[re.Match[str]], start: int, end: int) -> _Block:
    return _Block(
        kind=kind,
        start=lines[start].start(),
        end=lines[end - 1].end(),
        text="".join(line.group() for line in lines[start:end]),
    )


def _split_oversized(
    block: _Block,
    budget: int,
    counter: Callable[[str], int],
) -> list[_Block]:
    if block.tokens(counter) <= budget:
        return [block]
    if block.kind == "fenced_code":
        pieces = _split_fence(block, budget, counter)
        return _ensure_fit(pieces, budget, counter)
    if block.kind == "table":
        pieces = _split_table(block, budget, counter)
        return _ensure_fit(pieces, budget, counter)
    if block.kind == "list":
        pieces = _split_lines(block, budget, boundary=_LIST)
        if all(piece.tokens(counter) <= budget for piece in pieces):
            return pieces
    return _text_windows(block, budget, counter)


def _split_fence(
    block: _Block,
    budget: int,
    counter: Callable[[str], int],
) -> list[_Block]:
    lines = block.text.splitlines(keepends=True)
    if len(lines) < 2:
        return _text_windows(block, budget, counter)
    opener = lines[0].rstrip("\n")
    marker = _FENCE.match(opener)
    closer = marker.group(1) if marker else "```"
    content = lines[1:-1] if lines[-1].lstrip().startswith(closer[0]) else lines[1:]
    pieces: list[_Block] = []
    cursor = block.start + len(lines[0])
    selected: list[str] = []
    selected_start = cursor
    for line in content:
        candidate = f"{opener}\n{''.join(selected)}{line}{closer}\n"
        if selected and counter(candidate) > budget:
            emitted = f"{opener}\n{''.join(selected)}{closer}\n"
            pieces.append(
                _Block(
                    "fenced_code_fragment",
                    selected_start,
                    cursor,
                    emitted,
                    ("recreated_fence_open", "recreated_fence_close"),
                )
            )
            selected = []
            selected_start = cursor
        selected.append(line)
        cursor += len(line)
    if selected:
        pieces.append(
            _Block(
                "fenced_code_fragment",
                selected_start,
                cursor,
                f"{opener}\n{''.join(selected)}{closer}\n",
                ("recreated_fence_open", "recreated_fence_close"),
            )
        )
    return pieces or _text_windows(block, budget, counter)


def _split_table(
    block: _Block,
    budget: int,
    counter: Callable[[str], int],
) -> list[_Block]:
    lines = block.text.splitlines(keepends=True)
    if len(lines) < 3:
        return _text_windows(block, budget, counter)
    header = "".join(lines[:2])
    offset = block.start + len(header)
    pieces: list[_Block] = []
    selected: list[str] = []
    selected_start = offset
    for row in lines[2:]:
        if selected and counter(header + "".join(selected) + row) > budget:
            pieces.append(
                _Block(
                    "table_fragment",
                    selected_start,
                    offset,
                    header + "".join(selected),
                    ("repeated_table_header",),
                )
            )
            selected = []
            selected_start = offset
        selected.append(row)
        offset += len(row)
    if selected:
        pieces.append(
            _Block(
                "table_fragment",
                selected_start,
                offset,
                header + "".join(selected),
                ("repeated_table_header",),
            )
        )
    return pieces or _text_windows(block, budget, counter)


def _split_lines(
    block: _Block, budget: int, *, boundary: re.Pattern[str]
) -> list[_Block]:
    lines = block.text.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if boundary.match(line)]
    if not starts:
        return [block]
    starts.append(len(lines))
    offset = block.start
    line_offsets = []
    for line in lines:
        line_offsets.append(offset)
        offset += len(line)
    return [
        _Block(
            block.kind,
            line_offsets[starts[index]],
            block.end if starts[index + 1] == len(lines) else line_offsets[starts[index + 1]],
            "".join(lines[starts[index]:starts[index + 1]]),
        )
        for index in range(len(starts) - 1)
    ]


def _ensure_fit(
    blocks: list[_Block],
    budget: int,
    counter: Callable[[str], int],
) -> list[_Block]:
    """Ensure structural fragments also obey the hard content ceiling."""
    pieces: list[_Block] = []
    for block in blocks:
        if block.tokens(counter) <= budget:
            pieces.append(block)
        else:
            pieces.extend(_text_windows(block, budget, counter))
    return pieces


def _text_windows(
    block: _Block,
    budget: int,
    counter: Callable[[str], int],
) -> list[_Block]:
    """Split an oversized block without dropping whitespace or punctuation."""
    pieces: list[_Block] = []
    remaining = block.text
    relative_start = 0
    while remaining:
        low = 1
        high = len(remaining)
        accepted = 0
        while low <= high:
            middle = (low + high) // 2
            if counter(remaining[:middle]) <= budget:
                accepted = middle
                low = middle + 1
            else:
                high = middle - 1
        if accepted == 0:
            raise ValueError("token counter cannot fit one source code point")
        emitted = remaining[:accepted]
        relative_end = relative_start + accepted
        pieces.append(
            _Block(
                f"{block.kind}_fragment",
                block.start + relative_start,
                block.start + relative_end,
                emitted,
            )
        )
        remaining = remaining[accepted:]
        relative_start = relative_end
    return pieces
