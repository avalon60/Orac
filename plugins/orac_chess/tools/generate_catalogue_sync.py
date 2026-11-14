"""Normalise comprehensive source records into deterministic private sync input."""
# Author: Clive Bostock
# Date: 11-Nov-2026
# Description: Package field/set desired state separately from immutable source provenance.
# Purpose: Generate API-mediated immutable catalogue synchronisation batches.
# Usage: python3 plugins/orac_chess/tools/generate_catalogue_sync.py --check

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'seed/catalogue/2026_11_10_comprehensive_catalogue/catalogue.json'
OUTPUT = ROOT / 'db/schema/seed_data/chess_batch_2026_11_10_comprehensive_catalogue.sql'


def normalise(source: dict) -> dict:
    """Build ordered desired fields and canonical relationship sets with semantic hashes.

    Args:
        source: Reproducible comprehensive generator output.

    Returns:
        Dependency-ordered private sync payload, independent of source provenance.

    Raises:
        ValueError: If dependencies are missing or form a cycle.
    """
    entries = []
    openings = {r['name']: r for r in source['openings']}
    gambits = {r['name']: r for r in source['gambits']}
    owner_keys = {(kind, name): row['source_key'] for kind, rows in
                  [('OPENING', openings), ('GAMBIT', gambits)] for name, row in rows.items()}
    root_keys = {key: value + '__main' for key, value in owner_keys.items()}

    def clean(value: object) -> object:
        return None if value == '' else value

    def entry(key: str, kind: str, fields: dict, relationships: dict) -> dict:
        desired = {'fields': {k: clean(v) for k, v in fields.items()},
                   'relationships': {k: sorted(set(v)) for k, v in relationships.items()}}
        digest = hashlib.sha256(json.dumps(desired, ensure_ascii=False, sort_keys=True,
                                          separators=(',', ':')).encode()).hexdigest()
        return {'key': key, 'kind': kind, 'source_hash': digest, 'desired': desired}

    visiting = set()
    done = set()

    def opening(name: str) -> None:
        if name in done:
            return
        if name in visiting or name not in openings:
            raise ValueError(f'Unknown/cyclic opening parent: {name}')
        visiting.add(name)
        row = openings[name]
        parent = row.get('parent_opening_name')
        if parent:
            opening(parent)
        entries.append(entry(row['source_key'], 'OPENING',
                             {k: row[k] for k in ('name', 'description', 'opening_type')} |
                             ({'strategy': row['strategy']} if 'strategy' in row else {}) |
                             {'parent_key': owner_keys['OPENING', parent] if parent else None},
                             {k: row.get(k, []) for k in ('eco_codes', 'aliases')}))
        visiting.remove(name)
        done.add(name)

    for name in sorted(openings):
        opening(name)
    extra_links = {}
    for link in source.get('opening_gambits', []):
        extra_links.setdefault(link['gambit_name'], set()).add(link['opening_name'])
    for name, row in sorted(gambits.items()):
        names = set(row.get('opening_names', [])) | extra_links.get(name, set())
        entries.append(entry(row['source_key'], 'GAMBIT', {k: row[k] for k in ('name', 'description')} |
                             ({'strategy': row['strategy']} if 'strategy' in row else {}),
                             {'eco_codes': row.get('eco_codes', []),
                              'opening_keys': [owner_keys['OPENING', n] for n in sorted(names)]}))
    for kind, rows in [('OPENING', openings), ('GAMBIT', gambits)]:
        for name, row in sorted(rows.items()):
            if row.get('mainline_pgn'):
                entries.append(entry(root_keys[kind, name], 'VARIATION',
                    {'name': row['mainline_name'], 'annotation': row.get('mainline_annotation'),
                     'pgn': row['mainline_pgn'], 'line_kind': 'MAIN', 'branch_ply': None,
                     'starting_fen': row.get('starting_fen'), 'owner_kind': kind,
                     'owner_key': owner_keys[kind, name], 'parent_key': None},
                    {'eco_codes': row.get('mainline_eco_codes', [])}))
    branches = {r['key']: r for r in source['variations']}
    visiting.clear()
    done.clear()

    def branch(key: str) -> None:
        if key in done:
            return
        if key in visiting or key not in branches:
            raise ValueError(f'Unknown/cyclic variation parent: {key}')
        visiting.add(key)
        row = branches[key]
        owner = row['owner_type'], row['owner_name']
        parent = row['parent_key']
        if parent == 'owner-mainline':
            parent = root_keys[owner]
        else:
            branch(parent)
        entries.append(entry(row['source_key'], 'VARIATION',
                    {'name': row['name'], 'annotation': row['annotation'], 'pgn': row['pgn'],
                     'line_kind': row['line_kind'], 'branch_ply': row['branch_ply'],
                     'starting_fen': None, 'owner_kind': owner[0], 'owner_key': owner_keys[owner],
                     'parent_key': parent}, {'eco_codes': row.get('eco_codes', [])}))
        visiting.remove(key)
        done.add(key)

    for key in sorted(branches):
        branch(key)
    keys = [e['key'] for e in entries]
    if len(keys) != len(set(keys)) or any(len(key) > 100 for key in keys):
        raise ValueError('Duplicate/oversized stable catalogue key')
    return {'source_revision': source['source_revision'], 'entries': entries}


