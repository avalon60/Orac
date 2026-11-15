"""Refresh portable Chess reference, catalogue and video seeds from approved data."""
# Author: Clive Bostock
# Date: 14-Nov-2026
# Description: Capture coherent read-only Chess data and render current seed files.
# Purpose: Preserve APEX-maintained instructional data in repeatable installation seeds.
# Usage: python plugins/orac_chess/tools/refresh_seeds.py --from-snapshot snapshot.json

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SEEDS = ROOT / 'db/schema/seed_data'
SNAPSHOT = ROOT / 'seed/current.json'
COLUMNS = {
    'chess_content_source_v': 'creator,author,notes',
    'chess_eco_code_v': 'eco_code,description',
    'chess_opening_v': 'opening_id,name,opening_type,description,strategy,parent_opening_id',
    'chess_gambit_v': 'gambit_id,name,description,strategy',
    'chess_variation_v': 'variation_id,opening_id,gambit_id,parent_variation_id,branch_ply,name,line_kind,pgn,starting_fen,annotation',
    'chess_video_v': 'video_id,platform,external_video_id,video_url,title,creator,description,duration_seconds,published_on',
    'chess_opening_alias_v': 'opening_id,alias_name',
    'chess_opening_eco_v': 'opening_id,eco_code',
    'chess_gambit_eco_v': 'gambit_id,eco_code',
    'chess_variation_eco_v': 'variation_id,eco_code',
    'chess_opening_gambit_v': 'opening_id,gambit_id',
    'chess_video_opening_v': 'video_id,opening_id',
    'chess_video_gambit_v': 'video_id,gambit_id',
    'chess_video_variation_v': 'video_id,variation_id',
}


def capture(connection: Any, *, ledger: bool = False) -> dict:
    """Read allowlisted fields in one read-only transaction, always rolling back.

    Args:
        connection: An explicitly authorised python-oracledb connection.
        ledger: Read private stable identity columns using owner authority.

    Returns:
        Internal rows for conversion; surrogate identities are never published.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute('set transaction read only')
            result = {}
            queries = dict(COLUMNS)
            if ledger:
                queries['chess_catalogue_entry'] = ('catalogue_key,entity_kind,opening_id,'
                                                   'gambit_id,variation_id')
            for view, columns in queries.items():
                cursor.execute(f'select {columns} from orac_chess.{view}')
                names = columns.split(',')
                rows = []
                for values in cursor:
                    row = {}
                    for key, value in zip(names, values):
                        if hasattr(value, 'read'):
                            value = value.read()
                        elif hasattr(value, 'isoformat'):
                            value = value.isoformat()
                        row[key] = value
                    rows.append(row)
                result[view] = rows
            return result
    finally:
        connection.rollback()
        connection.close()


def sqlcl_capture_script(expected_user: str, expected_container: str) -> str:
    """Build an allowlisted read-only SQLcl script with explicit target verification."""
    for value in (expected_user, expected_container):
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_$#]{0,127}', value):
            raise ValueError('Expected user/container must be an ordinary Oracle identifier')
    expected_user, expected_container = expected_user.upper(), expected_container.upper()
    script = f"""whenever sqlerror exit failure rollback
set define off
set serveroutput on size unlimited
set feedback off
set heading off
set pagesize 0
set linesize 32767
begin
  if user <> '{expected_user}' or sys_context('USERENV','CON_NAME') <> '{expected_container}' then
    raise_application_error(-20000,'Unexpected seed capture target');
  end if;
  dbms_output.put_line('SEED_TARGET:{expected_user}|{expected_container}');
end;
/
set transaction read only;
"""
    for view, columns in COLUMNS.items():
        fields = []
        for column in columns.split(','):
            expression = f"to_char({column},'YYYY-MM-DD\"T\"HH24:MI:SS')" if column == 'published_on' else column
            fields.append(f"'{column}' value {expression}")
        projection = ','.join(fields)
        script += f"""declare
  l_json clob;
  l_piece varchar2(32767);
  l_offset pls_integer := 1;
