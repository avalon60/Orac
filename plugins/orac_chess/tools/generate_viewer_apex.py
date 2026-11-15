"""Package local PGN viewer modules and read-only APEX page components."""

# Author: Clive Bostock
# Date: 14-Nov-2026
# Description: Generate deterministic static files and viewer regions for existing Chess pages.
# Purpose: Deliver browser-only chess replay without schema or authorisation changes.
# Usage: python3 plugins/orac_chess/tools/generate_viewer_apex.py --check

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / 'apex/orac_chess_admin.sql'
PAGES = (11, 21, 22, 31)


def sql_string(value: str) -> str:
    """Quote a SQL string literal."""
    return "'" + value.replace("'", "''") + "'"


def sql_lines(value: str) -> str:
    """Render a multiline PL/SQL or HTML source as an APEX string expression."""
    return 'wwv_flow_string.join(wwv_flow_t_varchar2(\n' + ',\n'.join(sql_string(line) for line in value.splitlines()) + '))'


def asset_sources() -> dict[str, bytes]:
    """Return the explicit source mapping, retaining all relative module imports."""
    files = [ROOT / 'browser' / name for name in ('model.mjs', 'viewer.mjs', 'apex.mjs', 'bootstrap.mjs', 'viewer.css', 'pieces.svg', 'PIECES-LICENSE')]
    files += [ROOT / 'tools/mle/validator.mjs', ROOT / 'vendor/chess.js-1.4.0/chess.mjs', ROOT / 'vendor/chess.js-1.4.0/LICENSE']
    vendor = ROOT / 'vendor/cm-chessboard-8.15.4'
    files += [p for p in vendor.rglob('*') if p.is_file() and p.suffix in ('.js', '.css', '.svg')]
    files += [vendor / 'LICENSE']
    return {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in sorted(files) if p.is_file() and p.name != 'fixture.html'}


def asset_prefix() -> str:
    """Address the complete module graph by content so imports never reuse stale code."""
    digest = hashlib.sha256()
    for name, data in asset_sources().items():
        digest.update(name.encode() + b'\0' + hashlib.sha256(data).digest())
    return f'pgn/{digest.hexdigest()[:16]}'


def assets() -> dict[str, bytes]:
    """Map immutable versioned URLs to the exact local resource bytes."""
    prefix = asset_prefix()
    return {f'{prefix}/{name}': data for name, data in asset_sources().items()}


def static_files() -> str:
    """Encode byte-identical browser resources as application static files."""
    output = []
    for index, (name, data) in enumerate(assets().items()):
        mime = {'.mjs': 'text/javascript', '.js': 'text/javascript', '.svg': 'image/svg+xml', '.css': 'text/css'}.get(Path(name).suffix, 'text/plain')
        output += ['begin', 'wwv_flow_imp.g_varchar2_table := wwv_flow_imp.empty_varchar2_table;']
        encoded = data.hex().upper()
        for chunk, start in enumerate(range(0, len(encoded), 2000), 1):
            output.append(f'wwv_flow_imp.g_varchar2_table({chunk}) := {sql_string(encoded[start:start + 2000])};')
        output += ['wwv_flow_imp_shared.create_app_static_file(', f' p_id=>wwv_flow_imp.id({98600000000000000 + index})', f',p_file_name=>{sql_string(name)}', f',p_mime_type=>{sql_string(mime)}', ",p_file_charset=>'utf-8'", ',p_file_content=>wwv_flow_imp.varchar2_to_blob(wwv_flow_imp.g_varchar2_table)', ');', 'end;', '/']
    return '\n'.join(output) + '\n'


