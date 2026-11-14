"""Verify curated starter data, genuine PGN divergence and immutable packaging."""
# Author: Clive Bostock
# Date: 10-Nov-2026
# Description: Protect source provenance, branch topology and released seed output.

from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'plugins/orac_chess'))
from tools import generate_seed as seed  # noqa: E402

BATCH = seed.ROOT / 'seed/batches/2026_11_10_starter_catalogue'


def write_rows(path: Path, rows: list[dict]) -> None:
    """Write a modified fixture with its complete CSV header."""
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def fixture_batch(tmp_path: Path) -> Path:
    """Copy the source batch without relying on generated SQL."""
    batch = tmp_path / 'fixture_batch'
    batch.mkdir()
    for path in BATCH.glob('*.csv'):
        (batch / path.name).write_bytes(path.read_bytes())
    return batch


def test_catalogue_source_counts_and_moves() -> None:
    """All 190 lines replay legally and retain source-level CC0 provenance."""
    data = seed.load_batch(BATCH)
    assert (len(data['openings']), len(data['gambits']), len(data['variations'])) == (50, 40, 100)
    assert data['videos'] == []
    assert {row['name'] for row in data['openings']} >= {'Colle System', 'Black Lion'}
    assert 'Alien Gambit' in {row['name'] for row in data['gambits']}
    assert sum(row['owner_type'] == 'OPENING' for row in data['variations']) == 60
    assert {row['depth'] for row in data['variations']} == {1, 2}
    manifest = json.loads((BATCH / 'PROVENANCE.json').read_text())
    vendor = seed.ROOT / 'vendor/lichess-chess-openings-3ba6b20'
    assert manifest['source_commit'] == '3ba6b20d31b2e6125cb0e6a2e792f400717d9d39'
    assert len(manifest['entries']) == 190
    for name, digest in manifest['source_sha256'].items():
        assert hashlib.sha256((vendor / name).read_bytes()).hexdigest() == digest
    for entry in manifest['entries']:
        lines = (vendor / entry['source_file']).read_text().splitlines()
        eco, name, pgn = lines[entry['source_line'] - 1].split('\t')
        assert (entry['eco'], entry['source_name'], entry['pgn']) == (eco, name, pgn)
        assert entry['packaged_pgn'] == pgn + ' *'
    family_counts = Counter()
    for entry in manifest['entries']:
        if entry['kind'] == 'VARIATION':
            family = entry['source_name'].split(':')[0]
            if family.startswith("King's Gambit"):
                family = "King's Gambit"
            family_counts[family] += 1
    assert max(family_counts.values()) <= 15
    subjects = [entry for entry in manifest['entries'] if entry['kind'] != 'VARIATION']
    assert Counter(entry['category'] for entry in subjects) == {'mainstream': 63, 'historical': 18, 'unusual': 9}
    opening_names = {row['name'] for row in data['openings']}
    assert all(set(row['opening_names']) <= opening_names for row in data['gambits'])
    for branch in data['variations']:
        assert branch['branch_ply'] >= 0
        if branch['parent_key'] != 'owner-mainline':
            assert next(i for i, p in enumerate(data['variations']) if p['key'] == branch['parent_key']) < data['variations'].index(branch)
    black_lion = next(row for row in data['openings'] if row['name'] == 'Black Lion')
    assert black_lion['mainline_pgn'].startswith('1. e4 d6 2. d4 Nf6 3. Nc3 Nbd7')


def test_released_sql_and_templates_remain_byte_identical() -> None:
    """Extending CSV input does not rewrite either released runtime contract."""
    for relative in ['tools/seed_runtime.sql', 'tools/seed_runtime_eco.sql',
                     'db/schema/seed_data/chess_batch_2026_11_07_bootstrap.sql']:
        path = seed.ROOT / relative
        original = subprocess.run(['git', 'show', 'HEAD:' + str(path.relative_to(ROOT))],
                                  capture_output=True, check=True).stdout
        assert path.read_bytes() == original
    assert seed.generate(BATCH) == seed.generate(BATCH)
    assert seed.generate(BATCH) == (seed.ROOT / 'db/schema/seed_data/chess_batch_2026_11_10_starter_catalogue.sql').read_text()