def generate(source: dict, release_id: str = '2026_11_10_comprehensive',
             release_date: str = '11-Nov-2026') -> str:
    """Render a once-only changeset invoking the owner-only shared sync API.

    Args:
        source: Complete catalogue with optional strategy desired fields.
        release_id: Stable changeset suffix; the historical default is preserved.
        release_date: Provenance date rendered in the immutable SQL batch.

    Returns:
        Deterministic SQL for one owner-only catalogue application.
    """
    payload = json.dumps(normalise(source), ensure_ascii=False, separators=(',', ':'))
    encoded = payload.encode('utf-8')
    chunks = []
    start = 0
    while start < len(encoded):
        end = min(start + 1600, len(encoded))
        while end < len(encoded) and encoded[end] & 0xC0 == 0x80:
            end -= 1
        chunks.append(encoded[start:end].hex())
        start = end
    assignments = ''.join("  append_payload('" + chunk + "');\n" for chunk in chunks)
    template = '''--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 11-Nov-2026
-- Description: Source-managed comprehensive catalogue desired state.
-- Purpose: Apply additions and safe three-way changes through private catalogue/public domain APIs.
-- Usage: Managed plugin deployment; regenerate with tools/generate_catalogue_sync.py.
--changeset clive:orac_chess_catalogue_2026_11_10_comprehensive context:plugin,prod labels:plugin stripComments:false endDelimiter:/
declare
  l_payload clob;
  l_report clob;
  procedure append_payload(p_hex varchar2) is
    l_text varchar2(32767);
  begin
    l_text:=utl_i18n.raw_to_char(hextoraw(p_hex),'AL32UTF8');
    dbms_lob.writeappend(l_payload,length2(l_text),l_text);
  end;
  procedure release_clob(p_value in out nocopy clob) is
  begin
    if dbms_lob.istemporary(p_value)=1 then dbms_lob.freetemporary(p_value); end if;
    p_value:=null;
  end;
begin
  dbms_lob.createtemporary(l_payload,true);
''' + assignments + '''  orac_chess.chess_catalogue_api.apply_catalogue(l_payload,l_report);
  for i in 0..ceil(dbms_lob.getlength(l_report)/4000)-1 loop
    dbms_output.put_line(dbms_lob.substr(l_report,4000,i*4000+1));
  end loop;
  release_clob(l_payload);
  release_clob(l_report);
exception when others then
  release_clob(l_payload);
  release_clob(l_report);
  raise;
end;
/
-- Data, source baselines and user overrides survive release rollback.
--rollback empty
'''
    return template.replace('11-Nov-2026', release_date).replace(
        'orac_chess_catalogue_2026_11_10_comprehensive ',
        'orac_chess_catalogue_' + release_id + ' ')


def main() -> None:
    """Write/check a reproducible immutable sync batch and its reviewable payload."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--release-id', default='2026_11_10_comprehensive')
    parser.add_argument('--release-date', default='11-Nov-2026')
    args = parser.parse_args()
    source = json.loads(args.source.read_text())
    sql = generate(source, args.release_id, args.release_date)
    normalised = args.source.with_name('sync_payload.json')
    payload = json.dumps(normalise(source), ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    for path, text in [(args.output, sql), (normalised, payload)]:
        if args.check:
            if not path.exists() or path.read_text() != text:
                raise SystemExit(f'Stale generated catalogue artifact: {path}')
        else:
            path.write_text(text)


if __name__ == '__main__':
    main()
