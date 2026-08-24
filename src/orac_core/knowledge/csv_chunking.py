"""Chunk canonical CSV artefacts on complete record boundaries."""

# Author: Clive Bostock
# Date: 12-Aug-2026
# Description: Produces bounded CSV chunks with spreadsheet row provenance.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

import csv
from dataclasses import dataclass
import io
import json
import re


@dataclass(frozen=True)
class CsvChunk:
    """One CSV record group with source-range metadata."""

    chunk_no: int
    span_start: int
    span_end: int
    text: str
    token_count: int
    metadata_json: str


def chunk_csv(
    text: str,
    *,
    source_cell_range: str,
    chunk_size_tokens: int,
) -> list[CsvChunk]:
    """Split CSV text without cutting quoted or multiline records.

    Args:
        text: Canonical UTF-8 CSV decoded to text.
        source_cell_range: Canonical worksheet A1 range for the member.
        chunk_size_tokens: Approximate maximum token count per chunk.

    Returns:
        Ordered record-boundary chunks with workbook row provenance.

    Raises:
        ValueError: If the CSV or source range is malformed.
    """
    match = re.fullmatch(
        r"(?P<start_col>[A-Z]+)(?P<start_row>[1-9][0-9]*):"
        r"(?P<end_col>[A-Z]+)(?P<end_row>[1-9][0-9]*)",
        source_cell_range,
    )
    if match is None:
        raise ValueError("CSV member source_cell_range is invalid.")
    if not text or not text.endswith("\n") or "\r" in text:
        raise ValueError("Canonical CSV must end with LF and contain no CR.")

    records = _record_spans(text=text)
    if not records:
        return []
    budget = max(1, chunk_size_tokens) * 4
    start_row = int(match.group("start_row"))
    chunks: list[CsvChunk] = []
    group: list[tuple[int, int]] = []
    group_size = 0

    def emit() -> None:
        nonlocal group, group_size
        if not group:
            return
        span_start = group[0][0]
        span_end = group[-1][1]
        row_start = start_row + records.index(group[0])
        row_end = start_row + records.index(group[-1])
        chunk_text = text[span_start:span_end]
        metadata = {
            "schema_version": 1,
            "source_row_start": row_start,
            "source_row_end": row_end,
            "source_cell_range": (
                f"{match.group('start_col')}{row_start}:"
                f"{match.group('end_col')}{row_end}"
            ),
        }
        chunks.append(
            CsvChunk(
                chunk_no=len(chunks) + 1,
                span_start=span_start,
                span_end=span_end,
                text=chunk_text,
                token_count=max(1, (len(chunk_text) + 3) // 4),
                metadata_json=json.dumps(
                    metadata,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            )
        )
        group = []
        group_size = 0

    for record in records:
        record_size = record[1] - record[0]
        if group and group_size + record_size > budget:
            emit()
        group.append(record)
        group_size += record_size
    emit()
    return chunks


def _record_spans(text: str) -> list[tuple[int, int]]:
    """Return character spans for records accepted by ``csv.reader``."""
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    spans: list[tuple[int, int]] = []
    previous_line = 0
    try:
        for _record in reader:
            current_line = reader.line_num
            spans.append((offsets[previous_line], offsets[current_line]))
            previous_line = current_line
    except csv.Error as exc:
        raise ValueError("CSV member is malformed.") from exc
    return spans
