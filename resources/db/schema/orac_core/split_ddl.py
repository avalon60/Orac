#!/usr/bin/env python3
# __author__: Clive Bostock
# __date__: 2026-03-22
# __description__: Split Oracle DDL into per-object files, including comments, with optional Liquibase headers.

from __future__ import annotations

import argparse
import datetime
import getpass
import pathlib
import re
from typing import Callable, Iterator


SQL_ROOT_DEFAULT = "db_schema"

HEADER_TEMPLATE = """-- __author__: {author}
-- __date__: {date}
-- __description__: generated/synchronised by split_ddl; one object per file
"""

LIQUIBASE_HEADER_TEMPLATE = """-- liquibase formatted sql

--changeset {author}:{changeset_id}{changeset_attrs}
"""

DIR_MAP = {
  "table": "table",
  "view": "view",
  "index": "index",
  "comment": "comment",
}

CONSTRAINT_DIR_MAP = {
  "primary key": "constraint_pk",
  "unique": "constraint_uc",
  "foreign key": "constraint_fk",
  "check": "constraint_other",
}

RX_TABLE_START = re.compile(
  r'(?is)(?:--.*?$|/\*.*?\*/\s*)*create\s+table\s+(?:"?(\w+)"?\.)?"?(\w+)"?\s*\(',
  re.MULTILINE,
)

RX_VIEW_START = re.compile(
  r'(?is)(?:--.*?$|/\*.*?\*/\s*)*create\s+(?:or\s+replace\s+)?(?:force\s+)?view\s+(?:"?(\w+)"?\.)?"?(\w+)"?\s+as\b',
  re.MULTILINE,
)

RX_INDEX_START = re.compile(
  r'(?is)(?:--.*?$|/\*.*?\*/\s*)*create\s+(?:unique\s+)?index\s+(?:"?(\w+)"?\.)?"?(\w+)"?\s+on\s+(?:"?\w+"?\.)?"?\w+"?\b',
  re.MULTILINE,
)

RX_ALTER_ADD_CONSTRAINT = re.compile(
  r'''(?is)
      (?:--.*?$|/\*.*?\*/\s*)*
      alter\s+table\s+(?:"?(\w+)"?\.)?"?(\w+)"?\s+
      add\s+constraint\s+"?(\w+)"?\s+
      (primary\s+key|unique|foreign\s+key|check)\b
  ''',
  re.MULTILINE | re.VERBOSE,
)

RX_COMMENT_START = re.compile(r'(?im)^\s*comment\s+on\s+(?:table|column)\b')
RX_COMMENT_ON_TABLE = re.compile(
  r'''(?is)^\s*comment\s+on\s+table\s+(?:"?(\w+)"?\.)?"?(\w+)"?\s+is\s+' ''',
  re.VERBOSE,
)
RX_COMMENT_ON_COLUMN = re.compile(
  r'''(?is)^\s*comment\s+on\s+column\s+(?:"?(\w+)"?\.)?"?(\w+)"?\."?(\w+)"?\s+is\s+' ''',
  re.VERBOSE,
)


def write_text(path: pathlib.Path, text: str) -> None:
  """Write text to disk, creating a .bak file when overwriting.

  Args:
    path: Target file path.
    text: File content.
  """
  path.parent.mkdir(parents=True, exist_ok=True)

  if path.exists():
    bak = path.with_suffix(path.suffix + ".bak")
    bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

  if not text.endswith("\n"):
    text += "\n"

  path.write_text(text, encoding="utf-8")


def normalise_sql(sql: str) -> str:
  """Normalise emitted SQL keyword case and trailing whitespace.

  Args:
    sql: Input SQL.

  Returns:
    Normalised SQL.
  """
  lowers = [
    "CREATE", "OR", "REPLACE", "FORCE", "TABLE", "VIEW", "INDEX", "ON", "AS",
    "ALTER", "ADD", "CONSTRAINT", "PRIMARY", "KEY", "UNIQUE", "FOREIGN", "REFERENCES",
    "CHECK", "COMMENT", "COLUMN", "IS",
  ]

  for kw in lowers:
    sql = re.sub(rf'\b{kw}\b', kw.lower(), sql)

  sql = sql.replace("\t", "  ")
  sql = "\n".join(line.rstrip() for line in sql.splitlines())
  return sql


