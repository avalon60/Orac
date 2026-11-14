"""Verify strategy release identity preservation and optional desired-state semantics."""
# Author: Clive Bostock
# Date: 12-Nov-2026
# Description: Check immutable original strategy content and compatibility boundaries.

from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1] / 'plugins/orac_chess'
sys.path.insert(0, str(ROOT))
from tools.generate_catalogue_sync import normalise  # noqa: E402
from tools.generate_strategy_catalogue import build_release  # noqa: E402


def test_strategy_release_preserves_historical_fields() -> None:
    """Every owner receives bounded strategy while all prior records remain identical."""
    source = json.loads((ROOT / 'seed/catalogue/2026_11_10_comprehensive_catalogue/catalogue.json').read_text())
    overlay = json.loads((ROOT / 'seed/strategy/2026_11_12/strategies.json').read_text())
    release = build_release(source, overlay)
    assert (len(source['openings']), len(source['gambits'])) == (128, 612)
    for kind in ('openings', 'gambits'):
        for old, new in zip(source[kind], release[kind], strict=True):
            unchanged = copy.deepcopy(new)
            strategy = unchanged.pop('strategy')
            assert 80 <= len(strategy.split()) <= 130
            assert unchanged == old
            assert overlay['entries'][old['source_key']]['reference_fen']
    assert release['variations'] == source['variations']
    assert release['opening_gambits'] == source['opening_gambits']


def test_optional_strategy_changes_hash_only_when_present() -> None:
    """Missing strategy stays absent and explicit null forms a distinct desired state."""
    source = json.loads((ROOT / 'seed/catalogue/2026_11_10_comprehensive_catalogue/catalogue.json').read_text())
    prior = normalise(source)
    key = source['openings'][0]['source_key']
    old = next(row for row in prior['entries'] if row['key'] == key)
    assert 'strategy' not in old['desired']['fields']
    source['openings'][0]['strategy'] = None
    current = next(row for row in normalise(source)['entries'] if row['key'] == key)
    assert current['desired']['fields']['strategy'] is None
    assert current['source_hash'] != old['source_hash']
    assert all(a == b for a, b in zip(prior['entries'], normalise(source)['entries'], strict=True) if a['key'] != key)


def test_strategy_generators_are_deterministic() -> None:
    """Historical bytes and the new immutable release both remain reproducible."""
    for name in ('generate_catalogue_sync.py', 'generate_strategy_catalogue.py', 'generate_eco_apex.py', 'generate_mle_recovery.py'):
        subprocess.run([sys.executable, str(ROOT / 'tools' / name), '--check'], check=True, timeout=60)


def test_shared_narratives_only_describe_equivalent_positions() -> None:
    """Different reference positions retain concrete distinct instructional reasoning."""
    overlay = json.loads((ROOT / 'seed/strategy/2026_11_12/strategies.json').read_text())
    by_text: dict[str, set[str]] = {}
    for row in overlay['entries'].values():
        by_text.setdefault(row['strategy'], set()).add(' '.join(row['reference_fen'].split()[:4]))
    assert all(len(positions) == 1 for positions in by_text.values())
    assert overlay['equivalent_reference_positions']


def test_reference_positions_and_concrete_pawn_breaks_replay() -> None:
    """Replay every reference and validate the origin/path/target of suggested pawn advances."""
    script = r'''
import fs from 'node:fs';
import {Chess} from './plugins/orac_chess/vendor/chess.js-1.4.0/chess.mjs';
import {parse} from './plugins/orac_chess/tools/mle/validator.mjs';
const overlay=JSON.parse(fs.readFileSync('plugins/orac_chess/seed/strategy/2026_11_12/strategies.json'));
for(const row of Object.values(overlay.entries)) {
  const replay=parse(row.reference_pgn,1);
  const board=new Chess(replay.positions.at(-1));
  if(board.fen()!==row.reference_fen) throw Error(`Reference differs: ${row.name}`);
  for(const m of row.strategy.matchAll(/(White|Black) can prepare ([a-h][1-8])–([a-h][1-8]) to challenge ([a-h][1-8])/g)) {
    const color=m[1]==='White'?'w':'b', dr=color==='w'?1:-1;
    const pawn=board.get(m[2]),target=board.get(m[4]);
    if(pawn?.type!=='p'||pawn.color!==color||board.get(m[3]))throw Error(`Invalid break origin/path: ${row.name}`);
    if(m[2][0]!==m[3][0]||Number(m[3][1])-Number(m[2][1])!==dr)throw Error(`Invalid advance: ${row.name}`);
    if(target?.type!=='p'||target.color===color||Math.abs(m[4].charCodeAt(0)-m[3].charCodeAt(0))!==1||Number(m[4][1])-Number(m[3][1])!==dr)throw Error(`Invalid break target: ${row.name}`);
  }
  for(const m of row.strategy.matchAll(/(White|Black) can use the bishop on ([a-h][1-8]) to pressure ([a-h][1-8])/g)) {
    const color=m[1]==='White'?'w':'b';
    if(board.get(m[2])?.type!=='b'||!board.attackers(m[3],color).includes(m[2]))throw Error(`Blocked bishop ray: ${row.name}`);
  }
}
'''
    subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT.parents[1], check=True, timeout=60)


