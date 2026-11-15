"""Verify browser viewer packaging and additive Chess APEX integration."""

# Author: Clive Bostock
# Date: 14-Nov-2026
# Description: Protect static asset bytes, approved read surfaces and existing page contracts.
# Purpose: Detect drift between browser sources and installed APEX export payloads.
# Usage: .venv/bin/python -m pytest tests/test_orac_chess_pgn_viewer.py

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins/orac_chess'
SPEC = importlib.util.spec_from_file_location('viewer_generator', PLUGIN / 'tools/generate_viewer_apex.py')
assert SPEC and SPEC.loader
GEN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GEN)


def test_export_matches_sources_and_asset_bytes() -> None:
    """Decode every generated BLOB and compare with its actual shipped resource."""
    source = GEN.EXPORT.read_text()
    assert GEN.generate(source) == source
    section = source.split('-- BEGIN GENERATED PGN STATIC_FILES\n')[1].split('-- END GENERATED PGN STATIC_FILES')[0]
    found = {}
    for block in section.split('begin\n')[1:]:
        name = re.search(r",p_file_name=>'([^']+)'", block).group(1)
        encoded = ''.join(re.findall(r"g_varchar2_table\(\d+\) := '([0-9A-F]+)'", block))
        found[name] = bytes.fromhex(encoded)
    assert found == GEN.assets()
    assert all(name.startswith(GEN.asset_prefix() + '/') for name in found)
    for name, data in found.items():
        if name.endswith(('.js', '.mjs')):
            for path in re.findall(r'from\s+[\'"]([^\'"]+)[\'"]', data.decode()):
                if path.startswith('.'):
                    import posixpath
                    assert posixpath.normpath(posixpath.join(posixpath.dirname(name), path)) in found
    assert not any('assets/pieces/' in name for name in found)


def test_callbacks_use_existing_views_and_bounded_metadata() -> None:
    """Read callbacks select complete CLOBs only for a scoped chosen line."""
    for page in GEN.PAGES:
        callback = GEN.callback(page)
        assert 'fetch next 101 rows only' in callback
        assert "apex_json.write('pgn',l_pgn)" in callback
        assert 'dbms_lob.substr' not in callback
        assert 'chess_variation_v' in callback
        assert 'query_variation_line_v' not in callback
        assert 'ORAC_ADMIN' not in callback
        assert not re.search(r'\b(insert|update|delete|merge|execute immediate)\b', callback, re.I)
        assert 'regexp_like' in callback
        assert "'output_as','HTML'" in GEN.components(page)
        assert ("p_include_in_reg_disp_sel_yn=>'Y'" in GEN.components(page)) == (page in (11, 21, 31))
    assert 'v.opening_id=:P11_OPENING_ID' in GEN.callback(11)
    assert 'v.gambit_id=:P22_GAMBIT_ID' in GEN.callback(22)
    assert 'v.opening_id=:P31_OPENING_ID' in GEN.callback(31)