begin
  dbms_output.enable(null);
  select coalesce(json_arrayagg(json_object({projection} returning clob) returning clob),to_clob('[]'))
    into l_json from orac_chess.{view};
  dbms_output.put_line('SEED_BEGIN:{view}');
  while l_offset <= dbms_lob.getlength(l_json) loop
    l_piece := dbms_lob.substr(l_json,1000,l_offset);
    dbms_output.put_line('SEED_HEX:' || rawtohex(utl_i18n.string_to_raw(l_piece,'AL32UTF8')));
    l_offset := l_offset + length2(l_piece);
  end loop;
  dbms_output.put_line('SEED_END');
  if dbms_lob.istemporary(l_json)=1 then dbms_lob.freetemporary(l_json); end if;
end;
/
"""
    return script + 'rollback;\nprompt SEED_COMPLETE\nexit\n'


def parse_sqlcl_capture(output: str, expected_user: str, expected_container: str) -> dict:
    """Decode complete SQLcl capture markers; reject missing, duplicate or partial views."""
    target = f'SEED_TARGET:{expected_user.upper()}|{expected_container.upper()}'
    if output.splitlines().count('SEED_COMPLETE') != 1:
        raise ValueError('SQLcl capture did not complete; no seed files written')
    if output.splitlines().count(target) != 1:
        raise ValueError('SQLcl did not verify the requested user/container')
    result, current, chunks = {}, None, []
    for line in output.splitlines():
        if line.startswith('SEED_BEGIN:'):
            current_view = line.removeprefix('SEED_BEGIN:')
            if current is not None or current_view not in COLUMNS or current_view in result:
                raise ValueError('Unexpected or duplicate SQLcl capture view')
            current, chunks = current_view, []
        elif line.startswith('SEED_HEX:'):
            if current is None:
                raise ValueError('SQLcl data arrived outside a view')
            chunks.append(bytes.fromhex(line.removeprefix('SEED_HEX:')))
        elif line == 'SEED_END':
            if current is None:
                raise ValueError('Unexpected SQLcl end marker')
            result[current] = json.loads(b''.join(chunks).decode('utf-8'))
            if not isinstance(result[current], list):
                raise ValueError('SQLcl capture did not return a row array')
            current = None
    if current is not None or set(result) != set(COLUMNS):
        raise ValueError('SQLcl capture incomplete; no seed files written')
    return result


def capture_sqlcl(alias: str, expected_user: str, expected_container: str) -> dict:
    """Capture an explicitly authorised saved SQLcl connection without extracting secrets."""
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', alias):
        raise ValueError('Invalid saved SQLcl connection name')
    if expected_user.upper() in ('SYS', 'SYSTEM'):
        raise ValueError('Use an explicitly approved Chess reader, not an administrator')
    script = sqlcl_capture_script(expected_user, expected_container)
    with tempfile.TemporaryDirectory(prefix='orac-chess-seeds-') as directory:
        path = Path(directory) / 'capture.sql'
        path.write_text(script, encoding='utf-8')
        try:
            process = subprocess.run(['sql', '-s', '-name', alias, '@' + str(path)],
                capture_output=True, text=True, encoding='utf-8', check=False, timeout=180)
        except subprocess.TimeoutExpired as exc:
            raise ValueError('Read-only SQLcl capture timed out; no seed files written') from exc
        if process.returncode:
            raise ValueError(f'Read-only SQLcl capture failed (exit {process.returncode}); no seed files written')
        result = parse_sqlcl_capture(process.stdout, expected_user, expected_container)
    print(f'Captured read-only {expected_user.upper()} in {expected_container.upper()} via {alias}', flush=True)
    return result


def digest(value: Any) -> str:
    """Return a deterministic hash of JSON data without changing text whitespace."""
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def portable(raw: dict, previous: dict | None = None) -> dict:
    """Resolve database relationships to portable keys and reject incomplete graphs."""
    previous = previous or {}
    old = {(e['kind'], ((e['desired']['fields'].get('owner_key') + ':') if e['kind'] == 'VARIATION' else '') + e['desired']['fields']['name']): e['key']
           for e in previous.get('catalogue', {}).get('entries', [])}
    identities = {}
    for row in raw.get('chess_catalogue_entry', raw.get('catalogue_keys', [])):
        kind = row['entity_kind']
        identity = row.get(kind.lower() + '_id')
        if identity is not None:
            identities[kind, identity] = row['catalogue_key']
    maps = {}
    entries = []
    for kind in ('OPENING', 'GAMBIT', 'VARIATION'):
        rows = raw['chess_' + kind.lower() + '_v']
        ids = {}
        for row in rows:
            identity = row[kind.lower() + '_id']
            if identity is None:
                raise ValueError(f'Missing {kind} identity')
            if identity in ids:
                raise ValueError(f'Duplicate {kind} identity')
            natural = row['name']
            if kind == 'VARIATION':
                if (row['opening_id'] is None) == (row['gambit_id'] is None):
                    raise ValueError('Variation must have exactly one owner')
                owner_kind = 'OPENING' if row['opening_id'] is not None else 'GAMBIT'
                owner_id = row[owner_kind.lower() + '_id']
                natural = maps[owner_kind][owner_id] + ':' + natural
            key = identities.get((kind, identity)) or old.get((kind, natural))
            key = key or kind.lower() + '_' + digest(natural)[:32]
            ids[identity] = key
        maps[kind] = ids
    def resolve(kind: str, identity: Any) -> str | None:
        if identity is None:
            return None
        if identity not in maps[kind]:
            raise ValueError(f'Dangling {kind} relationship: {identity}')
        return maps[kind][identity]
    for view, columns in COLUMNS.items():
        if view in ('chess_content_source_v', 'chess_eco_code_v', 'chess_video_v'):
            continue
        for row in raw[view]:
            for kind in ('OPENING', 'GAMBIT', 'VARIATION'):
                column = kind.lower() + '_id'
                if column in row:
                    resolve(kind, row[column])
            if 'video_id' in row and row['video_id'] not in {v['video_id'] for v in raw['chess_video_v']}:
                raise ValueError('Dangling video relationship')
    def links(view: str, id_column: str, identity: Any, value: str) -> list:
        return [r[value] for r in raw[view] if r[id_column] == identity]
    for kind in ('OPENING', 'GAMBIT', 'VARIATION'):
        id_column = kind.lower() + '_id'
        for row in raw['chess_' + kind.lower() + '_v']:
            identity = row[id_column]
            fields = {'name': row['name']}
            relationships = {'eco_codes': links('chess_' + kind.lower() + '_eco_v', id_column, identity, 'eco_code')}
            if kind in ('OPENING', 'GAMBIT'):
                fields.update({k: row.get(k) for k in ('description', 'strategy')})
            if kind == 'OPENING':
                fields.update(opening_type=row['opening_type'], parent_key=resolve(kind, row['parent_opening_id']))
                relationships['aliases'] = links('chess_opening_alias_v', id_column, identity, 'alias_name')
            elif kind == 'GAMBIT':
                relationships['opening_keys'] = [resolve('OPENING', i) for i in links('chess_opening_gambit_v', id_column, identity, 'opening_id')]
            else:
                owner_kind = 'OPENING' if row['opening_id'] is not None else 'GAMBIT'
                fields.update({k: row.get(k) for k in ('annotation', 'pgn', 'line_kind', 'branch_ply', 'starting_fen')})
                fields.update(owner_kind=owner_kind, owner_key=resolve(owner_kind, row[owner_kind.lower() + '_id']), parent_key=resolve(kind, row['parent_variation_id']))
            desired = {'fields': fields, 'relationships': {k: sorted(set(v)) for k, v in relationships.items()}}
            entries.append({'key': maps[kind][identity], 'kind': kind, 'source_hash': digest(desired), 'desired': desired})
    videos = []
    for row in raw['chess_video_v']:
        video = {k: row[k] for k in COLUMNS['chess_video_v'].split(',') if k != 'video_id'}
        for kind in ('OPENING', 'GAMBIT', 'VARIATION'):
            video[kind.lower() + '_keys'] = sorted(set(resolve(kind, i) for i in links('chess_video_' + kind.lower() + '_v', 'video_id', row['video_id'], kind.lower() + '_id')))
        videos.append(video)
    result = {'format': 1, 'content_sources': raw['chess_content_source_v'],
              'eco_codes': raw['chess_eco_code_v'], 'catalogue': {'entries': entries}, 'videos': videos}
    return validate(result)


def validate(snapshot: dict) -> dict:
    """Validate portable references, uniqueness and cycles and canonicalise ordering."""
    def scalar(value: Any, label: str, limit: int, required: bool = False) -> None:
        if value is None and not required:
            return
        if not isinstance(value, str) or (required and not value) or len(value) > limit or '\x00' in value:
            raise ValueError(f'Invalid {label}')
    if snapshot.get('format') != 1:
        raise ValueError('Unsupported snapshot format')
    entries = snapshot['catalogue']['entries']
    by_key = {e['key']: e for e in entries}
    if len(by_key) != len(entries) or any(len(k) > 100 for k in by_key):
        raise ValueError('Duplicate or oversized catalogue key')
    natural = [(e['kind'], e['desired']['fields'].get('owner_key'), e['desired']['fields']['name']) for e in entries]
    if len(set(natural)) != len(natural):
        raise ValueError('Duplicate entity name within owner')
    done, visiting, ordered = set(), set(), []
    def visit(key: str) -> None:
        if key in done:
            return
        if key in visiting or key not in by_key:
            raise ValueError(f'Unknown or cyclic catalogue dependency: {key}')
        visiting.add(key)
        entry = by_key[key]
        if entry['kind'] not in ('OPENING', 'GAMBIT', 'VARIATION'):
            raise ValueError('Unsupported catalogue entity kind')
        desired = entry['desired']
        fields = desired['fields']
        scalar(fields['name'], 'entity name', 200, True)
        dependencies = [fields.get('parent_key'), fields.get('owner_key')]
        dependencies += desired['relationships'].get('opening_keys', [])
        parent = fields.get('parent_key')
        owner = fields.get('owner_key')
        if parent and parent in by_key and by_key[parent]['kind'] != entry['kind']:
            raise ValueError('Parent entity kind mismatch')
        if owner and (owner not in by_key or by_key[owner]['kind'] != fields['owner_kind']):
            raise ValueError('Invalid variation owner')
        if entry['kind'] == 'VARIATION':
            if fields['line_kind'] not in ('MAIN', 'ALTERNATIVE', 'CONTINUATION'):
                raise ValueError('Invalid variation line kind')
            if parent in by_key and by_key[parent]['desired']['fields'].get('owner_key') != owner:
                raise ValueError('Variation parent belongs to another owner')
        for linked in desired['relationships'].get('opening_keys', []):
            if linked not in by_key or by_key[linked]['kind'] != 'OPENING':
                raise ValueError('Invalid gambit opening relationship')
        for dep in dependencies:
            if dep:
                visit(dep)
        entry['source_hash'] = digest(desired)
        visiting.remove(key)
        done.add(key)
        ordered.append(entry)
    for key in sorted(by_key, key=lambda k: ({'OPENING': 0, 'GAMBIT': 1, 'VARIATION': 2}.get(by_key[k]['kind'], 3), k)):
        visit(key)
    snapshot['catalogue'] = {'source_revision': digest(ordered), 'entries': ordered}
    for collection, key in [('content_sources', 'creator'), ('eco_codes', 'eco_code')]:
        rows = snapshot[collection]
        if len({r[key] for r in rows}) != len(rows):
            raise ValueError(f'Duplicate {collection} identity')
        for row in rows:
            scalar(row[key], collection + ' identity', 300 if key == 'creator' else 3, True)
            if key == 'creator':
                scalar(row.get('author'), 'publisher author', 300)
                scalar(row.get('notes'), 'publisher notes', 16777216)
            elif len(row[key]) != 3 or row[key][0] not in 'ABCDE' or not row[key][1:].isdigit():
                raise ValueError('Invalid ECO code')
            else:
                scalar(row.get('description'), 'ECO description', 16777216, True)
        snapshot[collection] = sorted(rows, key=lambda r: r[key])
    eco_codes = {r['eco_code'] for r in snapshot['eco_codes']}
    for entry in entries:
        if not set(entry['desired']['relationships'].get('eco_codes', [])) <= eco_codes:
            raise ValueError('Unknown ECO relationship')
    creators = {r['creator'] for r in snapshot['content_sources']}
    mains = [e['desired']['fields']['owner_key'] for e in entries if e['kind'] == 'VARIATION' and e['desired']['fields']['line_kind'] == 'MAIN']
    if len(set(mains)) != len(mains):
        raise ValueError('Duplicate owner mainline')
    video_ids = set()
    for video in snapshot['videos']:
        for key, limit in [('platform', 50), ('external_video_id', 255), ('video_url', 2048), ('title', 500)]:
            scalar(video.get(key), 'video ' + key, limit, True)
        if video.get('published_on'):
            parsed_date = datetime.fromisoformat(video['published_on'])
            if parsed_date.tzinfo is not None:
                raise ValueError('Publication DATE must not contain a timezone')
            video['published_on'] = parsed_date.isoformat(timespec='seconds')
        if video.get('creator') and video['creator'] not in creators:
            raise ValueError('Video creator missing from content sources')
        identity = video['platform'], video['external_video_id']
        if identity in video_ids:
            raise ValueError('Duplicate video identity')
        video_ids.add(identity)
        for kind in ('opening', 'gambit', 'variation'):
            for key in video[kind + '_keys']:
                if key not in by_key or by_key[key]['kind'] != kind.upper():
                    raise ValueError(f'Invalid video {kind} reference: {key}')
    snapshot['videos'] = sorted(snapshot['videos'], key=lambda r: (r['platform'], r['external_video_id']))
    return snapshot


def sql_block(name: str, payload: Any, declarations: str, body: str) -> str:
    """Render one runOnChange changeset with UTF-8-safe unbounded CLOB input."""
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    chunks = []
    start = 0
    while start < len(encoded):
        end = min(start + 1600, len(encoded))
        while end < len(encoded) and encoded[end] & 0xC0 == 0x80:
            end -= 1
        chunks.append(encoded[start:end].hex())
        start = end
    assignments = ''.join(f"  append_payload('{chunk}');\n" for chunk in chunks)
    return f'''--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 14-Nov-2026
-- Description: Current portable Chess {name} seed; generated by refresh_seeds.py.
-- Purpose: Refresh desired data without deleting omitted records.
-- Usage: Managed plugin deployment; refresh with tools/refresh_seeds.py.
--changeset clive:orac_chess_current_{name}_2026_11_14 context:plugin,prod labels:plugin runOnChange:true stripComments:false endDelimiter:/
declare
  l_payload clob;
{declarations}
  procedure append_payload(p_hex varchar2) is
    l_text varchar2(32767);
  begin
    l_text := utl_i18n.raw_to_char(hextoraw(p_hex),'AL32UTF8');
    dbms_lob.writeappend(l_payload,length2(l_text),l_text);
  end;
begin
  dbms_lob.createtemporary(l_payload,true);
{assignments}{body}
  dbms_lob.freetemporary(l_payload);
exception when others then
  if dbms_lob.istemporary(l_payload)=1 then dbms_lob.freetemporary(l_payload); end if;
  raise;
end;
/
-- Retain reference data and user changes on rollback.
--rollback empty
'''


def reference_sql(name: str, rows: list) -> str:
    """Render insert/update MERGEs that only advance audit values on real changes."""
    source = name == 'content_source'
    key = 'creator' if source else 'eco_code'
    value = 'notes' if source else 'description'
    author_column = ', author varchar2(1200) path \'$.author\'' if source else ''
    author_select = ', r.author author' if source else ''
    author_update = 't.author=s.author, ' if source else ''
    author_diff = 'decode(t.author,s.author,0,1)=1 or ' if source else ''
    author_insert = ',author' if source else ''
    author_values = ',s.author' if source else ''
    audit_update = 't.updated_on=systimestamp,t.row_version=t.row_version+1,' if source else ''
    body = f'''  for r in (select * from json_table(l_payload,'$[*]' columns (
    {key} varchar2(1200) path '$.{key}'{author_column},
    {value} clob path '$.{value}' null on empty))) loop
    merge into orac_chess.chess_{name} t
    using (select r.{key} {key}{author_select},r.{value} {value} from dual) s
    on (t.{key}=s.{key})
    when matched then update set {audit_update}{author_update}t.{value}=s.{value}
      where {author_diff}(t.{value} is null and s.{value} is not null)
        or (t.{value} is not null and s.{value} is null)
        or dbms_lob.compare(t.{value},s.{value})<>0
    when not matched then insert ({key}{author_insert},{value})
      values (s.{key}{author_values},s.{value});
  end loop;'''
    return sql_block(name, rows, '', body)


def videos_sql(videos: list) -> str:
    """Render API-mediated missing videos and additive links, preserving existing values."""
    declarations = '''  l_rows json_array_t;
  l_row json_object_t;
  l_links json_array_t;
  l_id number;
  l_version number;
  l_new_version number;
  l_target number;
  l_description clob;
  l_platform varchar2(50);
  l_external varchar2(255);
  l_key varchar2(100);
  function text_value(p_name varchar2) return varchar2 is
  begin
    return l_row.get_string(p_name);
  end;
'''
    body = '''  l_rows := json_array_t.parse(l_payload);
  for i in 0..l_rows.get_size-1 loop
    l_row := treat(l_rows.get(i) as json_object_t);
    l_platform := text_value('platform');
    l_external := text_value('external_video_id');
    begin
      select video_id,row_version into l_id,l_version from orac_chess.chess_video_v
      where platform=l_platform and external_video_id=l_external;
    exception when no_data_found then
      l_id := null;
      l_description := l_row.get_clob('description');
      orac_chess.chess_admin_api.save_video(l_id,null,text_value('platform'),
        text_value('external_video_id'),text_value('video_url'),text_value('title'),
        text_value('creator'),l_description,l_row.get_number('duration_seconds'),
        to_date(text_value('published_on'),'YYYY-MM-DD"T"HH24:MI:SS'),l_version);
      if dbms_lob.istemporary(l_description)=1 then dbms_lob.freetemporary(l_description); end if;
    end;
'''
    for kind in ('opening', 'gambit', 'variation'):
        body += f'''    l_links := l_row.get_array('{kind}_keys');
    for j in 0..l_links.get_size-1 loop
      l_key := l_links.get_string(j);
      select max({kind}_id) into l_target from orac_chess.chess_catalogue_entry
      where catalogue_key=l_key and entity_kind='{kind.upper()}';
      if l_target is not null then
        declare l_count number;
        begin
          select count(*) into l_count from orac_chess.chess_video_{kind}_v
          where video_id=l_id and {kind}_id=l_target;
          if l_count=0 then
            orac_chess.chess_admin_api.link_video_{kind}(l_id,l_target,l_version,true,l_new_version);
            l_version := l_new_version;
          end if;
        end;
      end if;
    end loop;
'''
    body += '  end loop;'
    return sql_block('video', videos, declarations, body).replace(
        'exception when others then\n',
        'exception when others then\n  if dbms_lob.istemporary(l_description)=1 then dbms_lob.freetemporary(l_description); end if;\n')


def render(snapshot: dict) -> dict[Path, tuple[str, str]]:
    """Validate and render every output before permitting any file writes."""
    snapshot = validate(snapshot)
    catalogue = sql_block('catalogue', snapshot['catalogue'], '  l_report clob;',
                          '  orac_chess.chess_catalogue_api.apply_catalogue(l_payload,l_report);\n'
                          '  for i in 0..ceil(dbms_lob.getlength(l_report)/4000)-1 loop\n'
                          '    dbms_output.put_line(dbms_lob.substr(l_report,4000,i*4000+1));\n'
                          '  end loop;\n'
                          '  if dbms_lob.istemporary(l_report)=1 then dbms_lob.freetemporary(l_report); end if;')
    catalogue = catalogue.replace('exception when others then\n',
        'exception when others then\n  if dbms_lob.istemporary(l_report)=1 then dbms_lob.freetemporary(l_report); end if;\n')
    entries = snapshot['catalogue']['entries']
    counts = ', '.join(f"{sum(e['kind'] == kind for e in entries)} {kind.lower()}s" for kind in ('OPENING', 'GAMBIT', 'VARIATION'))
    sources = reference_sql('content_source', snapshot['content_sources'])
    # Preserve the user's already introduced current content-source changeset identity.
    sources = sources.replace('orac_chess_current_content_source_2026_11_14', 'orac_chess_content_source_catalogue_2026_11_14')
    video_links = ', '.join(f"{sum(len(v[kind + '_keys']) for v in snapshot['videos'])} {kind} links" for kind in ('opening', 'gambit', 'variation'))
    return {
        SEEDS / 'chess_content_source.sql': (sources, f"{len(snapshot['content_sources'])} content publishers (creator, author, notes)"),
        SEEDS / 'chess_eco_code.sql': (reference_sql('eco_code', snapshot['eco_codes']), f"{len(snapshot['eco_codes'])} ECO descriptions"),
        SEEDS / 'chess_catalogue.sql': (catalogue, counts + ' and their aliases/ECO/owner/parent relationships'),
        SEEDS / 'chess_video.sql': (videos_sql(snapshot['videos']), f"{len(snapshot['videos'])} videos, {video_links}"),
    }


def write_outputs(outputs: dict[Path, tuple[str, str]], *, check: bool = False) -> bool:
    """Write rendered files with a description at each write, or check without writes."""
    changed = False
    originals = {}
    staged = {}
    replaced = []
    try:
        for path, (content, description) in outputs.items():
            original = path.read_bytes() if path.exists() else None
            differs = original != content.encode('utf-8')
            changed |= differs
            if check:
                print(f"{'STALE' if differs else 'OK'} {description}: {path}")
            else:
                originals[path] = original
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix(path.suffix + '.tmp')
                staged[path] = temporary
                temporary.write_text(content, encoding='utf-8')
        if not check:
            for path, (_, description) in outputs.items():
                print(f'Writing {description}: {path}', flush=True)
                staged[path].replace(path)
                replaced.append(path)
        return changed
    except OSError:
        # A staging failure changes no target. Restore targets if a replacement fails.
        for path in reversed(replaced):
            if originals[path] is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(originals[path])
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)



def main() -> None:
    """Capture an authorised connection or replay a portable snapshot and refresh seeds."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-snapshot', type=Path)
    parser.add_argument('--snapshot', type=Path, default=SNAPSHOT)
    parser.add_argument('--sqlcl-connection', help='Explicitly authorised saved SQLcl connection; no fallback')
    parser.add_argument('--expected-user')
    parser.add_argument('--expected-container')
    parser.add_argument('--dsn')
    parser.add_argument('--user')
    parser.add_argument('--password-env', default='ORAC_CHESS_SEED_PASSWORD')
    parser.add_argument('--ledger', action='store_true', help='Read owner-only stable identity columns; requires explicit owner authority')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        if args.from_snapshot:
            if args.dsn or args.user or args.ledger or args.sqlcl_connection or args.expected_user or args.expected_container:
                parser.error('Snapshot replay cannot also select a live connection')
            snapshot = json.loads(args.from_snapshot.read_text(encoding='utf-8'))
        elif args.sqlcl_connection:
            if args.dsn or args.user or args.ledger:
                parser.error('SQLcl capture cannot also select direct credentials or private ledger access')
            if not args.expected_user or not args.expected_container:
                parser.error('SQLcl capture requires --expected-user and --expected-container')
            previous = json.loads(args.snapshot.read_text(encoding='utf-8')) if args.snapshot.exists() else None
            snapshot = portable(capture_sqlcl(args.sqlcl_connection, args.expected_user, args.expected_container), previous)
            print('Public-view keys reused by owner/name; use authorised direct owner --ledger capture for renames.')
        else:
            if args.expected_user or args.expected_container:
                parser.error('Expected user/container apply only to --sqlcl-connection')
            if not args.dsn or not args.user:
                parser.error('Live capture requires explicit --dsn and --user (no administrator fallback)')
            if args.user.upper() in ('SYS', 'SYSTEM'):
                parser.error('Use the Chess owner or an explicitly approved read-only consumer')
            password = os.environ.get(args.password_env)
            if not password:
                parser.error(f'Missing password environment variable: {args.password_env}')
            import oracledb
            previous = json.loads(args.snapshot.read_text(encoding='utf-8')) if args.snapshot.exists() else None
            snapshot = portable(capture(oracledb.connect(user=args.user, password=password, dsn=args.dsn), ledger=args.ledger), previous)
            if not args.ledger:
                print('Stable keys recovered from prior snapshot names; use --ledger as authorised owner to preserve keys across renames.')
        outputs = render(snapshot)
        outputs[args.snapshot] = (json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2) + '\n', 'portable instructional snapshot (no database IDs or audit/ownership state)')
        stale = write_outputs(outputs, check=args.check)
        if args.check and stale:
            raise SystemExit(1)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, f'Seed refresh refused before writing: {exc}\n')


if __name__ == '__main__':
    main()
