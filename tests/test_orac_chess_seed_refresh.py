"""Verify portable Chess seed capture, rendering and installation routing."""
# Author: Clive Bostock
# Date: 14-Nov-2026
# Description: Exercise coherent snapshots and lossless API-mediated current seeds.

from copy import deepcopy
import json
from pathlib import Path
import re
from unittest.mock import MagicMock
import xml.etree.ElementTree as ET

import pytest

from plugins.orac_chess.tools import refresh_seeds as refresh


def snapshot() -> dict:
    """Build a small portable graph with a video and a dependent mainline."""
    return {'format': 1, 'content_sources': [{'creator': 'Creator', 'author': None, 'notes': None}],
            'eco_codes': [{'eco_code': 'A00', 'description': 'Reference'}],
            'catalogue': {'entries': [
                {'key': 'root', 'kind': 'VARIATION', 'desired': {'fields': {
                    'name': 'Main', 'owner_kind': 'OPENING', 'owner_key': 'opening',
                    'parent_key': None, 'line_kind': 'MAIN', 'branch_ply': None,
                    'pgn': '1. e4 *', 'annotation': None, 'starting_fen': None},
                    'relationships': {'eco_codes': ['A00']}}},
                {'key': 'opening', 'kind': 'OPENING', 'desired': {'fields': {
                    'name': 'Opening', 'description': None, 'strategy': None,
                    'opening_type': 'OPENING', 'parent_key': None},
                    'relationships': {'eco_codes': ['A00'], 'aliases': []}}}]},
            'videos': [{'platform': 'YouTube', 'external_video_id': 'abcdefghijk',
                        'video_url': 'https://youtu.be/abcdefghijk', 'title': 'Video',
                        'creator': 'Creator', 'description': None, 'duration_seconds': None,
                        'published_on': None, 'opening_keys': ['opening'],
                        'gambit_keys': [], 'variation_keys': ['root']}]}


def decode(sql: str):
    """Decode the exact packaged UTF-8 SQL payload."""
    chunks = re.findall(r"append_payload\('([0-9a-f]+)'\)", sql)
    return json.loads(b''.join(bytes.fromhex(s) for s in chunks).decode())


def test_lossless_clob_and_deterministic_bytes() -> None:
    data = snapshot()
    text = "  O'Brien 🎲\n" * 10000
    data['content_sources'][0]['notes'] = text
    data['videos'][0]['description'] = text
    data['videos'][0]['published_on'] = '2026-11-14T15:16:17'
    first = refresh.render(deepcopy(data))
    second = refresh.render(deepcopy(data))
    assert first == second
    assert decode(first[refresh.SEEDS / 'chess_content_source.sql'][0])[0]['notes'] == text
    assert decode(first[refresh.SEEDS / 'chess_video.sql'][0])[0]['description'] == text
    assert decode(first[refresh.SEEDS / 'chess_video.sql'][0])[0]['published_on'] == '2026-11-14T15:16:17'
    entries = decode(first[refresh.SEEDS / 'chess_catalogue.sql'][0])['entries']
    assert [e['key'] for e in entries] == ['opening', 'root']
    assert entries[0]['desired']['fields']['description'] is None


@pytest.mark.parametrize('problem', ['cycle', 'missing', 'duplicate', 'video', 'eco', 'owner'])
def test_invalid_graph_refused_before_files_change(tmp_path: Path, problem: str) -> None:
    data = snapshot()
    entries = data['catalogue']['entries']
    if problem == 'cycle':
        entries[1]['desired']['fields']['parent_key'] = 'opening'
    elif problem == 'missing':
        entries[0]['desired']['fields']['parent_key'] = 'absent'
    elif problem == 'duplicate':
        entries.append(deepcopy(entries[0]))
    elif problem == 'video':
        data['videos'][0]['variation_keys'] = ['opening']
    elif problem == 'eco':
        entries[1]['desired']['relationships']['eco_codes'] = ['Z99']
    else:
        entries[0]['desired']['fields']['owner_key'] = 'root'
    path = tmp_path / 'untouched.sql'
    path.write_text('original')
    with pytest.raises(ValueError):
        refresh.render(data)
    assert path.read_text() == 'original'


