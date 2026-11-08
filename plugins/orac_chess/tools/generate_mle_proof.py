"""Generate deterministic, isolated Oracle MLE proof scripts."""

# Author: Clive Bostock
# Date: 06-Nov-2026
# Description: Package pinned chess.js and strict policy as diagnostic modules.
# Purpose: Produce reviewable DEV-only installation, test and cleanup assets.
# Usage: python3 plugins/orac_chess/tools/generate_mle_proof.py --check

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HEADER = """-- Author: Clive Bostock
-- Date: 06-Nov-2026
-- Purpose: Isolated DEV MLE feasibility proof; never included by plugin controllers.
-- Usage: SQLcl @plugins/orac_chess/db/diagnostics/mle/<script>.sql
whenever sqlerror exit failure rollback
whenever oserror exit failure rollback
set define off
set sqlblanklines on
set serveroutput on
"""
NAMES = (
    "CHESS_MLE_PROOF_LIB",
    "CHESS_MLE_PROOF_POLICY",
    "CHESS_MLE_PROOF_BRIDGE",
    "CHESS_MLE_PROOF_ENV",
    "CHESS_MLE_PROOF_RUN",
    "CHESS_MLE_PROOF_SMOKE",
)


def clob_assignments(variable: str, text: str) -> str:
    """Encode UTF-8 chunks as hex so SQLcl cannot rewrite JS escapes."""
    return "".join(
        f"  {variable} := {variable} || to_clob(utl_i18n.raw_to_char(hextoraw('{text[i:i+400].encode('utf-8').hex()}'), 'AL32UTF8'));\n"
        for i in range(0, len(text), 400)
    )


