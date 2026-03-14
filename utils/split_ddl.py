#!/usr/bin/env python3
# __author__: Clive Bostock
# __date__: 2026-03-13
# __description__: Fast streaming Oracle DDL splitter. Optionally emits Liquibase formatted SQL.

from __future__ import annotations

import argparse
import datetime
import pathlib
import re
import getpass


SQL_ROOT_DEFAULT = "db_schema"


HEADER_TEMPLATE = """-- __author__: {author}
-- __date__: {date}
-- __description__: generated/synchronised by split_ddl; one object per file
"""


LIQUIBASE_HEADER_TEMPLATE = """-- liquibase formatted sql

--changeset {author}:{changeset_id}
"""


DIR_MAP = {
  "table": "table",
  "view": "view",
  "index": "index",
}


CONSTRAINT_DIR_MAP = {
  "primary key": "constraint_pk",
  "unique": "constraint_uc",
  "foreign key": "constraint_fk",
  "check": "constraint_other",
}


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

RX_ALTER_ADD_CONSTRAINT = re.compile(
  r'''(?is)
      (?:--.*?$|/\*.*?\*/\s*)*
      alter\s+table\s+(?:"?(\w+)"?\.)?"?(\w+)"?\s+
      add\s+constraint\s+"?(\w+)"?\s+
      (primary\s+key|unique|foreign\s+key|check)\b
  ''',
  re.MULTILINE | re.VERBOSE
)


def write_text(path: pathlib.Path, text: str):

  path.parent.mkdir(parents=True, exist_ok=True)

  if path.exists():
    bak = path.with_suffix(path.suffix + ".bak")
    bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

  if not text.endswith("\n"):
    text += "\n"

  path.write_text(text, encoding="utf-8")


def normalise_sql(sql: str):

  lowers = [
    "CREATE","OR","REPLACE","FORCE","TABLE","VIEW","INDEX","ON","AS",
    "ALTER","ADD","CONSTRAINT","PRIMARY","KEY","UNIQUE","FOREIGN","REFERENCES","CHECK"
  ]

  for kw in lowers:
    sql = re.sub(rf'\b{kw}\b', kw.lower(), sql)

  sql = sql.replace("\t", "  ")
  sql = "\n".join(line.rstrip() for line in sql.splitlines())

  return sql


def scan_to_semicolon(sql, start_index):

  depth = 0
  i = start_index
  n = len(sql)

  while i < n:

    ch = sql[i]

    if ch == "'":
      i += 1
      while i < n:
        if sql[i] == "'":
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


def extract_by_regex(sql, rx, name_group):

  for m in rx.finditer(sql):

    name = (m.group(name_group) or "").lower()

    end = scan_to_semicolon(sql, m.end())

    stmt = sql[m.start():end]

    if name:
      yield name, stmt


def extract_constraints(sql):

  for m in RX_ALTER_ADD_CONSTRAINT.finditer(sql):

    cons_name = (m.group(3) or "").lower()
    cons_type = " ".join((m.group(4) or "").lower().split())

    end = scan_to_semicolon(sql, m.end())

    stmt = sql[m.start():end]

    yield cons_name, cons_type, stmt


def build_header(author, liquify, headers, obj_type, name):

  today = datetime.date.today().isoformat()

  parts = []

  if liquify:

    if obj_type == "table":
      cs = f"create_table_{name}"
    elif obj_type == "view":
      cs = f"create_view_{name}"
    elif obj_type == "index":
      cs = f"create_index_{name}"
    else:
      cs = f"add_constraint_{name}"

    parts.append(
      LIQUIBASE_HEADER_TEMPLATE.format(
        author=author,
        changeset_id=cs
      )
    )

  if headers:

    parts.append(
      HEADER_TEMPLATE.format(
        author=author,
        date=today
      )
    )

  if not parts:
    return None

  return "\n".join(parts)


def assemble_sql(header, sql):

  if header:
    return header + "\n\n" + sql

  return sql


