"""Generate a reviewed data-preserving Chess runtime withdrawal path."""

# Author: Clive Bostock
# Date: 06-Nov-2026
# Description: Restore fail-closed PGN APIs and a read-only administration export.
# Purpose: Withdraw the MLE integration without undoing data or history.
# Usage: python3 plugins/orac_chess/tools/generate_mle_recovery.py --check

from __future__ import annotations

import argparse
import re
from pathlib import Path


def generate(root: Path) -> dict[Path, str]:
    """Create deterministic recovery assets from current public contracts."""
    target = root / 'db/recovery/mle'
    assets: dict[Path, str] = {}
    unavailable = "    raise_application_error(-20020,'Chess PGN maintenance is unavailable: runtime withdrawn.');\n  end;\n"
    validation = (root / 'db/schema/package_body/chess_validation_api.sql').read_text()
    for name, following in [('pgn_header', '  procedure lock_control'), ('validate_pgn', '  procedure validate_branch'), ('validate_branch', '  procedure validate_variation_tree'), ('validate_variation_tree', '  procedure validate_image_structure')]:
        start = validation.index('  ' + ('function' if name == 'pgn_header' else 'procedure') + ' ' + name + '(')
        end = validation.index(following, start)
        declaration = validation[start:validation.index(' is\n', start) + 4]
        validation = validation[:start] + declaration + '  begin\n' + unavailable + validation[end:]
    assets[target / 'chess_validation_api.sql'] = validation
    for entity in ('game', 'variation'):
        source_path = (root / 'db/schema/package_body/chess_variation_api_eco.sql'
                       if entity == 'variation'
                       else root / f'db/schema/package_body/chess_{entity}_api.sql')
        source = source_path.read_text()
        source = re.sub(r'    chess_admin_tapi\.(?:save|delete)_\w+\([^\n]+\);', unavailable.strip().removesuffix('end;').rstrip(), source)
        assets[target / f'chess_{entity}_api.sql'] = source
    source = (root / 'apex/orac_chess_admin.sql').read_text()
    # Withdrawal must describe the actual read-only writer state on the home page.
    source = source.replace(
        'Maintain openings, gambits, games, variations and their instructional material. PGN is validated before saving.',
        'Maintain openings, gambits and their instructional material. Games and variations are read only while the PGN validator runtime is withdrawn.',
    )
    for page in (30,31,60,61):
        marker = f'prompt --application/pages/page_{page:05}'
        at = source.index(marker)
        end = source.index('prompt --application/pages/page_', at + len(marker))
        part = source[at:end]
        part = re.sub(r'wwv_flow_imp_page.create_page_button\(.*?\n\);\n', lambda m: '' if re.search(r"p_button_name=>'(SAVE|DELETE|HEADERS|CREATE)'", m[0]) else m[0], part, flags=re.S)
        if page in (31,61):
            part = re.sub(r"p_display_as=>'NATIVE_(?:TEXT_FIELD|TEXTAREA|NUMBER_FIELD|SELECT_LIST|DATE_PICKER_APEX)'", "p_display_as=>'NATIVE_DISPLAY_ONLY'", part)
            region = f"""wwv_flow_imp_page.create_page_plug(
 p_id=>wwv_flow_imp.id({97000000000000000+page})
,p_plug_name=>'PGN maintenance unavailable'
,p_plug_display_sequence=>1
,p_plug_source=>'<p role="status">Chess PGN maintenance is read only while its validator runtime is withdrawn.</p>'
);
"""
            part = part.replace('end;\n/\n',region+'end;\n/\n')
        source = source[:at]+part+source[end:]
    assets[root / 'apex/recovery/orac_chess_admin_readonly.sql'] = source
    assets[target / 'withdraw.sql'] = """-- Author: Clive Bostock
-- Date: 06-Nov-2026
-- Purpose: Fail closed before removing private MLE; retain all data and history.
-- Usage: Approved owner/admin SQLcl @plugins/orac_chess/db/recovery/mle/withdraw.sql
-- First import apex/recovery/orac_chess_admin_readonly.sql through the host receipt path.
-- Preserve the currently installed app ID; this script does not import APEX.
whenever sqlerror exit failure rollback
whenever oserror exit failure rollback
set define off
set sqlblanklines on
begin
  if sys_context('userenv','session_user') not in ('ORAC_CHESS','SYSTEM')
     or sys_context('userenv','con_name')<>'FREEPDB1'
  then
    raise_application_error(-20998,'Wrong approved withdrawal target');
  end if;
end;
/
@@chess_game_api.sql
@@chess_variation_api.sql
@@chess_validation_api.sql
alter package orac_chess.chess_admin_tapi compile body;
alter package orac_chess.chess_game_api compile body;
alter package orac_chess.chess_variation_api compile body;
declare
  l_count number;
begin
  select count(*) into l_count from all_objects where owner='ORAC_CHESS'
  and object_name in ('CHESS_VALIDATION_API','CHESS_ADMIN_TAPI','CHESS_GAME_API','CHESS_VARIATION_API')
  and status<>'VALID';
  if l_count<>0 then raise_application_error(-20020,'Recovery API compilation failed; MLE retained'); end if;
end;
/
drop function orac_chess.chess_mle_header;
drop function orac_chess.chess_mle_branch;
drop function orac_chess.chess_mle_validate;
drop mle env orac_chess.chess_mle_env;
drop mle module orac_chess.chess_mle_bridge;
drop mle module orac_chess.chess_mle_policy;
drop mle module orac_chess.chess_mle_lib;
-- No privilege revocation: a pre-existing owner grant must not be removed blindly.
prompt CHESS_MLE_WITHDRAWN_DATA_AND_HISTORY_RETAINED
"""
    return assets


def main() -> None:
    """Write recovery assets or reject source drift."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    for path, source in generate(Path(__file__).resolve().parents[1]).items():
        if args.check:
            if not path.exists() or path.read_text() != source:
                raise SystemExit(f'Recovery asset differs: {path}')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source)


if __name__ == '__main__':
    main()