def test_browser_model_contract() -> None:
    """Exercise actual shipped model modules with legal and malformed PGNs."""
    result = subprocess.run(['node', str(PLUGIN / 'browser/model.test.mjs')], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '# pass 21' in result.stdout


def test_viewer_navigation_and_disposal_contract() -> None:
    """Exercise public viewer state transitions against an isolated render boundary."""
    result = subprocess.run(['node', str(PLUGIN / 'browser/viewer.test.mjs')], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '# pass 3' in result.stdout


def test_adapter_stale_response_and_dialog_cleanup_contract() -> None:
    """Exercise actual adapter flow with isolated DOM and delayed AJAX boundaries."""
    result = subprocess.run(['node', str(PLUGIN / 'browser/apex.test.mjs')], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '# fail 0' in result.stdout


def test_gambit_selector_and_drawer_page_contracts() -> None:
    """Preserve complete form workflows while grouping regions and using drawer templates."""
    source = GEN.EXPORT.read_text()
    gambit = source.split('prompt --application/pages/page_00021\n')[1].split('prompt --application/pages/page_00022\n')[0]
    assert "p_plug_name=>'Gambit Synopsis'" in gambit
    regions = re.findall(r'create_page_plug\((.*?)\n\);', gambit, re.S)
    for name, sequence in (('PGN Viewer', 10), ('Gambit Synopsis', 20), ('Variations', 30)):
        region = next(region for region in regions if f"p_plug_name=>'{name}'" in region)
        assert f'p_plug_display_sequence=>{sequence}\n' in region
    assert "p_plug_source_type=>'NATIVE_DISPLAY_SELECTOR'" in gambit
    assert 'p_parent_plug_id=>wwv_flow_imp.id(99100000000000021)' in gambit
    assert "p_process_name=>'SAVE_GAMBIT'" in gambit or 'save_gambit(' in gambit
    for page in (22, 31, 41):
        page_source = source.split(f'prompt --application/pages/page_{page:05d}\n')[1].split('wwv_flow_imp_page.create_page_plug(')[0]
        assert "p_page_mode=>'MODAL'" in page_source
        assert 'p_step_template=>2100407606326202693' in page_source
        assert 'js-dialog-class-t-Drawer--pullOutEnd' in page_source



def test_variation_drawer_has_dedicated_region_selections() -> None:
    """Keep replay first by default, with details and ECO in dedicated selections."""
    source = GEN.EXPORT.read_text()
    page = source.split('prompt --application/pages/page_00031\n')[1].split('prompt --application/pages/page_00040\n')[0]
    regions = {}
    for block in page.split('wwv_flow_imp_page.create_page_plug(')[1:]:
        block = block.split(');', 1)[0]
        region_id = re.search(r'p_id=>wwv_flow_imp.id\((\d+)\)', block).group(1)
        regions[region_id] = block
    selected = [block for block in regions.values() if "p_include_in_reg_disp_sel_yn=>'Y'" in block]
    selected.sort(key=lambda block: int(re.search(r'p_plug_display_sequence=>(\d+)', block).group(1)))
    assert [re.search(r"p_plug_name=>'([^']+)'", block).group(1) for block in selected] == [
        'PGN Viewer', 'Variation details', 'ECO Codes'
    ]
    selector = regions['97010000000000031']
    assert "p_plug_source_type=>'NATIVE_DISPLAY_SELECTOR'" in selector
    assert "'include_show_all','N'" in selector
    assert "'remember_selection','N'" in selector
    assert "p_plug_display_condition_type=>'NEVER'" in regions['99200000000000031']
    assert "p_include_in_reg_disp_sel_yn=>'Y'" not in regions['99300000000003100']



def test_variation_selector_identity_is_unique_in_recovery() -> None:
    """Keep the selector distinct from the runtime-withdrawal status region."""
    for export in (GEN.EXPORT, PLUGIN / 'apex/recovery/orac_chess_admin_readonly.sql'):
        source = export.read_text()
        ids = re.findall(r'wwv_flow_imp_page.create_page_plug\(\s*p_id=>wwv_flow_imp.id\((\d+)\)', source)
        assert ids.count('97010000000000031') == 1
        assert len(ids) == len(set(ids))



def test_explorer_display_name_preserves_application_identity() -> None:
    """Use the Explorer name across discovery and exports without reallocating it."""
    manifest = json.loads((ROOT / 'plugins/orac_chess.json').read_text())
    assert manifest['plugin_id'] == 'orac_chess'
    app = manifest['apex_apps'][0]
    assert app['label'] == 'Orac Chess Explorer'
    assert app['application_id'] == 10030
    assert app['app_alias'] == 'ORAC_CHESS_ADMIN'
    assert manifest['ui']['surfaces'][0]['label'] == 'Orac Chess Explorer'
    for export in (GEN.EXPORT, PLUGIN / 'apex/recovery/orac_chess_admin_readonly.sql'):
        source = export.read_text()
        assert "set_application_name('Orac Chess Explorer')" in source
        assert 'Orac Chess Administration' not in source
        assert 'ORAC_CHESS_ADMIN' in source
        assert '10030' in source


def test_changed_module_invalidates_entire_relative_import_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    """A changed dependency must change every asset URL, including unchanged importers."""
    initial = GEN.assets()
    sources = GEN.asset_sources()
    sources['browser/model.mjs'] += b'\n// changed dependency\n'
    monkeypatch.setattr(GEN, 'asset_sources', lambda: sources)
    updated = GEN.assets()
    assert set(initial).isdisjoint(updated)
    assert 'PGN Viewer' in GEN.components(11)
    assert GEN.asset_prefix() in GEN.components(11)


def test_subject_headers_and_variations_match_selected_subject() -> None:
    """Keep identity visible and exclude lines belonging to unrelated subjects."""
    import re
    import sqlite3

    database = sqlite3.connect(':memory:')
    database.execute("attach database ':memory:' as orac_chess")
    database.executescript("""
        create table orac_chess.chess_variation_v (
          variation_id integer, name text, line_kind text, parent_variation_id integer,
          branch_ply integer, opening_id integer, gambit_id integer);
        create table orac_chess.chess_opening_gambit_v (opening_id integer, gambit_id integer);
        insert into orac_chess.chess_opening_gambit_v values (1, 2);
        insert into orac_chess.chess_variation_v values
          (1,'Direct','MAIN',null,null,1,null),
          (2,'Linked','MAIN',null,null,null,2),
          (3,'Child','BRANCH',2,4,null,2),
          (4,'Unrelated opening','MAIN',null,null,9,null),
          (5,'Unrelated gambit','MAIN',null,null,null,9);
    """)
    for page, expected in ((11, {'Direct', 'Linked', 'Child'}),
                           (21, {'Linked', 'Child'})):
        rendered = GEN.subject_components(page)
        header, report = rendered.split("p_plug_name=>'Variations'", 1)
        assert 'p_plug_display_sequence=>1' in header
        assert 'apex_escape.html(l_name)' in header
        assert 'when no_data_found then' in header
        assert 'is null then' in header
        assert 'p_include_in_reg_disp_sel_yn' not in header
        assert 'p_plug_display_sequence=>30' in report
        assert 'p_display_rows=>15' in report
        source = report.split('p_plug_source=>wwv_flow_string.join(wwv_flow_t_varchar2(', 1)[1].split("\n,p_plug_source_type=>", 1)[0]
        query = '\n'.join(re.findall(r"'((?:[^']|'')*)'", source)).replace("''", "'")
        assert 'pgn' not in query.lower()
        parameters = {'P11_OPENING_ID': 1, 'P21_GAMBIT_ID': 2}
        assert {row[1] for row in database.execute(query, parameters)} == expected
    database.close()


def test_opening_variation_names_open_existing_protected_drawer() -> None:
    """Link escaped names to the existing native Variation drawer on Opening only."""
    import re

    for relative in ('orac_chess_admin.sql', 'recovery/orac_chess_admin_readonly.sql'):
        source = (PLUGIN / 'apex' / relative).read_text()
        for page in (11, 21):
            section = source.split(f'prompt --application/pages/page_{page:05d}\n', 1)[1].split('prompt --application/pages/', 1)[0]
            generated = section.split(f'-- BEGIN GENERATED PGN PAGE_{page}\n', 1)[1]
            columns = re.findall(r'create_worksheet_column\((.*?)\n\);', generated, re.S)
            name = next(c for c in columns if "p_db_column_name=>'NAME'" in c)
            identity = next(c for c in columns if "p_db_column_name=>'VARIATION_ID'" in c)
            assert "p_column_type=>'NUMBER'" in identity
            assert "p_display_text_as=>'HIDDEN_ESCAPE_SC'" in identity
            assert "p_display_text_as=>'ESCAPE_SC'" in name
            if page == 11:
                assert "p_column_link=>'f?p=&APP_ID.:31:&APP_SESSION.::&DEBUG.:RP:P31_VARIATION_ID:#VARIATION_ID#'" in name
                assert "p_column_linktext=>'#NAME#'" in name
            else:
                assert 'p_column_link' not in name
        drawer = source.split('prompt --application/pages/page_00031\n', 1)[1].split('prompt --application/pages/', 1)[0]
        assert "p_page_mode=>'MODAL'" in drawer
        assert 'js-dialog-class-t-Drawer--pullOutEnd' in drawer
        assert "p_protection_level=>'C'" in drawer
        identity = next(i for i in re.findall(r'create_page_item\((.*?)\n\);', drawer, re.S)
                        if "p_name=>'P31_VARIATION_ID'" in i)
        assert "p_protection_level=>'S'" in identity
        assert "'value_protected', 'Y'" in identity or "'value_protected','Y'" in identity