def callback(page: int) -> str:
    """Render a bounded metadata and complete selected-PGN read callback."""
    item = f'P{page}_' + ('OPENING_ID' if page == 11 else 'VARIATION_ID' if page == 31 else 'GAMBIT_ID')
    ownership = f'v.opening_id=:{item}' if page == 11 else f'v.gambit_id=:{item}'
    if page == 11:
        ownership = f'({ownership} or v.gambit_id in (select gambit_id from orac_chess.chess_opening_gambit_v where opening_id=:{item}))'
    if page == 31:
        ownership = f'(v.variation_id=:{item} or (apex_application.g_x01=\'PARENT\' and ((v.opening_id=:P31_OPENING_ID and v.gambit_id is null) or (v.gambit_id=:P31_GAMBIT_ID and v.opening_id is null))))'
    return f"""declare
  l_id number;
  l_offset number := 0;
  l_root number;
  l_fen varchar2(4000);
  l_count pls_integer := 0;
  l_pgn clob;
  l_name varchar2(4000);
  l_parent number;
  l_kind varchar2(30);
  l_ply number;
begin
  if apex_application.g_x01 not in ('LIST','LINE','PARENT') then raise no_data_found; end if;
  if apex_application.g_x01 <> 'LIST' then
    if apex_application.g_x02 is null or not regexp_like(apex_application.g_x02,'^[1-9][0-9]{{0,17}}$') then raise no_data_found; end if;
    l_id := to_number(apex_application.g_x02);
  end if;
  if apex_application.g_x03 is not null then
    if not regexp_like(apex_application.g_x03,'^[0-9]{{1,7}}$') then raise no_data_found; end if;
    l_offset := to_number(apex_application.g_x03);
  end if;
  if apex_application.g_x01 = 'LIST' then
    apex_json.open_object;
    apex_json.open_array('lines');
    for r in (select v.variation_id,v.name,v.parent_variation_id,v.line_kind,v.branch_ply,p.name parent_name
      from orac_chess.chess_variation_v v left join orac_chess.chess_variation_v p on p.variation_id=v.parent_variation_id
      where {ownership}
      order by case when v.parent_variation_id is null then 0 else 1 end, v.parent_variation_id,v.name,v.variation_id
      offset l_offset rows fetch next 101 rows only) loop
      l_count := l_count+1;
      if l_count <= 100 then
        apex_json.open_object;
        apex_json.write('id',r.variation_id); apex_json.write('name',r.name);
        apex_json.write('parentId',r.parent_variation_id); apex_json.write('parentName',r.parent_name);
        apex_json.write('kind',r.line_kind); apex_json.write('branchPly',r.branch_ply);
        apex_json.close_object;
      end if;
    end loop;
    apex_json.close_array; apex_json.write('more',l_count>100); apex_json.close_object;
  else
    select v.name,v.pgn,v.parent_variation_id,v.line_kind,v.branch_ply
      into l_name,l_pgn,l_parent,l_kind,l_ply from orac_chess.chess_variation_v v
      where v.variation_id=l_id and {ownership};
    select variation_id,starting_fen into l_root,l_fen from orac_chess.chess_variation_v
      where parent_variation_id is null
      start with variation_id=l_id connect by nocycle prior parent_variation_id=variation_id;
    apex_json.open_object;
    apex_json.write('id',l_id); apex_json.write('name',l_name); apex_json.write('pgn',l_pgn);
    apex_json.write('parentId',l_parent); apex_json.write('kind',l_kind); apex_json.write('branchPly',l_ply);
    apex_json.write('rootId',l_root); apex_json.write('startingFen',l_fen);
    apex_json.close_object;
  end if;
exception when others then
  apex_json.open_object; apex_json.write('error','The requested variation is unavailable for this subject.'); apex_json.close_object;
end;"""