def test_capture_reads_one_transaction_and_always_closes() -> None:
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.__iter__.return_value = iter([])
    raw = refresh.capture(connection)
    assert set(raw) == set(refresh.COLUMNS)
    assert cursor.execute.call_args_list[0].args == ('set transaction read only',)
    assert all('select *' not in c.args[0] for c in cursor.execute.call_args_list)
    connection.rollback.assert_called_once()
    connection.close.assert_called_once()
    connection.reset_mock()
    cursor.execute.side_effect = RuntimeError('read failed')
    with pytest.raises(RuntimeError):
        refresh.capture(connection)
    connection.rollback.assert_called_once()
    connection.close.assert_called_once()


def test_capture_preserves_ledger_key_after_rename() -> None:
    raw = {name: [] for name in refresh.COLUMNS}
    raw['chess_opening_v'] = [{'opening_id': 42, 'name': 'Renamed', 'opening_type': 'OPENING',
                             'description': None, 'strategy': None, 'parent_opening_id': None}]
    raw['chess_catalogue_entry'] = [{'entity_kind': 'OPENING', 'catalogue_key': 'stable',
                                    'opening_id': 42, 'gambit_id': None, 'variation_id': None}]
    result = refresh.portable(raw)
    assert result['catalogue']['entries'][0]['key'] == 'stable'
    assert 'opening_id' not in json.dumps(result)


def test_check_never_writes_and_reports_each_file(tmp_path: Path, capsys) -> None:
    path = tmp_path / 'seed.sql'
    assert refresh.write_outputs({path: ('content', '2 records')}, check=True)
    assert not path.exists()
    refresh.write_outputs({path: ('content', '2 records')})
    assert path.read_text() == 'content'
    assert f'Writing 2 records: {path}' in capsys.readouterr().out
    assert not refresh.write_outputs({path: ('content', '2 records')}, check=True)


def test_current_snapshot_is_reproducible_and_fully_reachable() -> None:
    current = json.loads(refresh.SNAPSHOT.read_text())
    for path, (sql, _) in refresh.render(current).items():
        assert path.read_text() == sql
    controller = refresh.ROOT / 'db/liquibase/pluginController.xml'
    reached = set()
    def walk(path: Path) -> None:
        assert path.is_file(), path
        reached.add(path.resolve())
        if path.suffix == '.xml':
            for item in ET.parse(path).getroot():
                if item.tag.endswith('include'):
                    walk(path.parent / item.attrib['file'])
    walk(controller)
    assert set(refresh.render(current)) <= reached
    assert not any(p.name.startswith('chess_batch_') for p in reached)
    assert len(current['catalogue']['entries']) >= 5198
    assert len(current['videos']) >= 44
    assert all(v['creator'] in {s['creator'] for s in current['content_sources']} for v in current['videos'])


def test_variation_keys_are_scoped_to_owner() -> None:
    raw = {name: [] for name in refresh.COLUMNS}
    previous = {'catalogue': {'entries': []}}
    for i in (1, 2):
        owner = f'owner_{i}'
        raw['chess_opening_v'].append({'opening_id': i, 'name': f'Opening {i}',
            'opening_type': 'OPENING', 'description': None, 'strategy': None,
            'parent_opening_id': None})
        raw['chess_variation_v'].append({'variation_id': i, 'opening_id': i,
            'gambit_id': None, 'parent_variation_id': None, 'branch_ply': None,
            'name': 'Shared Main Line', 'line_kind': 'MAIN', 'pgn': '1. e4 *',
            'starting_fen': None, 'annotation': None})
        previous['catalogue']['entries'] += [
            {'kind': 'OPENING', 'key': owner, 'desired': {'fields': {'name': f'Opening {i}'}}},
            {'kind': 'VARIATION', 'key': f'root_{i}', 'desired': {'fields': {
                'name': 'Shared Main Line', 'owner_key': owner}}}]
    result = refresh.portable(raw, previous)
    assert {e['key'] for e in result['catalogue']['entries']} == {'owner_1', 'owner_2', 'root_1', 'root_2'}
    raw['chess_opening_eco_v'].append({'opening_id': 999, 'eco_code': 'A00'})
    with pytest.raises(ValueError, match='Dangling'):
        refresh.portable(raw, previous)


