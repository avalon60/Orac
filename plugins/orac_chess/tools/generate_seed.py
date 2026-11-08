"""Validate immutable Chess CSV batches and generate packaged Liquibase SQL."""

# Author: Clive Bostock
# Date: 07-Nov-2026
# Description: Generate deterministic API-only catalogue bootstrap batches.
# Purpose: Package validated CSV data without install-time filesystem or network dependencies.
# Usage: python3 plugins/orac_chess/tools/generate_seed.py --check

from __future__ import annotations

import argparse
import csv
import logging
from datetime import date
import json
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, urlsplit

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
VIDEO_REQUIRED = (
    "Platform",
    "Creator",
    "Title",
    "Video URL",
    "Published On",
    "Description",
)
VIDEO_OPTIONAL = (
    "External Video Id",
    "Duration Seconds",
    "Opening Names",
    "Gambit Names",
)
OPENING_COLUMNS = (
    "name",
    "opening_type",
    "description",
    "parent_opening_name",
    "eco_codes",
    "aliases",
    "mainline_name",
    "mainline_pgn",
    "starting_fen",
    "mainline_annotation",
)
GAMBIT_COLUMNS = (
    "name",
    "description",
    "opening_names",
    "mainline_name",
    "mainline_pgn",
    "starting_fen",
    "mainline_annotation",
)


def _validate_quoting(text: str, path: Path) -> None:
    """Reject quote characters outside the standard CSV escaped-field grammar."""
    state = "start"
    line = 1
    for char in text:
        if state == "quoted":
            if char == '"':
                state = "closed"
        elif state == "closed":
            if char == '"':
                state = "quoted"
            elif char == ",":
                state = "start"
            elif char in "\r\n":
                state = "start"
            else:
                raise ValueError(
                    f"{path.name}: row {line}, column record: characters after closing quote"
                )
        elif char == '"':
            if state != "start":
                raise ValueError(
                    f"{path.name}: row {line}, column record: quote inside unquoted field"
                )
            state = "quoted"
        elif char == "," or char in "\r\n":
            state = "start"
        else:
            state = "unquoted"
        if char == "\n":
            line += 1
    if state == "quoted":
        raise ValueError(
            f"{path.name}: row {line}, column record: unterminated quoted field"
        )


def read_csv(
    path: Path, required: tuple[str, ...], optional: tuple[str, ...] = ()
) -> list[dict[str, object]]:
    """Read strict UTF-8 CSV and retain physical record locations.

    Args:
        path: Input CSV file, optionally containing a UTF-8 BOM.
        required: Required header names.
        optional: Additional supported header names.

    Returns:
        Records with context for validation and database errors.

    Raises:
        ValueError: If a header or CSV record is malformed.
    """
    rows = []
    reader = None
    previous_limit = csv.field_size_limit(sys.maxsize)
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            _validate_quoting(stream.read(), path)
            stream.seek(0)
            reader = csv.reader(stream, strict=True)
            header = next(reader, [])
            if (
                len(header) != len(set(header))
                or not set(required) <= set(header)
                or set(header) - set(required + optional)
            ):
                raise ValueError(
                    f"{path.name}: row 1, column header: expected {required}, optional {optional}; got {header}"
                )
            for cells in reader:
                if len(cells) != len(header):
                    raise ValueError(
                        f"{path.name}: row {reader.line_num}, column record: expected {len(header)} cells, got {len(cells)}"
                    )
                rows.append(
                    dict(zip(header, cells))
                    | {"context": f"{path.name}: row {reader.line_num}"}
                )
    except (csv.Error, UnicodeError) as exc:
        raise ValueError(
            f"{path.name}: row {reader.line_num if reader else 1}, column record: {exc}"
        ) from exc
    finally:
        csv.field_size_limit(previous_limit)
    for row in rows:
        for column, value in row.items():
            if isinstance(value, str) and "\x00" in value:
                fail(row, column, "NUL is not supported")
    return rows


def fail(row: dict[str, object], column: str, message: str) -> None:
    """Raise a validation error with a file, row and column location."""
    raise ValueError(f'{row["context"]}, column {column}: {message}')


def field(
    row: dict[str, object],
    column: str,
    limit: int | None = None,
    required: bool = False,
) -> str:
    """Trim an identity or scalar cell and enforce its storage contract."""
    value = str(row.get(column, "")).strip()
    if required and not value:
        fail(row, column, "value is required")
    if limit is not None and len(value) > limit:
        fail(row, column, f"exceeds {limit} characters")
    if "\x00" in value:
        fail(row, column, "NUL is not supported")
    return value