def scan_to_semicolon(sql: str, start_index: int) -> int:
  """Scan forward to the terminating semicolon for a SQL statement.

  Single-quoted strings and parenthesis depth are respected.

  Args:
    sql: Source SQL text.
    start_index: Start index.

  Returns:
    Index immediately after the terminating semicolon, or end of text.
  """
  depth = 0
  i = start_index
  n = len(sql)

  while i < n:
    ch = sql[i]

    if ch == "'":
      i += 1
      while i < n:
        if sql[i] == "'":
          if i + 1 < n and sql[i + 1] == "'":
            i += 2
            continue
          i += 1
          break
        i += 1
      continue

    if ch == "(":
      depth += 1
    elif ch == ")":
      depth = max(0, depth - 1)
    elif ch == ";" and depth == 0:
      return i + 1

    i += 1

  return n


def extract_by_regex(
  sql: str,
  rx: re.Pattern[str],
  name_group: int,
  schema_group: int = 1,
) -> Iterator[tuple[str, str, str, str]]:
  """Extract statements identified by a start regex.

  Args:
    sql: Source SQL text.
    rx: Start regex.
    name_group: Object name group index.
    schema_group: Schema name group index.

  Yields:
    Tuples of schema, lowercase name, uppercase name, and statement text.
  """
  for match in rx.finditer(sql):
    name = (match.group(name_group) or "").lower()
    schema = (match.group(schema_group) or "").upper()
    name_upper = (match.group(name_group) or "").upper()
    end = scan_to_semicolon(sql, match.end())
    stmt = sql[match.start():end]

    if name:
      yield schema, name, name_upper, stmt


def extract_constraints(sql: str) -> Iterator[tuple[str, str, str, str, str]]:
  """Extract alter table add constraint statements.

  Args:
    sql: Source SQL text.

  Yields:
    Tuples of schema, lowercase name, uppercase name, type, and statement text.
  """
  for match in RX_ALTER_ADD_CONSTRAINT.finditer(sql):
    cons_name = (match.group(3) or "").lower()
    cons_type = " ".join((match.group(4) or "").lower().split())
    cons_schema = (match.group(1) or "").upper()
    cons_name_upper = (match.group(3) or "").upper()
    end = scan_to_semicolon(sql, match.end())
    stmt = sql[match.start():end]
    yield cons_schema, cons_name, cons_name_upper, cons_type, stmt


def extract_comments(sql: str) -> Iterator[tuple[str, str, str]]:
  """Extract comment statements sequentially with no overlap.

  Args:
    sql: Source SQL text.

  Yields:
    Tuples of schema, lowercase table stem, and statement text.
  """
  pos = 0
  n = len(sql)

  while pos < n:
    match = RX_COMMENT_START.search(sql, pos)
    if not match:
      break

    start = match.start()
    end = scan_to_semicolon(sql, match.end())
    stmt = sql[start:end]
    stripped = stmt.strip()

    mt = RX_COMMENT_ON_TABLE.match(stripped)
    if mt:
      schema = (mt.group(1) or "").upper()
      table_name = (mt.group(2) or "").lower()
      if table_name:
        yield schema, table_name, stmt
      pos = end
      continue

    mc = RX_COMMENT_ON_COLUMN.match(stripped)
    if mc:
      schema = (mc.group(1) or "").upper()
      table_name = (mc.group(2) or "").lower()
      if table_name:
        yield schema, table_name, stmt
      pos = end
      continue

    pos = match.end()


def build_header(
  author: str,
  liquify: bool,
  headers: bool,
  name: str,
  changeset_attrs: str = "",
  changeset_suffix: str = "create",
) -> str | None:
  """Build an optional header block.

  Args:
    author: Author or Liquibase changeset owner.
    liquify: Whether Liquibase output is enabled.
    headers: Whether metadata header lines are enabled.
    name: Object name.
    changeset_attrs: Extra Liquibase changeset attributes.
    changeset_suffix: Changeset suffix.

  Returns:
    Header text, or None.
  """
  today = datetime.date.today().isoformat()
  parts = []

  if liquify:
    parts.append(
      LIQUIBASE_HEADER_TEMPLATE.format(
        author=author,
        changeset_id=f"{name}_{changeset_suffix}",
        changeset_attrs=changeset_attrs,
      )
    )

  if headers:
    parts.append(HEADER_TEMPLATE.format(author=author, date=today))

  if not parts:
    return None

  return "\n".join(parts)


