"""Verify complete-parent continuation semantics and production routing."""
# Author: Clive Bostock
# Date: 10-Nov-2026
# Description: Guard additive continuation support without weakening true branches.

import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1] / 'plugins/orac_chess'


def test_typed_continuation_replays_complete_parent_and_preserves_alternatives() -> None:
    """Real policy replay rejects truncation, changed moves, wrong ply and own FEN."""
    source = (ROOT / 'tools/mle/production_bridge.mjs').read_text().replace(
        "'orac-chess-policy'", repr((ROOT / 'tools/mle/validator.mjs').as_uri()))
    program = '''
import assert from 'node:assert/strict';
const b=await import('data:text/javascript;base64,'+Buffer.from(process.env.CHESS_BRIDGE_SOURCE).toString('base64'));
const c=s=>({length:()=>s.length,getData:()=>s});
const parent=c('1.e4 e5 *'),child=c('1.e4 e5 2.Nf3 Nc6 *');
assert.equal(b.validateContinuation(parent,child,2,null),null);
for(const [pgn,ply] of [['1.e4 c5 2.Nf3 *',2],['1.e4 e5 *',2],['1.e4 *',2],
 ['1.e4 e5 2.Nf3 *',1],['1.e4 e5 2.Nf3 *',2.5],['1.e4 e5 2.Nf3 *',-1],
 ['[SetUp "1"] [FEN "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"] 1.e4 e5 2.Nf3 *',2]]) {
 assert.notEqual(b.validateContinuation(parent,c(pgn),ply,null),null);
}
assert.equal(b.validateBranch(parent,c('1.e4 c5 *'),1,null),null);
assert.notEqual(b.validateBranch(parent,child,2,null),null);
assert.notEqual(b.validateContinuation(null,child,2,null),null);
'''
    subprocess.run(['node', '--input-type=module', '--eval', program],
                   env=os.environ | {'CHESS_BRIDGE_SOURCE': source}, check=True,
                   capture_output=True, text=True, timeout=30)


def test_continuation_routes_immediate_and_retained_descendant_validation() -> None:
    """Both TAPI versions and whole-tree validation retain owner/FEN checks."""
    for name in ['chess_admin_tapi.sql', 'chess_admin_tapi_eco.sql']:
        body = (ROOT / 'db/schema/package_body' / name).read_text()
        assert "if p_line_kind = 'CONTINUATION'" in body
        assert 'chess_validation_api.validate_continuation(l_parent,p_pgn,p_branch_ply,l_fen);' in body
        assert 'chess_validation_api.validate_branch(l_parent,p_pgn,p_branch_ply,l_fen);' in body
        assert 'chess_validation_api.validate_variation_tree(p_id);' in body
        assert 'Ordinary maintenance cannot change variation ownership.' in body
        assert 'Only a root variation may define a starting FEN.' in body
    body = (ROOT / 'db/schema/package_body/chess_validation_api.sql').read_text()
    assert "if l_node.line_kind = 'CONTINUATION'" in body
    assert 'validate_continuation(l_parent.pgn,l_node.pgn,l_node.branch_ply,l_root.starting_fen);' in body
    assert 'validate_branch(l_parent.pgn,l_node.pgn,l_node.branch_ply,l_root.starting_fen);' in body
    assert 'Every variation in a tree must have the same owner.' in body
    recovery = (ROOT / 'db/recovery/mle/chess_validation_api.sql').read_text()
    assert 'procedure validate_continuation(' in recovery
    continuation = recovery.split('procedure validate_continuation(', 1)[1].split('procedure validate_variation_tree(', 1)[0]
    assert "raise_application_error(-20020,'Chess PGN maintenance is unavailable: runtime withdrawn.')" in continuation
    assert 'chess_mle_continuation(' not in continuation


def test_structural_migration_precedes_batches_and_ui_uses_additive_line_kind() -> None:
    """Immutable widening and native item metadata are wired before new seed data."""
    includes = [n.attrib['file'] for n in ET.parse(ROOT / 'db/liquibase/pluginController.xml').getroot()]
    assert includes.index('controllers/11_admin_compile.xml') < includes.index('controllers/17_continuation.xml') < includes.index('controllers/15_eco_seed_batches.xml')
    sql = (ROOT / 'db/schema/constraint_other/chs_var_continuation_ck.sql').read_text()
    assert sql.index('add constraint chs_var_continuation_ck') < sql.index('drop constraint chs_var_branch_ck')
    assert "line_kind in ('ALTERNATIVE','CONTINUATION')" in sql
    assert 'runOnChange:' not in sql
    for relative in ['orac_chess_admin.sql', 'recovery/orac_chess_admin_readonly.sql']:
        export = (ROOT / 'apex' / relative).read_text()
        assert "STATIC:MAIN;MAIN,ALTERNATIVE;ALTERNATIVE,CONTINUATION;CONTINUATION" in export
        assert 'CONTINUATION extends the complete parent' in export


def test_insert_only_optimisation_keeps_authoritative_local_and_update_checks() -> None:
    """New PKs are leaves; inserts validate their edge while updates retain subtree checks."""
    for name in ['chess_admin_tapi.sql', 'chess_admin_tapi_eco.sql']:
        text = (ROOT / 'db/schema/package_body' / name).read_text()
        body = text.split('  procedure save_variation(', 1)[1].split('  procedure delete_variation(', 1)[0]
        insert = body.index('insert into chess_variation')
        assert body.index('l_is_insert boolean := p_id is null') < insert
        for check in ['chess_validation_api.lock_control;',
                      'Ordinary maintenance cannot change variation ownership.',
                      'Choose exactly one owner opening or gambit.',
                      'Only a root variation may define a starting FEN.',
                      'A variation cannot contain a hierarchy cycle.',
                      'chess_validation_api.validate_pgn(p_pgn,true,l_fen);',
                      'chess_validation_api.validate_continuation(l_parent,p_pgn,p_branch_ply,l_fen);',
                      'chess_validation_api.validate_branch(l_parent,p_pgn,p_branch_ply,l_fen);']:
            assert body.index(check) < insert
        assert "if not l_is_insert\n    then\n      chess_validation_api.validate_variation_tree(p_id);\n    end if;" in body
        assert 'rollback to chess_admin_save;' in body
    for name in ['chs_var_parent_opn_fk.sql', 'chs_var_parent_gmb_fk.sql']:
        fk = (ROOT / 'db/schema/constraint_fk' / name).read_text()
        assert 'deferrable' not in fk.lower()
        assert 'references orac_chess.chess_variation' in fk.lower()