def test_staging_failure_preserves_all_original_files(tmp_path: Path, monkeypatch) -> None:
    first, second = tmp_path / 'first.sql', tmp_path / 'second.sql'
    first.write_text('first original')
    second.write_text('second original')
    original = Path.write_text
    def fail_second(path: Path, content: str, **kwargs):
        if path.name == 'second.sql.tmp':
            raise OSError('disk unavailable')
        return original(path, content, **kwargs)
    monkeypatch.setattr(Path, 'write_text', fail_second)
    with pytest.raises(OSError, match='disk unavailable'):
        refresh.write_outputs({first: ('new first', '1 record'), second: ('new second', '2 records')})
    assert first.read_text() == 'first original'
    assert second.read_text() == 'second original'
    assert not list(tmp_path.glob('*.tmp'))


def test_live_alien_videos_and_associations_are_packaged() -> None:
    data = json.loads(refresh.SNAPSHOT.read_text())
    alien = next(e['key'] for e in data['catalogue']['entries']
                 if e['kind'] == 'GAMBIT' and e['desired']['fields']['name'] == 'Alien Gambit')
    videos = {v['external_video_id']: v for v in data['videos']}
    for identity, title in [('S6dozy6euxc', 'The Alien Gambit'),
                            ('lP6BgSkOPlY', 'CRUSH The Alien Gambit With This Simple System')]:
        assert videos[identity]['title'] == title
        assert alien in videos[identity]['gambit_keys']
    packaged = decode((refresh.SEEDS / 'chess_video.sql').read_text())
    assert packaged == data['videos']
    sources = {r['creator']: r for r in data['content_sources']}
    assert sources['Gotham Chess'] == {'creator': 'Gotham Chess', 'author': 'Levy Rozman', 'notes': 'IM'}


def sqlcl_output() -> str:
    """Build complete UTF-8 capture markers without invoking a real connection."""
    lines = ['SEED_TARGET:ORAC_APX_PUB|FREEPDB1']
    for view in refresh.COLUMNS:
        payload = [{'notes': " O'Brien 🎲\n" * 5000}] if view == 'chess_content_source_v' else []
        lines += ['SEED_BEGIN:' + view, 'SEED_HEX:' + json.dumps(payload, ensure_ascii=False).encode().hex(), 'SEED_END']
    return '\n'.join(lines + ['SEED_COMPLETE'])


def test_sqlcl_capture_is_explicit_read_only_and_lossless(monkeypatch, capsys) -> None:
    from types import SimpleNamespace
    scripts = []
    def run(arguments, **kwargs):
        assert arguments[:4] == ['sql', '-s', '-name', 'orac_apx_pub']
        assert 'shell' not in kwargs
        scripts.append(Path(arguments[4][1:]).read_text())
        return SimpleNamespace(returncode=0, stdout=sqlcl_output())
    monkeypatch.setattr(refresh.subprocess, 'run', run)
    result = refresh.capture_sqlcl('orac_apx_pub', 'ORAC_APX_PUB', 'FREEPDB1')
    assert result['chess_content_source_v'][0]['notes'] == " O'Brien 🎲\n" * 5000
    script = scripts[0]
    assert script.count('set transaction read only;') == 1
    assert script.count('rollback;') == 1
    assert 'when' not in script.lower().replace('whenever sqlerror exit failure rollback', '')
    assert "user <> 'ORAC_APX_PUB'" in script
    assert 'length2(l_piece)' in script
    assert 'Captured read-only ORAC_APX_PUB in FREEPDB1' in capsys.readouterr().out


@pytest.mark.parametrize('problem', ['target', 'missing', 'duplicate', 'hex', 'complete'])
def test_sqlcl_capture_refuses_partial_or_wrong_target(problem: str) -> None:
    output = sqlcl_output()
    if problem == 'target':
        output = output.replace('ORAC_APX_PUB|FREEPDB1', 'SYSTEM|OTHER')
    elif problem == 'missing':
        output = output.replace('SEED_END', '', 1)
    elif problem == 'duplicate':
        output = output.replace('SEED_COMPLETE', 'SEED_BEGIN:chess_video_v\nSEED_HEX:5b5d\nSEED_END\nSEED_COMPLETE')
    elif problem == 'hex':
        output = output.replace('SEED_HEX:', 'SEED_HEX:zz', 1)
    else:
        output = output.replace('SEED_COMPLETE', '')
    with pytest.raises(ValueError):
        refresh.parse_sqlcl_capture(output, 'ORAC_APX_PUB', 'FREEPDB1')