def split_kind(kind, src, out_root, extractor, author, liquify, headers):

  text = src.read_text(encoding="utf-8", errors="ignore")

  out_dir = out_root / DIR_MAP[kind]

  written = []

  for name, stmt in extractor(text):

    header = build_header(author, liquify, headers, kind, name)

    sql = normalise_sql(stmt.strip())

    body = assemble_sql(header, sql)

    out = out_dir / f"{name}.sql"

    write_text(out, body)

    written.append(out)

  return written

def generate_run_all(out_root: pathlib.Path):

  run_script = out_root / "run_all.sql"

  sections = [
    ("tables", "table"),
    ("constraints_pk", "constraint_pk"),
    ("constraints_uc", "constraint_uc"),
    ("constraints_fk", "constraint_fk"),
    ("constraints_other", "constraint_other"),
    ("indexes", "index"),
    ("views", "view"),
  ]

  lines = []
  lines.append("set echo on\n")
  lines.append("spool run_all.log\n")

  for label, directory in sections:

    dir_path = out_root / directory

    if not dir_path.exists():
      continue

    files = sorted(dir_path.glob("*.sql"))

    if not files:
      continue

    lines.append(f"prompt === {label} ===")

    for f in files:
      rel = f.relative_to(out_root)
      lines.append(f"@{rel}")

    lines.append("")

  lines.append("spool\n")
  lines.append("spool off\n")
  run_script.write_text("\n".join(lines) + "\n", encoding="utf-8")


def split_constraints(src, out_root, author, liquify, headers):

  text = src.read_text(encoding="utf-8", errors="ignore")

  written = []

  for cons_name, cons_type, stmt in extract_constraints(text):

    subdir = CONSTRAINT_DIR_MAP.get(cons_type, "constraint_other")

    header = build_header(author, liquify, headers, "constraint", cons_name)

    sql = normalise_sql(stmt.strip())

    body = assemble_sql(header, sql)

    out = out_root / subdir / f"{cons_name}.sql"

    write_text(out, body)

    written.append(out)

  return written


def run():

  ap = argparse.ArgumentParser()

  ap.add_argument("input")
  ap.add_argument("--sql-root", default=SQL_ROOT_DEFAULT)
  ap.add_argument("--guid", help="Liquibase author GUID")
  ap.add_argument("-H","--headers", action="store_true",
                  help="Include author/date metadata header")
  ap.add_argument("-L","--liquify", action="store_true",
                  help="Emit Liquibase formatted SQL")
  ap.add_argument("--tables-only", action="store_true")
  ap.add_argument("--views-only", action="store_true")
  ap.add_argument("--indexes-only", action="store_true")
  ap.add_argument("--constraints-only", action="store_true")

  args = ap.parse_args()

  author = args.guid if args.guid else getpass.getuser()

  src = pathlib.Path(args.input)

  out_root = pathlib.Path(args.sql_root)

  written = []

  if args.tables_only:
    written += split_kind("table", src, out_root,
                          lambda t: extract_by_regex(t, RX_TABLE_START, 2),
                          author, args.liquify, args.headers)

  elif args.views_only:
    written += split_kind("view", src, out_root,
                          lambda t: extract_by_regex(t, RX_VIEW_START, 2),
                          author, args.liquify, args.headers)

  elif args.indexes_only:
    written += split_kind("index", src, out_root,
                          lambda t: extract_by_regex(t, RX_INDEX_START, 2),
                          author, args.liquify, args.headers)

  elif args.constraints_only:
    written += split_constraints(src, out_root,
                                 author, args.liquify, args.headers)

  else:

    written += split_kind("table", src, out_root,
                          lambda t: extract_by_regex(t, RX_TABLE_START, 2),
                          author, args.liquify, args.headers)

    written += split_kind("view", src, out_root,
                          lambda t: extract_by_regex(t, RX_VIEW_START, 2),
                          author, args.liquify, args.headers)

    written += split_kind("index", src, out_root,
                          lambda t: extract_by_regex(t, RX_INDEX_START, 2),
                          author, args.liquify, args.headers)

    written += split_constraints(src, out_root,
                                 author, args.liquify, args.headers)

  generate_run_all(out_root)


  print("Wrote:")

  for p in written:
    print(f" - {p}")


if __name__ == "__main__":
  run()

