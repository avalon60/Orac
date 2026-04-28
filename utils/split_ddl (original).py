#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
__author__: clive bostock
__date__: 2025-10-19
__description__: Fast, streaming splitter for Oracle DDL into one-object-per-file.
Handles: CREATE TABLE, CREATE VIEW, CREATE [UNIQUE] INDEX, and
standalone ALTER TABLE ... ADD CONSTRAINT (pk/uk/fk/check).

Usage
=====
# Tables
python3 utils/split_ddl.py resources/db/schema/table/tables.sql

# Views
python3 utils/split_ddl.py --views-only resources/db/schema/view/views.sql

# Indexes
python3 utils/split_ddl.py --indexes-only resources/db/schema/index/indexes.sql

# Constraints (standalone ALTER ... ADD CONSTRAINT)
python3 utils/split_ddl.py --constraints-only resources/db/schema/constraints.sql

# Mixed monolith (all kinds, in one pass)
python3 utils/split_ddl.py resources/db/schema/model_dump.sql

# Specify a different output root
python3 utils/split_ddl.py --sql-root /tmp/schema resources/db/schema/model_dump.sql
"""

from __future__ import annotations

import argparse
import datetime
import pathlib
import re
import sys
from typing import Callable, Iterable, Iterator, List, Tuple


# ---------- Configuration ----------

SQL_ROOT_DEFAULT = "resources/db/schema"  # singular to match your tree

HEADER = f"""-- __author__: clive bostock
-- __date__: {datetime.date.today().isoformat()}
-- __description__: generated/synchronised by Cline; one object per file
"""

DIR_MAP = {
  "table": "table",
  "view": "view",
  "index": "index",
  # constraints are routed by type → dedicated folders below
}
CONSTRAINT_DIR_MAP = {
  "primary key": "constraint_pk",
  "unique": "constraint_uc",
  "foreign key": "constraint_fk",
  "check": "constraint_other",
}


# ---------- Start regexes (allowing leading comments) ----------

RX_TABLE_START = re.compile(
  r'(?is)(?:--.*?$|/\*.*?\*/\s*)*create\s+table\s+(?:"?(\w+)"?\.)?"?(\w+)"?\s*\(',
  re.MULTILINE
)

RX_VIEW_START = re.compile(
  r'(?is)(?:--.*?$|/\*.*?\*/\s*)*create\s+(?:or\s+replace\s+)?(?:force\s+)?view\s+(?:"?(\w+)"?\.)?"?(\w+)"?\s+as\b',
  re.MULTILINE
)

RX_INDEX_START = re.compile(
  r'(?is)(?:--.*?$|/\*.*?\*/\s*)*create\s+(?:unique\s+)?index\s+(?:"?(\w+)"?\.)?"?(\w+)"?\s+on\s+(?:"?\w+"?\.)?"?\w+"?\b',
  re.MULTILINE
)

# Standalone: alter table <owner?.>table add constraint <name> (primary key|unique|foreign key|check) ...
RX_ALTER_ADD_CONSTRAINT = re.compile(
  r'''(?is)
      (?:--.*?$|/\*.*?\*/\s*)*
      alter\s+table\s+(?:"?(\w+)"?\.)?"?(\w+)"?\s+        # owner?, table
      add\s+constraint\s+"?(\w+)"?\s+                     # constraint name
      (primary\s+key|unique|foreign\s+key|check)\b        # head/type
  ''',
  re.MULTILINE | re.VERBOSE
)


# ---------- Utilities ----------

def write_text(path: pathlib.Path, text: str) -> None:
  """Write `text` to `path`, creating parents; backup existing to *.bak."""
  path.parent.mkdir(parents=True, exist_ok=True)
  if path.exists():
    bak = path.with_suffix(path.suffix + ".bak")
    bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
  if not text.endswith("\n"):
    text += "\n"
  path.write_text(text, encoding="utf-8")


def normalise_sql(sql: str) -> str:
  """Conservative normalisation: lowercase common keywords; tabs→2 spaces; trim line ends."""
  lowers = [
    "CREATE","OR","REPLACE","FORCE","TABLE","VIEW","INDEX","ON","AS",
    "ALTER","ADD","CONSTRAINT","PRIMARY","KEY","UNIQUE","FOREIGN","REFERENCES","CHECK",
    "NUMBER","VARCHAR2","CHAR","DATE","TIMESTAMP","DEFAULT","NOT","NULL",
    "GENERATED","BY","DEFAULT","ALWAYS","IDENTITY","ENABLE","DISABLE","USING","LOCAL","GLOBAL"
  ]
  for kw in lowers:
    sql = re.sub(rf'\b{kw}\b', kw.lower(), sql)
  sql = sql.replace("\t", "  ")
  sql = "\n".join(line.rstrip() for line in sql.splitlines())
  return sql


def _scan_to_terminating_semicolon(sql: str, start_index: int) -> int:
  """Scan forward to first ';' at paren-depth 0, skipping comments/strings; return end index (exclusive)."""
  depth = 0
  i = start_index
  n = len(sql)
  while i < n:
    ch = sql[i]

    # strings: '...'
    if ch == "'":
      i += 1
      while i < n:
        if sql[i] == "'":
          i += 1
          break
        i += 1
      continue

    # /* ... */
    if sql.startswith("/*", i):
      j = sql.find("*/", i + 2)
      return n if j == -1 else j + 2

    # -- ... EOL
    if sql.startswith("--", i):
      j = sql.find("\n", i + 2)
      i = n if j == -1 else j + 1
      continue

    if ch == "(":
      depth += 1
      i += 1
      continue
    if ch == ")":
      depth = max(0, depth - 1)
      i += 1
      continue
    if ch == ";" and depth == 0:
      return i + 1

    i += 1
  return n


def _extract_by_regex(
  sql: str,
  start_rx: re.Pattern,
  name_group_index: int,
  debug: bool = False
) -> Iterator[Tuple[str, str, int, int]]:
  """Generic extractor: yields (object_name, statement_text, start, end) for each match."""
  for m in start_rx.finditer(sql):
    name = (m.group(name_group_index) or "").lower()
    end = _scan_to_terminating_semicolon(sql, m.end())
    stmt = sql[m.start():end]
    if debug:
      print(f"[split_ddl] found '{name}' at {m.start()}–{end}", file=sys.stderr)
    yield name, stmt, m.start(), end


def extract_tables(sql: str, debug: bool = False) -> Iterator[Tuple[str, str]]:
  for name, stmt, _, _ in _extract_by_regex(sql, RX_TABLE_START, 2, debug=debug):
    if name:
      yield name, stmt


def extract_views(sql: str, debug: bool = False) -> Iterator[Tuple[str, str]]:
  for name, stmt, _, _ in _extract_by_regex(sql, RX_VIEW_START, 2, debug=debug):
    if name:
      yield name, stmt


def extract_indexes(sql: str, debug: bool = False) -> Iterator[Tuple[str, str]]:
  for name, stmt, _, _ in _extract_by_regex(sql, RX_INDEX_START, 2, debug=debug):
    if name:
      yield name, stmt


def extract_alter_add_constraints(sql: str, debug: bool = False):
  """
  Yields (table_name, constraint_name, constraint_type, statement_text)
  for standalone ALTER TABLE ... ADD CONSTRAINT statements.
  """
  for m in RX_ALTER_ADD_CONSTRAINT.finditer(sql):
    table_name = (m.group(2) or "").lower()
    cons_name  = (m.group(3) or "").lower()
    cons_type  = " ".join((m.group(4) or "").lower().split())  # normalise spaces
    end = _scan_to_terminating_semicolon(sql, m.end())
    stmt = sql[m.start():end]
    if debug:
      print(f"[split_ddl] alter add constraint '{cons_name}' on {table_name} ({cons_type})", file=sys.stderr)
    yield table_name, cons_name, cons_type, stmt


def split_kind(
  kind: str,
  src_path: pathlib.Path,
  out_root: pathlib.Path,
  extractor: Callable[[str, bool], Iterable[Tuple[str, str]]],
  debug: bool = False,
  max_items: int | None = None
) -> List[pathlib.Path]:
  """Split a specific object kind using `extractor`, write files, return paths."""
  text = src_path.read_text(encoding="utf-8", errors="ignore")
  out_dir = out_root / DIR_MAP[kind]
  total = 0
  written: List[pathlib.Path] = []
  for name, stmt in extractor(text, debug=debug):
    if not name:
      continue
    out = out_dir / f"{name}.sql"
    body = HEADER + "\n" + normalise_sql(stmt.strip())
    write_text(out, body)
    written.append(out)
    total += 1
    if debug and total % 25 == 0:
      print(f"[split_ddl] wrote {total} {kind}s…", file=sys.stderr)
    if max_items and total >= max_items:
      break
  return written


def split_constraints_only(
  src_path: pathlib.Path,
  out_root: pathlib.Path,
  debug: bool = False,
  max_items: int | None = None
) -> List[pathlib.Path]:
  """Split standalone ALTER TABLE ... ADD CONSTRAINT statements into type-specific folders."""
  text = src_path.read_text(encoding="utf-8", errors="ignore")
  total = 0
  written: List[pathlib.Path] = []
  for table_name, cons_name, cons_type, stmt in extract_alter_add_constraints(text, debug=debug):
    subdir = CONSTRAINT_DIR_MAP.get(cons_type, "constraint_other")
    out = out_root / subdir / f"{cons_name}.sql"
    body = HEADER + "\n" + normalise_sql(stmt.strip())
    write_text(out, body)
    written.append(out)
    total += 1
    if debug and total % 25 == 0:
      print(f"[split_ddl] wrote {total} constraints…", file=sys.stderr)
    if max_items and total >= max_items:
      break
  return written


def run() -> int:
  ap = argparse.ArgumentParser(
    description="Split Oracle DDL into one-object-per-file (tables, views, indexes, constraints).",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
  )
  ap.add_argument("input", help="Path to monolithic DDL file (or '-' for stdin)")
  mode = ap.add_mutually_exclusive_group()
  mode.add_argument("--tables-only", action="store_true", help="Process only CREATE TABLE statements")
  mode.add_argument("--views-only", action="store_true", help="Process only CREATE VIEW statements")
  mode.add_argument("--indexes-only", action="store_true", help="Process only CREATE [UNIQUE] INDEX statements")
  mode.add_argument("--constraints-only", action="store_true", help="Process only ALTER TABLE ... ADD CONSTRAINT")
  ap.add_argument("--sql-root", default=SQL_ROOT_DEFAULT, help="Output root directory")
  ap.add_argument("--max", type=int, default=0, help="Limit number of objects to write (for testing)")
  ap.add_argument("--debug", action="store_true", help="Verbose progress to stderr")
  args = ap.parse_args()

  # acquire source
  if args.input == "-":
    tmp = pathlib.Path("/tmp/split_ddl_buffer.sql")
    tmp.write_text(sys.stdin.read(), encoding="utf-8")
    src = tmp
  else:
    src = pathlib.Path(args.input)
    if not src.exists():
      print(f"ERROR: {src} not found.", file=sys.stderr)
      return 2

  out_root = pathlib.Path(args.sql_root)
  if args.debug:
    print(f"[split_ddl] source: {src.resolve()}", file=sys.stderr)
    print(f"[split_ddl] output root: {out_root.resolve()}", file=sys.stderr)

  written: List[pathlib.Path] = []

  # select mode
  if args.tables_only:
    written += split_kind("table", src, out_root, extract_tables, debug=args.debug, max_items=(args.max or None))
  elif args.views_only:
    written += split_kind("view", src, out_root, extract_views, debug=args.debug, max_items=(args.max or None))
  elif args.indexes_only:
    written += split_kind("index", src, out_root, extract_indexes, debug=args.debug, max_items=(args.max or None))
  elif args.constraints_only:
    written += split_constraints_only(src, out_root, debug=args.debug, max_items=(args.max or None))
  else:
    # default: do all, in a sensible order
    written += split_kind("table", src, out_root, extract_tables,  debug=args.debug, max_items=(args.max or None))
    written += split_kind("view",  src, out_root, extract_views,   debug=args.debug, max_items=(args.max or None))
    written += split_kind("index", src, out_root, extract_indexes, debug=args.debug, max_items=(args.max or None))
    written += split_constraints_only(src, out_root, debug=args.debug, max_items=(args.max or None))

  print("Wrote:")
  for p in written:
    print(f" - {p}")

  return 0


if __name__ == "__main__":
  raise SystemExit(run())