@pytest.mark.parametrize('problem', ['extension', 'illegal', 'cycle', 'unknown_parent', 'owner', 'eco', 'depth'])
def test_bad_branch_input_fails(fixture_batch: Path, problem: str) -> None:
    """Malformed branches fail before any installable SQL is emitted."""
    path = fixture_batch / 'variations.csv'
    rows = list(csv.DictReader(path.open()))
    if problem == 'extension':
        owner = next(r for r in csv.DictReader((fixture_batch / 'openings.csv').open()) if r['name'] == rows[0]['owner_name'])
        rows[0]['pgn'] = owner['mainline_pgn']
    elif problem == 'illegal':
        rows[0]['pgn'] = '1. e4 e5 2. Ke3 *'
    elif problem == 'cycle':
        rows[0]['parent_key'] = rows[0]['key']
    elif problem == 'unknown_parent':
        rows[0]['parent_key'] = 'missing'
    elif problem == 'owner':
        rows[0]['owner_name'] = 'Unknown Opening'
    elif problem == 'eco':
        rows[0]['eco_codes'] = 'Z99'
    else:
        # Three parent edges are forbidden, independently of move compatibility.
        same = [r for r in rows if r['owner_name'] == rows[0]['owner_name'] and r['owner_type'] == rows[0]['owner_type']]
        if len(same) < 3:
            same = [dict(rows[0], key='extra_a', name='Extra A'),dict(rows[0], key='extra_b', name='Extra B'), rows[0]]
            rows.extend(same[:2])
        same[0]['parent_key'] = 'owner-mainline'
        same[1]['parent_key'] = same[0]['key']
        same[2]['parent_key'] = same[1]['key']
    write_rows(path, rows)
    with pytest.raises(ValueError):
        seed.generate(fixture_batch)


def test_forward_parents_and_unicode_are_safe(fixture_batch: Path) -> None:
    """Forward CSV references sort correctly and SQL treats Unicode as inert data."""
    path = fixture_batch / 'variations.csv'
    rows = list(csv.DictReader(path.open()))
    rows.reverse()
    rows[0]['annotation'] = "O'Brien’s line; / -- 日本語"
    write_rows(path, rows)
    sql = seed.generate(fixture_batch)
    assert '日本語' not in sql and "O'Brien" not in sql
    assert 'hextoraw(' in sql
    assert seed.load_batch(fixture_batch)['variations']


def test_runtime_atomic_preservation_contract() -> None:
    """Packaged SQL preserves edited data and limits recoverable conflicts precisely."""
    sql = seed.generate(BATCH)
    assert 'rollback to chess_seed_batch' in sql and '--rollback empty' in sql
    assert 'runAlways:' not in sql and 'runOnChange:' not in sql
    assert "if sqlcode != -20025" in sql
    assert 'l_branch_skips.exists(l_parent_key)' in sql
    assert 'Ambiguous variation name within owner' in sql
    assert "'ALTERNATIVE',l_pgn" in sql
    assert 'save_variation_with_eco' in sql
    assert 'insert into' not in sql.lower()


def test_branch_ply_is_zero_based_prefix_length(fixture_batch: Path) -> None:
    """The shared e4/e5 prefix is two plies, matching the production API."""
    path = fixture_batch / 'variations.csv'
    row = next(csv.DictReader(path.open()))
    row.update(parent_key='owner-mainline', pgn='1. e4 e5 2. Bc4 Nf6 *')
    write_rows(path, [row])
    openings_path = fixture_batch / 'openings.csv'
    openings = list(csv.DictReader(openings_path.open()))
    next(owner for owner in openings if owner['name'] == row['owner_name'])['mainline_pgn'] = '1. e4 e5 2. Nf3 Nc6 *'
    write_rows(openings_path, openings)
    assert seed.load_batch(fixture_batch)['variations'][0]['branch_ply'] == 2


@pytest.mark.parametrize('filename,column', [('openings.csv', 'mainline_pgn'),
                                            ('gambits.csv', 'mainline_pgn'),
                                            ('variations.csv', 'pgn')])
def test_incomplete_pgn_without_terminal_result_is_rejected(
    fixture_batch: Path, filename: str, column: str
) -> None:
    """A legal move sequence alone must fail the production complete-PGN policy."""
    path = fixture_batch / filename
    rows = list(csv.DictReader(path.open()))
    assert rows[0][column].endswith(' *')
    rows[0][column] = rows[0][column][:-2]
    write_rows(path, rows)
    with pytest.raises(ValueError, match='Complete PGN requires a terminal result'):
        seed.generate(fixture_batch)