def test_editorial_release_preserves_identity_and_paragraphs_through_sql() -> None:
    """Editorial prose survives the complete generated payload without other data edits."""
    import re

    prior = json.loads((ROOT / 'seed/catalogue/2026_11_12_strategy_catalogue/catalogue.json').read_text())
    current = json.loads((ROOT / 'seed/catalogue/2026_11_13_editorial_catalogue/catalogue.json').read_text())
    overlay = json.loads((ROOT / 'seed/strategy/2026_11_13/strategies.json').read_text())
    old_overlay = json.loads((ROOT / 'seed/strategy/2026_11_12/strategies.json').read_text())
    assert overlay['equivalent_reference_positions'] == old_overlay['equivalent_reference_positions']
    by_text: dict[str, set[str]] = {}
    for kind in ('openings', 'gambits'):
        for old, new in zip(prior[kind], current[kind], strict=True):
            assert {k: v for k, v in old.items() if k != 'strategy'} == {k: v for k, v in new.items() if k != 'strategy'}
            key = old['source_key']
            assert {k: v for k, v in overlay['entries'][key].items() if k != 'strategy'} == {k: v for k, v in old_overlay['entries'][key].items() if k != 'strategy'}
            assert new['strategy'] == overlay['entries'][key]['strategy']
            assert '\n\n' in new['strategy']
            by_text.setdefault(new['strategy'], set()).add(' '.join(overlay['entries'][key]['reference_fen'].split()[:4]))
    assert all(len(fens) == 1 for fens in by_text.values())
    for key in prior.keys() - {'openings', 'gambits', 'batch_key', 'source_revision', 'provenance'}:
        assert current[key] == prior[key]
    sql = (ROOT / 'db/schema/seed_data/chess_batch_2026_11_13_editorial_catalogue.sql').read_text()
    decoded = json.loads(bytes.fromhex(''.join(re.findall(r"append_payload\('([0-9A-Fa-f]+)'\)", sql))).decode('utf-8'))
    assert decoded == normalise(current)
    assert decoded == json.loads((ROOT / 'seed/catalogue/2026_11_13_editorial_catalogue/sync_payload.json').read_text())


def test_editorial_board_facts_and_pinned_tal_regression() -> None:
    """Replay editorial references and prove the cited bishop rays and Tal pin."""
    script = r'''
import fs from 'node:fs';
import {Chess} from './plugins/orac_chess/vendor/chess.js-1.4.0/chess.mjs';
import {parse} from './plugins/orac_chess/tools/mle/validator.mjs';
const overlay=JSON.parse(fs.readFileSync('plugins/orac_chess/seed/strategy/2026_11_13/strategies.json'));
for(const row of Object.values(overlay.entries)) {
 const board=new Chess(parse(row.reference_pgn,1).positions.at(-1));
 if(board.fen()!==row.reference_fen) throw Error(row.name);
 for(const m of row.strategy.matchAll(/(White|Black)’s bishop on ([a-h][1-8]) has a clear diagonal to ([a-h][1-8])/g)) {
  const color=m[1]==='White'?'w':'b';
  if(board.get(m[2])?.type!=='b'||!board.attackers(m[3],color).includes(m[2])) throw Error(`Blocked bishop ray: ${row.name}`);
 }
 for(const m of row.strategy.matchAll(/(White|Black) can consider preparing ([a-h][1-8])–([a-h][1-8]) to challenge ([a-h][1-8])/g)) {
  const color=m[1]==='White'?'w':'b', dr=color==='w'?1:-1;
  const pawn=board.get(m[2]),target=board.get(m[4]);
  if(pawn?.type!=='p'||pawn.color!==color||board.get(m[3])) throw Error(`Break origin: ${row.name}`);
  if(m[2][0]!==m[3][0]||Number(m[3][1])-Number(m[2][1])!==dr) throw Error(`Advance: ${row.name}`);
  if(target?.type!=='p'||target.color===color||Math.abs(m[4].charCodeAt(0)-m[3].charCodeAt(0))!==1||Number(m[4][1])-Number(m[3][1])!==dr) throw Error(`Target: ${row.name}`);
 }
}
const tal=overlay.entries.gambit_a82cc7ec76957d3199ad93a0c5e02c02;
const board=new Chess(tal.reference_fen);
if(board.moves({verbose:true}).some(m=>m.from==='d7'&&m.to==='d6')) throw Error('Tal regression fixture no longer pinned');
if(!tal.strategy.includes('d7–d6 is illegal')) throw Error('Tal correction missing');
'''
    subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT.parents[1], check=True, timeout=60)
