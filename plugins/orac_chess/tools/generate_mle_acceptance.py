"""Generate Oracle acceptance coverage for the production Chess facade."""

# Author: Clive Bostock
# Date: 06-Nov-2026
# Description: Send the portable corpus through real production call specifications.
# Purpose: Verify Oracle CLOB, typed arguments and facade error mapping.
# Usage: python3 plugins/orac_chess/tools/generate_mle_acceptance.py --check

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Support both direct CLI execution and imports through the plugin-local package.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.generate_mle_proof import clob_assignments


def generate(root: Path) -> str:
    """Render a rollback-only production runtime acceptance script."""
    source = """-- Author: Clive Bostock
-- Date: 06-Nov-2026
-- Purpose: Verify production facade with the complete corpus and Oracle boundaries.
-- Usage: Approved SQLcl owner/admin @plugins/orac_chess/db/acceptance/verify_mle_runtime.sql
-- This does not deploy objects or commit fixture data.
whenever sqlerror exit failure rollback
whenever oserror exit failure rollback
set define off
set sqlblanklines on
set serveroutput on
declare
  l_pgn clob;
  l_parent clob;
  l_depth clob;
  l_code number;
  l_count number := 0;
  procedure check_case(p_name varchar2,p_valid boolean,p_single boolean,p_fen varchar2 default null,p_ply number default null,p_continuation boolean default false) is
  begin
    l_code:=0;
    begin
      if p_ply is null then
        orac_chess.chess_validation_api.validate_pgn(l_pgn,p_single,p_fen);
      elsif p_continuation then
        orac_chess.chess_validation_api.validate_continuation(l_parent,l_pgn,p_ply,p_fen);
      else
        orac_chess.chess_validation_api.validate_branch(l_parent,l_pgn,p_ply,p_fen);
      end if;
    exception when others then
      l_code:=sqlcode;
      if l_code not in (-20021,-20025) then raise; end if;
    end;
    if (p_valid and l_code<>0) or (not p_valid and l_code=0) then
      raise_application_error(-20999,'Production corpus mismatch: '||p_name||' code='||l_code);
    end if;
    l_count:=l_count+1;
    if dbms_lob.istemporary(l_pgn)=1 then dbms_lob.freetemporary(l_pgn); end if;
    if dbms_lob.istemporary(l_parent)=1 then dbms_lob.freetemporary(l_parent); end if;
  end;
begin
  if sys_context('userenv','session_user') not in ('ORAC_CHESS','SYSTEM')
     or sys_context('userenv','con_name')<>'FREEPDB1' then
    raise_application_error(-20998,'Wrong production runtime verification target');
  end if;
"""
    cases = json.loads((root / 'tools/mle/corpus.json').read_text())
    cases += [{'name':'null-input','pgn':None,'valid':False}, {'name':'unicode-header','pgn':'[Event "♞ café"] 1.e4 *','valid':True}]
    for case in cases:
        source += '  l_pgn:=null; l_parent:=null;\n'
        if case.get('pgn', case.get('child')) is not None:
            source += clob_assignments('l_pgn', case.get('pgn',case.get('child')))
        if 'parent' in case:
            source += clob_assignments('l_parent',case['parent'])
        fen = "'"+case['fen'].replace("'","''")+"'" if case.get('fen') else 'null'
        source += f"  check_case('{case['name']}',{str(case['valid']).lower()},{str(case.get('single')==1).lower()},{fen},{case.get('ply','null')},{str(case.get('op')=='continuation').lower()});\n"
    source += """  for depth in 64..65 loop
    l_pgn:=null;
    for n in 1..depth loop l_pgn:=l_pgn||to_clob('1.e4 ('); end loop;
    l_pgn:=l_pgn||'1.d4'||rpad(')',depth,')')||' *';
    check_case('depth-'||depth,depth=64,false);
  end loop;
  dbms_lob.createtemporary(l_depth,true);
  for n in 1..128 loop dbms_lob.writeappend(l_depth,32767,rpad('a',32767,'a')); end loop;
  dbms_lob.writeappend(l_depth,128,rpad('a',128,'a'));
  l_pgn:=to_clob('1.e4 {')||l_depth||'} *';
  dbms_lob.trim(l_pgn,4194304-3);
  l_pgn:=l_pgn||'} *';
  check_case('size-4Mi',true,false);
  l_pgn:=to_clob('1.e4 {')||l_depth||'aaaa} *';
  check_case('size-over-4Mi',false,false);
  dbms_lob.freetemporary(l_depth);
  if orac_chess.chess_game_api.pgn_header(to_clob('[Event "Unicode ♞"] 1.e4 *'),'Event')<>'Unicode ♞' then
    raise_application_error(-20999,'Unicode header changed at Oracle boundary');
  end if;
  dbms_output.put_line('CHESS_PRODUCTION_MLE_CORPUS_PASSED checks='||l_count);
end;
/
rollback;
exit
"""
    return source


def main() -> None:
    """Write the generated corpus or reject drift."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    path = root / 'db/acceptance/verify_mle_runtime.sql'
    source = generate(root)
    if args.check:
        if not path.exists() or path.read_text()!=source:
            raise SystemExit(f'Production acceptance differs: {path}')
    else:
        path.write_text(source)


if __name__ == '__main__':
    main()
