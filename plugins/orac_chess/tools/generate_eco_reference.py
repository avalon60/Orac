"""Validate the pinned ECO source and generate immutable installation reference data."""

# Author: Clive Bostock
# Date: 07-Nov-2026
# Description: Package all 500 ECO codes with their distinct English opening names.
# Purpose: Generate reference data without installation-time Python or network access.
# Usage: python plugins/orac_chess/tools/generate_eco_reference.py --check

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import logging
from pathlib import Path
import re

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "vendor/lichess-chess-openings-3ba6b20"
CSV_PATH = ROOT / "seed/eco/2026_11_07/eco_codes.csv"
SQL_PATH = ROOT / "db/schema/seed_data/chess_eco_2026_11_07.sql"
CODES = {f"{letter}{number:02d}" for letter in "ABCDE" for number in range(100)}


def load_reference(source: Path = SOURCE) -> dict[str, str]:
    """Validate pinned bytes and aggregate distinct English names by ECO code.

    Args:
        source: Directory containing the pinned source and provenance manifest.

    Returns:
        Sorted mapping of all 500 codes to newline-separated opening names.

    Raises:
        ValueError: Source hashes, rows or code coverage are invalid.
    """
    manifest = json.loads((source / "PROVENANCE.json").read_text(encoding="utf-8"))
    for name, metadata in manifest["files"].items():
        if (
            hashlib.sha256((source / name).read_bytes()).hexdigest()
            != metadata["sha256"]
        ):
            raise ValueError(f"Source hash mismatch: {name}")
    names: dict[str, set[str]] = {}
    seen: set[tuple[str, str, str]] = set()
    for letter in "abcde":
        path = source / f"{letter}.tsv"
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream, delimiter="\t", strict=True)
            if reader.fieldnames != ["eco", "name", "pgn"]:
                raise ValueError(f"Unexpected TSV header: {path.name}")
            for row in reader:
                if None in row or any(
                    not row.get(key, "") for key in ("eco", "name", "pgn")
                ):
                    raise ValueError(
                        f"Empty or malformed TSV row: {path.name}:{reader.line_num}"
                    )
                code, name, pgn = row["eco"], row["name"], row["pgn"]
                if (
                    not re.fullmatch(r"[A-E][0-9]{2}", code)
                    or code[0].lower() != letter
                ):
                    raise ValueError(f"Invalid ECO code: {code}")
                if any(char in name for char in "\r\n\x00") or name != name.strip():
                    raise ValueError(f"Invalid opening name: {code}")
                identity = (code, name, pgn)
                if identity in seen:
                    raise ValueError(f"Duplicate source row: {code} {name}")
                seen.add(identity)
                names.setdefault(code, set()).add(name)
    if set(names) != CODES:
        raise ValueError("Source must cover every ECO code A00 to E99")
    return {code: "\n".join(sorted(names[code])) for code in sorted(names)}


def render_csv(reference: dict[str, str]) -> str:
    """Return reviewable UTF-8 CSV with one row per code."""
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("eco_code", "description"))
    writer.writerows(reference.items())
    return stream.getvalue()


def render_sql(reference: dict[str, str]) -> str:
    """Return a once-only atomic seed preserving every existing description."""
    lines = [
        "--liquibase formatted sql",
        "-- Author: Clive Bostock",
        "-- Date: 07-Nov-2026",
        "-- Description: Generated pinned ECO reference; do not edit a released batch.",
        "-- Purpose: Insert missing codes and preserve existing descriptions.",
        "-- Usage: Managed plugin deployment; regenerate with tools/generate_eco_reference.py.",
        "-- Source: lichess-org/chess-openings 3ba6b20d31b2e6125cb0e6a2e792f400717d9d39; CC0-1.0.",
        "-- Description policy: sorted distinct English source names, newline-separated.",
        "",
        "--changeset clive:orac_chess_eco_seed_2026_11_07 context:plugin,prod labels:plugin stripComments:false endDelimiter:/",
        "--preconditions onFail:HALT onError:HALT",
        "--precondition-sql-check expectedResult:1 select count(*) from all_tables where owner='ORAC_CHESS' and table_name='CHESS_ECO_CODE'",
        "declare",
        "  l_description clob;",
        "begin",
        "  savepoint chess_eco_reference;",
    ]
    for code, description in reference.items():
        lines.append("  l_description := empty_clob();")
        # Decode each complete Unicode segment independently; hex stays ASCII in SQLcl.
        for offset in range(0, len(description), 500):
            chunk = description[offset : offset + 500].encode("utf-8").hex().upper()
            lines.append(
                "  l_description := l_description || to_clob(utl_i18n.raw_to_char("
                f"hextoraw('{chunk}'), 'AL32UTF8'));"
            )
        lines.extend(
            [
                "  insert into orac_chess.chess_eco_code (eco_code, description)",
                f"  select '{code}', l_description from dual",
                f"  where not exists (select 1 from orac_chess.chess_eco_code where eco_code = '{code}');",
            ]
        )
    lines.extend(
        [
            "exception",
            "  when others then",
            "    rollback to chess_eco_reference;",
            "    raise;",
            "end;",
            "/",
            "-- Installer transaction owns commit; failure rolls back all seed inserts.",
            "-- Rollback retains reference rows: deleting them could discard subsequent user edits.",
            "-- Structural rollback drops the new table after dependent surfaces are removed.",
            "--rollback empty",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    """Generate artifacts or check them without modifying any file."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Verify packaged outputs without writing"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        reference = load_reference()
        outputs = {CSV_PATH: render_csv(reference), SQL_PATH: render_sql(reference)}
        for path, content in outputs.items():
            if args.check:
                if not path.exists() or path.read_bytes() != content.encode("utf-8"):
                    raise ValueError(f"Generated output differs: {path}")
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content.encode("utf-8"))
    except (OSError, ValueError, csv.Error, KeyError) as exc:
        logger.error("ECO reference generation failed: %s", exc)
        return 1
    logger.info("Verified %d ECO codes", len(reference))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