def build_precondition(kind: str, schema: str, name_upper: str) -> str | None:
  """Build an optional Liquibase precondition.

  Args:
    kind: Object kind.
    schema: Owner schema.
    name_upper: Uppercase object name.

  Returns:
    Precondition block, or None.
  """
  if not schema:
    return None

  if kind == "table":
    return "\n".join([
      "--preconditions onFail:MARK_RAN onError:HALT",
      f"--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = '{schema}' and table_name = '{name_upper}';",
    ])

  if kind == "index":
    return "\n".join([
      "--preconditions onFail:MARK_RAN onError:HALT",
      f"--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = '{schema}' and index_name = '{name_upper}';",
    ])

  if kind == "constraint":
    return "\n".join([
      "--preconditions onFail:MARK_RAN onError:HALT",
      f"--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = '{schema}' and constraint_name = '{name_upper}';",
    ])

  return None


def split_kind(
  kind: str,
  src: pathlib.Path,
  out_root: pathlib.Path,
  extractor: Callable[[str], Iterator[tuple[str, str, str, str]]],
  author: str,
  liquify: bool,
  headers: bool,
) -> list[pathlib.Path]:
  """Split standard one-object statements into one file per object.

  Args:
    kind: Object kind.
    src: Input SQL file.
    out_root: Output root.
    extractor: Extractor function.
    author: Author or Liquibase changeset owner.
    liquify: Whether Liquibase output is enabled.
    headers: Whether metadata headers are enabled.

  Returns:
    Written file paths.
  """
  text = src.read_text(encoding="utf-8", errors="ignore")
  out_dir = out_root / DIR_MAP[kind]
  written: list[pathlib.Path] = []

  for schema, name, name_upper, stmt in extractor(text):
    if not schema:
      print(f"[warn] skipping {kind} '{name_upper}' due to missing schema. DDL snippet: {stmt.strip()[:200]}")
      continue

    changeset_attrs = " stripComments:false"
    precondition = None

    if liquify:
      if kind == "view":
        changeset_attrs += " runOnChange:true"
      else:
        precondition = build_precondition(kind, schema, name_upper)

    header = build_header(author, liquify, headers, name, changeset_attrs, "create")
    sql = normalise_sql(stmt.strip())

    parts = []
    if header:
      parts.append(header)
    if precondition:
      parts.append(precondition)
    parts.append(sql)

    out = out_dir / f"{name}.sql"
    write_text(out, "\n\n".join(parts))
    written.append(out)

  return written


def split_constraints(
  src: pathlib.Path,
  out_root: pathlib.Path,
  author: str,
  liquify: bool,
  headers: bool,
) -> list[pathlib.Path]:
  """Split constraints into one file per constraint.

  Args:
    src: Input SQL file.
    out_root: Output root.
    author: Author or Liquibase changeset owner.
    liquify: Whether Liquibase output is enabled.
    headers: Whether metadata headers are enabled.

  Returns:
    Written file paths.
  """
  text = src.read_text(encoding="utf-8", errors="ignore")
  written: list[pathlib.Path] = []

  for schema, name, name_upper, cons_type, stmt in extract_constraints(text):
    if not schema:
      print(f"[warn] skipping constraint '{name_upper}' due to missing schema. DDL snippet: {stmt.strip()[:200]}")
      continue

    subdir = CONSTRAINT_DIR_MAP.get(cons_type, "constraint_other")
    precondition = build_precondition("constraint", schema, name_upper) if liquify else None
    header = build_header(author, liquify, headers, name, " stripComments:false", "create")
    sql = normalise_sql(stmt.strip())

    parts = []
    if header:
      parts.append(header)
    if precondition:
      parts.append(precondition)
    parts.append(sql)

    out = out_root / subdir / f"{name}.sql"
    write_text(out, "\n\n".join(parts))
    written.append(out)

  return written


def split_comments(
  src: pathlib.Path,
  out_root: pathlib.Path,
  author: str,
  liquify: bool,
  headers: bool,
) -> list[pathlib.Path]:
  """Split comment statements into one file per table stem.

  Args:
    src: Input SQL file.
    out_root: Output root.
    author: Author or Liquibase changeset owner.
    liquify: Whether Liquibase output is enabled.
    headers: Whether metadata headers are enabled.

  Returns:
    Written file paths.
  """
  text = src.read_text(encoding="utf-8", errors="ignore")
  out_dir = out_root / DIR_MAP["comment"]
  grouped: dict[tuple[str, str], list[str]] = {}

  for schema, table_name, stmt in extract_comments(text):
    if not schema:
      print(f"[warn] skipping comment block for table '{table_name.upper()}' due to missing schema. DDL snippet: {stmt.strip()[:200]}")
      continue
    grouped.setdefault((schema, table_name), []).append(normalise_sql(stmt.strip()))

  written: list[pathlib.Path] = []

  for (schema, table_name), statements in sorted(grouped.items()):
    del schema
    header = build_header(
      author,
      liquify,
      headers,
      table_name,
      " stripComments:false runOnChange:true runAlways:false endDelimiter:; rollbackEndDelimiter:;",
      "comment",
    )

    parts = []
    if header:
      parts.append(header)
    parts.append("\n\n".join(statements))

    out = out_dir / f"{table_name}.sql"
    write_text(out, "\n\n".join(parts))
    written.append(out)

  return written