def names(row: dict[str, object], column: str, limit: int = 200) -> list[str]:
    """Parse exact canonical names separated by the reserved pipe delimiter."""
    value = field(row, column)
    if not value:
        return []
    result = [part.strip() for part in value.split("|")]
    if any(not part or len(part) > limit for part in result) or len(result) != len(
        set(result)
    ):
        fail(
            row,
            column,
            f"expected distinct nonempty names of at most {limit} characters separated by |",
        )
    return result


def video_identity(row: dict[str, object]) -> tuple[str, str]:
    """Validate an HTTP(S) URL and derive or check its external video identity."""
    platform = field(row, "Platform", 50, True)
    url = field(row, "Video URL", 2048, True)
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or any(c.isspace() for c in url)
        ):
            raise ValueError(
                "expected an absolute HTTP(S) URL without credentials or whitespace"
            )
        parsed.port
    except ValueError as exc:
        fail(row, "Video URL", str(exc))
    external = field(row, "External Video Id", 255)
    if platform.casefold() == "youtube":
        platform = "YouTube"
        host = parsed.hostname.lower()
        query = parse_qs(parsed.query, keep_blank_values=True)
        if len(query.get("v", [])) > 1:
            fail(row, "Video URL", "duplicate v parameters")
        if (
            host in ("youtube.com", "www.youtube.com", "m.youtube.com")
            and parsed.path == "/watch"
        ):
            derived = query.get("v", [""])[0]
        elif host in (
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
        ) and re.fullmatch(r"/(shorts|embed)/[^/]+/?", parsed.path):
            derived = parsed.path.strip("/").split("/")[1]
        elif host in ("youtu.be", "www.youtu.be") and re.fullmatch(
            r"/[^/]+/?", parsed.path
        ):
            derived = parsed.path.strip("/")
        else:
            fail(row, "Video URL", "unsupported YouTube URL")
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", derived):
            fail(row, "Video URL", "YouTube ID must contain 11 URL-safe characters")
        if external and external != derived:
            fail(row, "External Video Id", "conflicts with URL identity")
        external = derived
    elif not external:
        fail(row, "External Video Id", "required for non-YouTube platforms")
    return platform, external


def catalogue(rows: list[dict[str, object]], opening: bool) -> list[dict[str, object]]:
    """Validate catalogue identities, list columns and optional root mainlines."""
    result = []
    seen = set()
    for row in rows:
        name = field(row, "name", 200, True)
        if "|" in name or name in seen:
            fail(row, "name", "duplicate identity or reserved | delimiter")
        seen.add(name)
        item = dict(row) | {"name": name}
        for column, limit in [("mainline_name", 200), ("starting_fen", 200)]:
            item[column] = field(row, column, limit)
        if len(str(row.get("mainline_pgn", ""))) > 4194304:
            fail(row, "mainline_pgn", "exceeds 4194304 characters")
        if row.get("mainline_pgn"):
            if not item["mainline_name"]:
                fail(row, "mainline_name", "required when mainline_pgn is supplied")
        elif any(
            item.get(column)
            for column in ("mainline_name", "starting_fen", "mainline_annotation")
        ):
            fail(
                row, "mainline_pgn", "required when other mainline fields are supplied"
            )
        for column in (("mainline_eco_codes",) if opening else ("eco_codes", "mainline_eco_codes")):
            if column in row:
                item[column] = names(row, column, 3)
                if any(not re.fullmatch("[A-E][0-9]{2}", code) for code in item[column]):
                    fail(row, column, "expected A00 through E99")
                if column == "mainline_eco_codes" and item[column] and not row.get("mainline_pgn"):
                    fail(row, column, "requires mainline_pgn")
        if opening:
            item["opening_type"] = field(row, "opening_type") or "OPENING"
            if item["opening_type"] not in ("OPENING", "SYSTEM"):
                fail(row, "opening_type", "expected OPENING or SYSTEM")
            item["parent_opening_name"] = field(row, "parent_opening_name", 200)
            item["eco_codes"] = names(row, "eco_codes", 3)
            if any(
                not re.fullmatch("[A-E][0-9]{2}", code) for code in item["eco_codes"]
            ):
                fail(row, "eco_codes", "expected A00 through E99")
            item["aliases"] = names(row, "aliases")
        else:
            item["opening_names"] = names(row, "opening_names")
        result.append(item)
    if opening:
        parents = {item["name"]: item["parent_opening_name"] for item in result}
        for item in result:
            chain = set()
            cursor = item["name"]
            while cursor in parents and cursor:
                if cursor in chain:
                    fail(
                        item, "parent_opening_name", "cycle in batch opening hierarchy"
                    )
                chain.add(cursor)
                cursor = parents[cursor]
    return result