def subject_components(page: int) -> str:
    """Render persisted subject identity and a paginated, read-only variation list."""
    if page not in (11, 21):
        return ''
    subject = 'opening' if page == 11 else 'gambit'
    item = f'P{page}_{subject.upper()}_ID'
    summary = f"""declare
  l_name varchar2(4000);
begin
  if :{item} is null then
    return '<p>New {subject}</p>';
  end if;
  select name into l_name from orac_chess.chess_{subject}_v where {subject}_id=:{item};
  return '<p class="u-bold">' || apex_escape.html(l_name) || '</p>';
exception when no_data_found then
  return '<p>This {subject} is no longer available.</p>';
end;"""
    ownership = f'v.{subject}_id=:{item}'
    if page == 11:
        ownership = f'({ownership} or v.gambit_id in (select gambit_id from orac_chess.chess_opening_gambit_v where opening_id=:{item}))'
    query = f"""select v.variation_id,v.name,v.line_kind,p.name parent_name,v.branch_ply
from orac_chess.chess_variation_v v
left join orac_chess.chess_variation_v p on p.variation_id=v.parent_variation_id
where {ownership}
order by v.name,v.variation_id"""
    base = 98900000000000000 + page * 100
    result = f"""wwv_flow_imp_page.create_page_plug(
 p_id=>wwv_flow_imp.id({base})
,p_plug_name=>'Selected {subject}'
,p_region_name=>'selected_subject'
,p_plug_template=>4501440665235496320
,p_plug_display_sequence=>1
,p_plug_source=>{sql_lines(summary)}
,p_function_body_language=>'PLSQL'
,p_plug_source_type=>'NATIVE_DYNAMIC_CONTENT'
,p_attributes=>wwv_flow_t_plugin_attributes(wwv_flow_t_varchar2('expand_shortcuts','N','output_as','HTML','show_line_breaks','N')).to_clob
);
wwv_flow_imp_page.create_page_plug(
 p_id=>wwv_flow_imp.id({base + 1})
,p_plug_name=>'Variations'
,p_region_name=>'subject_variations'
,p_include_in_reg_disp_sel_yn=>'Y'
,p_plug_template=>4072358936313175081
,p_plug_display_sequence=>30
,p_query_type=>'SQL'
,p_plug_source=>{sql_lines(query)}
,p_plug_source_type=>'NATIVE_IR'
);
wwv_flow_imp_page.create_worksheet(
 p_id=>wwv_flow_imp.id({base + 2})
,p_name=>'Variations'
,p_base_pk1=>'VARIATION_ID'
,p_pagination_type=>'ROWS_X_TO_Y'
,p_pagination_display_pos=>'BOTTOM_RIGHT'
,p_lazy_loading=>false
,p_show_detail_link=>'N'
,p_owner=>'ORAC_ADMIN'
,p_internal_uid=>{base + 2}
);
"""
    columns = [('VARIATION_ID', 'Variation ID', 'NUMBER'), ('NAME', 'Name', 'STRING'),
               ('LINE_KIND', 'Line kind', 'STRING'), ('PARENT_NAME', 'Parent', 'STRING'),
               ('BRANCH_PLY', 'Branch ply', 'NUMBER')]
    for index, (name, label, kind) in enumerate(columns):
        hidden = ",p_display_text_as=>'HIDDEN_ESCAPE_SC'" if index == 0 else ",p_display_text_as=>'ESCAPE_SC'"
        link = (
            ",p_column_link=>'f?p=&APP_ID.:31:&APP_SESSION.::&DEBUG.:RP:P31_VARIATION_ID:#VARIATION_ID#'\n"
            ",p_column_linktext=>'#NAME#'\n"
            if page == 11 and name == 'NAME' else ''
        )
        result += f"""wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id({base + 3 + index})
,p_db_column_name=>'{name}'
,p_display_order=>{index + 1}
,p_column_identifier=>'{chr(65 + index)}'
,p_column_label=>'{label}'
,p_column_type=>'{kind}'
{hidden}
{link},p_use_as_row_header=>'N'
);
"""
    return result + f"""wwv_flow_imp_page.create_worksheet_rpt(
 p_id=>wwv_flow_imp.id({base + 8})
,p_application_user=>'APXWS_DEFAULT'
,p_report_seq=>10
,p_report_alias=>'{base + 8}'
,p_status=>'PUBLIC'
,p_is_default=>'Y'
,p_display_rows=>15
,p_report_columns=>'NAME:LINE_KIND:PARENT_NAME:BRANCH_PLY'
);
"""