def generate_run_all(out_root: pathlib.Path) -> None:
  """Generate a dependency-ordered run_all.sql script.

  Args:
    out_root: Output root.
  """
  out_root.mkdir(parents=True, exist_ok=True)
  run_script = out_root / "run_all.sql"

  sections = [
    ("tables", "table"),
    ("indexes", "index"),
    ("constraints_pk", "constraint_pk"),
    ("constraints_uc", "constraint_uc"),
    ("constraints_fk", "constraint_fk"),
    ("constraints_other", "constraint_other"),
    ("comments", "comment"),
    ("views", "view"),
  ]

  lines = ["set echo on\n", "spool run_all.log\n"]
  wrote_any = False

  for label, directory in sections:
    dir_path = out_root / directory
    if not dir_path.exists():
      continue

    files = sorted(dir_path.glob("*.sql"))
    if not files:
      continue

    wrote_any = True
    lines.append(f"prompt === {label} ===")
    for file_path in files:
      rel = file_path.relative_to(out_root)
      lines.append(f"@{rel}")
    lines.append("")

  if wrote_any:
    lines.append("spool off\n")
    run_script.write_text("\n".join(lines), encoding="utf-8")


def run() -> None:
  """Parse arguments and execute the split."""
  parser = argparse.ArgumentParser()
  parser.add_argument("input")
  parser.add_argument("--sql-root", default=SQL_ROOT_DEFAULT)
  parser.add_argument("--guid", help="Liquibase author GUID")
  parser.add_argument("-H", "--headers", action="store_true", help="Include author/date metadata header")
  parser.add_argument("-L", "--liquify", action="store_true", help="Emit Liquibase formatted SQL")
  parser.add_argument("--tables-only", action="store_true")
  parser.add_argument("--views-only", action="store_true")
  parser.add_argument("--indexes-only", action="store_true")
  parser.add_argument("--constraints-only", action="store_true")
  parser.add_argument("--comments-only", action="store_true")

  args = parser.parse_args()

  selected_modes = sum([
    args.tables_only,
    args.views_only,
    args.indexes_only,
    args.constraints_only,
    args.comments_only,
  ])

  if selected_modes > 1:
    parser.error(
      "Only one of --tables-only, --views-only, --indexes-only, --constraints-only or --comments-only may be specified."
    )

  author = args.guid if args.guid else getpass.getuser()
  src = pathlib.Path(args.input)
  out_root = pathlib.Path(args.sql_root)

  written: list[pathlib.Path] = []

  if args.tables_only:
    written += split_kind("table", src, out_root, lambda t: extract_by_regex(t, RX_TABLE_START, 2), author, args.liquify, args.headers)
  elif args.views_only:
    written += split_kind("view", src, out_root, lambda t: extract_by_regex(t, RX_VIEW_START, 2), author, args.liquify, args.headers)
  elif args.indexes_only:
    written += split_kind("index", src, out_root, lambda t: extract_by_regex(t, RX_INDEX_START, 2), author, args.liquify, args.headers)
  elif args.constraints_only:
    written += split_constraints(src, out_root, author, args.liquify, args.headers)
  elif args.comments_only:
    written += split_comments(src, out_root, author, args.liquify, args.headers)
  else:
    written += split_kind("table", src, out_root, lambda t: extract_by_regex(t, RX_TABLE_START, 2), author, args.liquify, args.headers)
    written += split_kind("view", src, out_root, lambda t: extract_by_regex(t, RX_VIEW_START, 2), author, args.liquify, args.headers)
    written += split_kind("index", src, out_root, lambda t: extract_by_regex(t, RX_INDEX_START, 2), author, args.liquify, args.headers)
    written += split_constraints(src, out_root, author, args.liquify, args.headers)
    written += split_comments(src, out_root, author, args.liquify, args.headers)

  generate_run_all(out_root)

  print("Wrote:")
  for path in written:
    print(f" - {path}")


if __name__ == "__main__":
  run()