def load_batch(batch: Path) -> dict[str, object]:
    """Validate a complete batch, leaving existing database name resolution to APIs."""
    openings = catalogue(read_csv(batch / "openings.csv", OPENING_COLUMNS, ("mainline_eco_codes",)), True)
    gambits = catalogue(read_csv(batch / "gambits.csv", GAMBIT_COLUMNS, ("eco_codes", "mainline_eco_codes")), False)
    videos = []
    seen = set()
    for row in read_csv(batch / "videos.csv", VIDEO_REQUIRED, VIDEO_OPTIONAL):
        platform, external = video_identity(row)
        if (platform, external) in seen:
            fail(row, "External Video Id", "duplicate platform/video identity")
        seen.add((platform, external))
        published = field(row, "Published On")
        if published:
            try:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", published):
                    raise ValueError("expected YYYY-MM-DD")
                date.fromisoformat(published)
            except ValueError as exc:
                fail(row, "Published On", str(exc))
        duration = field(row, "Duration Seconds")
        if duration and (
            not re.fullmatch("[0-9]+", duration) or not 1 <= int(duration) <= 9999999999
        ):
            fail(row, "Duration Seconds", "expected integer 1 through 9999999999")
        videos.append(
            {
                "context": row["context"],
                "platform": platform,
                "external_video_id": external,
                "title": field(row, "Title", 500, True),
                "video_url": field(row, "Video URL"),
                "creator": field(row, "Creator", 300),
                "description": row.get("Description", ""),
                "published_on": published,
                "duration_seconds": int(duration) if duration else None,
                "opening_names": names(row, "Opening Names"),
                "gambit_names": names(row, "Gambit Names"),
            }
        )
    return {"openings": openings, "gambits": gambits, "videos": videos}


def is_eco_aware(batch: Path) -> bool:
    """Return whether a batch uses fields requiring the later ECO API."""
    def headers(path: Path) -> set[str]:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            return set(next(csv.reader(stream), []))

    return bool(
        headers(batch / "gambits.csv") & {"eco_codes", "mainline_eco_codes"}
        or "mainline_eco_codes" in headers(batch / "openings.csv")
    )


def generate(batch: Path) -> str:
    """Render a once-only Liquibase changeset with an inert UTF-8 hex payload."""
    if not re.fullmatch("[a-z0-9_]+", batch.name):
        raise ValueError(
            "batch directory must contain only lowercase ASCII letters, digits and underscores"
        )
    data = json.dumps(load_batch(batch), ensure_ascii=False, separators=(",", ":"))
    eco_aware = is_eco_aware(batch)
    assignments = "".join(
        f"  l_payload := l_payload || to_clob(utl_i18n.raw_to_char(hextoraw('{data[i:i+400].encode('utf-8').hex()}'), 'AL32UTF8'));\n"
        for i in range(0, len(data), 400)
    )
    template_name = "seed_runtime_eco.sql" if eco_aware else "seed_runtime.sql"
    template = (ROOT / "tools" / template_name).read_text(encoding="utf-8")
    return template.replace("@BATCH@", batch.name).replace(
        "-- @PAYLOAD@", assignments.rstrip()
    )


def main() -> int:
    """Generate all immutable packaged batches or check that artefacts are current."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--batch",
        type=Path,
        help="Generate one batch directory instead of all packaged batches",
    )
    parser.add_argument("--output", type=Path, help="Output for a single --batch")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when generated SQL differs; write nothing",
    )
    args = parser.parse_args()
    if args.output and not args.batch:
        parser.error("--output requires --batch")
    try:
        for batch in (
            [args.batch] if args.batch else sorted((ROOT / "seed/batches").iterdir())
        ):
            output = (
                args.output
                or ROOT / f"db/schema/seed_data/chess_batch_{batch.name}.sql"
            )
            content = generate(batch)
            if args.check:
                if not output.exists() or output.read_text(encoding="utf-8") != content:
                    raise ValueError(f"{output}: generated SQL is stale")
            else:
                output.write_text(content, encoding="utf-8")
            if is_eco_aware(batch) and args.output is None:
                controller = ROOT / "db/liquibase/controllers/15_eco_seed_batches.xml"
                include = f'  <include file="../../schema/seed_data/{output.name}" relativeToChangelogFile="true"/>'
                controller_text = controller.read_text(encoding="utf-8")
                if include not in controller_text:
                    if args.check:
                        raise ValueError(f"{controller}: missing ECO-aware batch include")
                    controller.write_text(
                        controller_text.replace("</databaseChangeLog>", include + "\n</databaseChangeLog>"),
                        encoding="utf-8",
                    )
            logger.info("%s %s", "Checked" if args.check else "Generated", output)
    except (ValueError, OSError) as exc:
        logger.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    raise SystemExit(main())