def components(page: int) -> str:
    """Render an additive viewer region and its page-local read callback."""
    html = f'''<link rel="stylesheet" href="#APP_FILES#{asset_prefix()}/browser/viewer.css">
<div class="orac-pgn-explorer" data-orac-pgn data-page="{page}"></div>
<script type="module" src="#APP_FILES#{asset_prefix()}/browser/bootstrap.mjs"></script>'''
    membership = ",p_include_in_reg_disp_sel_yn=>'Y'\n" if page in (11, 21, 31) else ''
    selector = f"""wwv_flow_imp_page.create_page_plug(
 p_id=>wwv_flow_imp.id({97010000000000031 if page == 31 else 97000000000000000 + page})
,p_plug_name=>'View'
,p_region_template_options=>'#DEFAULT#:margin-bottom-md'
,p_escape_on_http_output=>'Y'
,p_plug_template=>4501440665235496320
,p_plug_display_sequence=>5
,p_plug_source_type=>'NATIVE_DISPLAY_SELECTOR'
,p_attributes=>wwv_flow_t_plugin_attributes(wwv_flow_t_varchar2('display_region_icons','N','include_show_all','N','rds_mode','STANDARD','remember_selection','N')).to_clob
);
""" if page in (21, 31) else ''
    return subject_components(page) + selector + f"""wwv_flow_imp_page.create_page_plug(
 p_id=>wwv_flow_imp.id({98700000000000000 + page})
,p_plug_name=>'PGN Viewer'
,p_region_name=>'pgn_viewer'
,p_plug_template=>4072358936313175081
,p_plug_display_sequence=>{9 if page == 31 else 10 if page in (11, 21) else 45}
{membership},p_plug_source=>{sql_lines(html)}
,p_plug_source_type=>'NATIVE_STATIC'
,p_attributes=>wwv_flow_t_plugin_attributes(wwv_flow_t_varchar2('expand_shortcuts','N','output_as','HTML','show_line_breaks','N')).to_clob
);
wwv_flow_imp_page.create_page_process(
 p_id=>wwv_flow_imp.id({98800000000000000 + page})
,p_process_sequence=>90
,p_process_point=>'ON_DEMAND'
,p_process_type=>'NATIVE_PLSQL'
,p_process_name=>'PGN_VIEWER'
,p_process_sql_clob=>{sql_lines(callback(page))}
,p_process_clob_language=>'PLSQL'
,p_error_display_location=>'INLINE_IN_NOTIFICATION'
);
"""


def replace_section(source: str, name: str, rendered: str, anchor: str) -> str:
    """Replace a marked generated section or initialise it at a unique anchor."""
    begin, end = f'-- BEGIN GENERATED PGN {name}\n', f'-- END GENERATED PGN {name}\n'
    if begin not in source:
        if source.count(anchor) != 1:
            raise ValueError(f'Nonunique viewer anchor: {name}')
        source = source.replace(anchor, begin + end + anchor, 1)
    if source.count(begin) != 1 or source.count(end) != 1:
        raise ValueError(f'Nonunique viewer section: {name}')
    before, rest = source.split(begin)
    _, after = rest.split(end)
    return before + begin + rendered + end + after


def generate(source: str) -> str:
    """Generate only marked viewer sections, preserving all existing page features."""
    source = replace_section(source, 'STATIC_FILES', static_files(), 'prompt --application/shared_components/user_interface/themes\n')
    for page in PAGES:
        anchor = f'prompt --application/pages/page_{page:05d}\n'
        start = source.index(anchor)
        next_page = source.index('prompt --application/pages/', start + len(anchor))
        section = source[start:next_page]
        # Add components immediately before the existing page block closes.
        close = section.rfind('end;\n/\n')
        section = replace_section(section, f'PAGE_{page}', components(page), section[close:])
        source = source[:start] + section + source[next_page:]
    return source


def main() -> int:
    """Check or update packaged APEX viewer components."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Fail if packaged resources are stale')
    args = parser.parse_args()
    source = EXPORT.read_text()
    generated = generate(source)
    if args.check:
        if generated != source:
            parser.exit(1, 'PGN viewer components are stale\n')
    elif generated != source:
        EXPORT.write_text(generated)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