def generate(root: Path) -> dict[Path, str]:
    """Build scripts after checking every pinned upstream byte."""
    vendor = root / "vendor/chess.js-1.4.0"
    provenance = json.loads((vendor / "PROVENANCE.json").read_text())
    for name, expected in provenance["files_sha256"].items():
        if hashlib.sha256((vendor / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Vendor checksum mismatch: {name}")
    target = root / "db/diagnostics/mle"
    guard = """begin
  if sys_context('userenv','session_user') <> 'SYSTEM'
     or sys_context('userenv','con_name') <> 'FREEPDB1'
  then
    raise_application_error(-20000, 'Requires approved SYSTEM DEV FREEPDB1 connection');
  end if;
end;
/
"""
    names = ",".join("'" + n + "'" for n in NAMES)
    preflight = HEADER + guard + f"""declare
  l_count pls_integer;
begin
  select count(*) into l_count from dba_objects
  where owner = 'ORAC_CHESS' and object_name in ({names});
  if l_count <> 0
  then
    raise_application_error(-20001, 'Proof object collision: inspect DBA_OBJECTS; no replacements allowed');
  end if;
end;
/
"""
    install = HEADER + "@@preflight.sql\n"
    install += """create function orac_chess.chess_mle_proof_smoke return number
as mle language javascript pure
{{ return 6 * 7; }};
/
declare
  l_result number;
begin
  l_result := orac_chess.chess_mle_proof_smoke();
  if l_result <> 42
  then
    raise_application_error(-20002, 'MLE arithmetic proof failed');
  end if;
end;
/
"""
    sources = [
        ("lib", (vendor / "chess.mjs").read_text()),
        (
            "policy",
            (root / "tools/mle/validator.mjs")
            .read_text()
            .replace("'../../vendor/chess.js-1.4.0/chess.mjs'", "'orac-chess-lib'"),
        ),
        ("bridge", (root / "tools/mle/bridge.mjs").read_text()),
    ]
    for name, source in sources:
        statement = f"create mle module orac_chess.chess_mle_proof_{name}\nlanguage javascript as\n{source}"
        install += "declare\n  l_source clob;\nbegin\n"
        install += clob_assignments("l_source", statement)
        install += "  execute immediate l_source;\nend;\n/\n"
        install += f"""declare
  l_valid pls_integer;
begin
  select count(*) into l_valid from dba_objects
  where owner = 'ORAC_CHESS' and object_name = 'CHESS_MLE_PROOF_{name.upper()}'
    and object_type = 'MLE MODULE' and status = 'VALID';
  if l_valid <> 1
  then
    raise_application_error(-20007, 'Invalid MLE module: CHESS_MLE_PROOF_{name.upper()}');
  end if;
end;
/
"""
    install += """create mle env orac_chess.chess_mle_proof_env
imports (
  'orac-chess-lib' module orac_chess.chess_mle_proof_lib,
  'orac-chess-policy' module orac_chess.chess_mle_proof_policy
) pure;
create function orac_chess.chess_mle_proof_run(p_input clob) return clob
as mle module orac_chess.chess_mle_proof_bridge
  env orac_chess.chess_mle_proof_env signature 'run';
/
prompt MLE_PROOF_INSTALL_CREATED
"""
    corpus = (root / "tools/mle/corpus.json").read_text()
    cases = json.loads(corpus) + [
        {"name": "depth64", "depth": 64, "valid": True},
        {"name": "depth65", "depth": 65, "valid": False},
        {"name": "size4Mi", "size": 4194304, "valid": True},
        {"name": "size4Mi-plus-one", "size": 4194305, "valid": False},
        {
            "name": "long-legal-pgn",
            "pgn": "1.e4 {" + "x" * 64000 + "} *",
            "valid": True,
        },
    ]
    request = json.dumps({"cases": cases}, separators=(",", ":"))
    request_assignments = clob_assignments("l_request", request)
    test = HEADER + guard + f"""declare
  l_request clob;
  l_output clob;
  l_failures pls_integer;
  l_count pls_integer;
begin
{request_assignments}  l_output := orac_chess.chess_mle_proof_run(l_request);
  select count(*) into l_failures
  from json_table(l_request, '$.cases[*]' columns (
    name varchar2(100) path '$.name', valid varchar2(5) path '$.valid')) expected
  full outer join json_table(l_output, '$.results[*]' columns (
    name varchar2(100) path '$.name', valid varchar2(5) path '$.valid')) actual
  on expected.name = actual.name
  where expected.valid <> actual.valid or actual.valid is null
     or actual.valid not in ('true','false')
     or expected.name is null or actual.name is null;
  select count(*) into l_count from json_table(l_output, '$.results[*]' columns (name varchar2(100) path '$.name'));
  if l_failures <> 0 or l_count <> 44
  then
    raise_application_error(-20003, 'Portable MLE corpus mismatch');
  end if;
  if json_value(l_output, '$.header') <> 'proof' or json_value(l_output, '$.header') is null
  then
    raise_application_error(-20005, 'Runtime header extraction failed');
  end if;
  dbms_lob.freetemporary(l_output);
  -- Input and output both exceed the VARCHAR2 limit. Caller frees returned LOB.
  l_request := to_clob('{{"cases":[],"echo":"') || to_clob(rpad('x',32000,'x')) || to_clob(rpad('x',32000,'x')) || '"}}';
  l_output := orac_chess.chess_mle_proof_run(l_request);
  if dbms_lob.getlength(l_output) < 64000
  then
    raise_application_error(-20004, 'CLOB output was truncated');
  end if;
  dbms_lob.freetemporary(l_output);
  dbms_output.put_line('MLE_PROOF_PASS: 44 corpus/boundary cases; CLOB input/output >64K');
end;
/
"""
    cleanup = HEADER + guard
    for kind, name, objtype in [
        ("function", "run", "FUNCTION"),
        ("function", "smoke", "FUNCTION"),
        ("mle env", "env", "MLE ENVIRONMENT"),
        ("mle module", "bridge", "MLE MODULE"),
        ("mle module", "policy", "MLE MODULE"),
        ("mle module", "lib", "MLE MODULE"),
    ]:
        object_name = "CHESS_MLE_PROOF_" + name.upper()
        cleanup += f"""declare
  l_count pls_integer;
  l_conflicts pls_integer;
begin
  select count(*), count(case when object_type <> '{objtype}' then 1 end)
  into l_count, l_conflicts from dba_objects
  where owner = 'ORAC_CHESS' and object_name = '{object_name}';
  if l_conflicts <> 0
  then
    raise_application_error(-20006, 'Conflicting proof object type: {object_name}');
  end if;
  if l_count > 0
  then
    execute immediate 'drop {kind} orac_chess.chess_mle_proof_{name}';
  end if;
end;
/
"""
    cleanup += "prompt MLE_PROOF_CLEANUP_COMPLETE\n"
    return {
        target / "preflight.sql": preflight,
        target / "install.sql": install,
        target / "test.sql": test,
        target / "cleanup.sql": cleanup,
    }


def main() -> None:
    """Write deterministic assets or reject drift without changing files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for path, content in generate(Path(__file__).resolve().parents[1]).items():
        if args.check:
            if not path.exists() or path.read_text() != content:
                raise SystemExit(f"Generated proof asset differs: {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)


if __name__ == "__main__":
    main()
