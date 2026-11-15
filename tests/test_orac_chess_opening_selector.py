"""Protect the five native views on the Chess Opening detail page."""
# Author: Clive Bostock
# Date: 14-Nov-2026
# Description: Verify Opening selector targets and existing form connections.
# Purpose: Detect packaged Opening selector regressions.
# Usage: .venv/bin/python -m pytest tests/test_orac_chess_opening_selector.py

from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1] / 'plugins/orac_chess'


@pytest.mark.parametrize('relative', ['orac_chess_admin.sql',
                                     'recovery/orac_chess_admin_readonly.sql'])
def test_opening_selector_preserves_five_views_and_controls(relative: str) -> None:
    """Select PGN first while preserving the existing regions and actions."""
    source = (ROOT / 'apex' / relative).read_text(encoding='utf-8')
    page = source.split('prompt --application/pages/page_00011\n', 1)[1].split(
        'prompt --application/pages/page_00020\n', 1)[0]
    regions = re.findall(r'wwv_flow_imp_page\.create_page_plug\((.*?)\n\);', page, re.S)
    selectors = [r for r in regions if "p_plug_source_type=>'NATIVE_DISPLAY_SELECTOR'" in r]
    assert len(selectors) == 1
    selector = selectors[0]
    assert 'id(97000000000000011)' in selector
    assert 'p_plug_display_sequence=>5' in selector
    for setting in ("'include_show_all', 'N'", "'remember_selection', 'N'",
                    "'rds_mode', 'STANDARD'", "'display_region_icons', 'N'"):
        assert setting in selector
    targets = [r for r in regions if "p_include_in_reg_disp_sel_yn=>'Y'" in r]
    assert len(targets) == 5
    expected = [(27430604072874915, 'Opening Synopsis', 20),
                (98900000000001101, 'Variations', 30),
                (98700000000000011, 'PGN Viewer', 10),
                (27430604072874929, 'Aliases', 51),
                (27430604072874947, 'Gambits', 53)]
    for region_id, name, sequence in expected:
        region = next(r for r in targets if f'id({region_id})' in r)
        assert f"p_plug_name=>'{name}'" in region
        assert f'p_plug_display_sequence=>{sequence}\n' in region
    assert 'select alias_name from orac_chess.chess_opening_alias_v where opening_id=:P11_OPENING_ID' in page
    worksheets = re.findall(r'create_worksheet\((.*?)\n\);', page, re.S)
    for worksheet_id, label in ((27430604072874930, 'Aliases'), (27430604072874948, 'Gambits')):
        worksheet = next(w for w in worksheets if f'id({worksheet_id})' in w)
        assert f"p_name=>'{label}'" in worksheet
    items = re.findall(r'wwv_flow_imp_page\.create_page_item\((.*?)\n\);', page, re.S)
    for name in ('P11_OPENING_ID', 'P11_ROW_VERSION', 'P11_NAME', 'P11_DESCRIPTION'):
        item = next(item for item in items if f"p_name=>'{name}'" in item)
        assert 'p_item_plug_id=>wwv_flow_imp.id(27430604072874915)' in item
    assert 'orac_chess.chess_opening_eco_v' in page
    assert 'orac_chess.chess_opening_gambit_v' in page
    if relative == 'orac_chess_admin.sql':
        buttons = re.findall(r'wwv_flow_imp_page\.create_page_button\((.*?)\n\);', page, re.S)
        for name, region_id in [('SAVE', 27430604072874915),
                                ('DELETE', 27430604072874915),
                                ('CANCEL', 27430604072874915),
                                ('LINK_1', 27430604072874929),
                                ('UNLINK_1', 27430604072874929),
                                ('LINK_3', 27430604072874947),
                                ('UNLINK_3', 27430604072874947)]:
            button = next(b for b in buttons if f"p_button_name=>'{name}'" in b)
            assert f'p_button_plug_id=>wwv_flow_imp.id({region_id})' in button
        assert 'chess_admin_api.save_opening' in page


@pytest.mark.parametrize('relative', ['orac_chess_admin.sql',
                                     'recovery/orac_chess_admin_readonly.sql'])
def test_opening_gambits_offer_descriptors_and_read_only_drawer(relative: str) -> None:
    """Names open protected details without submitting or changing the opening."""
    source = (ROOT / 'apex' / relative).read_text(encoding='utf-8')
    opening = source.split('prompt --application/pages/page_00011\n', 1)[1].split(
        'prompt --application/pages/page_00020\n', 1)[0]
    assert 'join orac_chess.chess_gambit_v g on g.gambit_id=m.gambit_id' in opening
    assert 'where m.opening_id=:P11_OPENING_ID order by g.name' in opening
    assert 'dbms_lob.substr(g.description, 240, 1)' in opening
    assert 'No description available.' in opening
    columns = re.findall(r'create_worksheet_column\((.*?)\n\);', opening, re.S)
    identifier = next(c for c in columns if "p_db_column_name=>'GAMBIT_ID'" in c)
    assert "p_column_type=>'NUMBER'" in identifier
    assert "p_display_text_as=>'HIDDEN_ESCAPE_SC'" in identifier
    assert "p_column_label=>'Gambit'" in identifier
    name = next(c for c in columns if "p_db_column_name=>'NAME'" in c)
    assert "p_column_label=>'Gambit'" in name
    assert "p_column_link=>'f?p=&APP_ID.:22:&APP_SESSION.::&DEBUG.:22:P22_GAMBIT_ID:#GAMBIT_ID#'" in name
    assert "p_display_text_as=>'ESCAPE_SC'" in name
    assert "p_report_columns=>'NAME:DESCRIPTION'" in opening
    drawer = source.split('prompt --application/pages/page_00022\n', 1)[1].split(
        'prompt --application/pages/page_00030\n', 1)[0]
    assert "p_name=>'Gambit Details'" in drawer
    assert "p_page_mode=>'MODAL'" in drawer
    assert 'js-dialog-class-t-Drawer--pullOutEnd' in drawer
    assert 'p_required_role=>wwv_flow_imp.id(21969436581161538)' in drawer
    assert "p_protection_level=>'C'" in drawer
    assert "p_name=>'P22_GAMBIT_ID'" in drawer
    assert "p_protection_level=>'S'" in drawer
    assert "'value_protected','Y'" in drawer
    assert 'from orac_chess.chess_gambit_v where gambit_id=:P22_GAMBIT_ID' in drawer
    assert 'apex_escape.html(l_name)' in drawer
    assert 'apex_escape.html(dbms_lob.substr(p_text, 1000, l_offset))' in drawer
    assert "escaped_text(l_description, ''No description available.'')" in drawer
    assert "escaped_text(l_strategy, ''No strategy available.'')" in drawer
    assert 'when no_data_found then' in drawer
    assert 'This gambit is no longer available.' in drawer
    assert 'white-space: pre-wrap' in drawer
    assert 'apex.navigation.dialog.cancel(true)' in drawer
    assert "p_button_execute_validations=>'N'" in drawer
    processes = re.findall(r'wwv_flow_imp_page\.create_page_process\((.*?)\n\);', drawer, re.S)
    assert len(processes) == 1
    callback = processes[0]
    assert "p_process_name=>'PGN_VIEWER'" in callback
    assert "p_process_point=>'ON_DEMAND'" in callback
    assert "p_process_type=>'NATIVE_PLSQL'" in callback
    assert 'from orac_chess.chess_variation_v v' in callback
    assert 'v.variation_id=l_id and v.gambit_id=:P22_GAMBIT_ID' in callback
    assert "regexp_like(apex_application.g_x02,''^[1-9][0-9]{0,17}$'')" in callback
    assert "apex_json.write(''pgn'',l_pgn)" in callback
    assert not re.search(r'\b(insert|update|delete|merge|execute immediate)\b', callback, re.I)
    assert 'ORAC_ADMIN' not in callback
    buttons = re.findall(r'wwv_flow_imp_page\.create_page_button\((.*?)\n\);', drawer, re.S)
    assert all("p_button_action=>'SUBMIT'" not in button for button in buttons)
    assert 'chess_admin_api.' not in drawer
    assert ':21:' not in name
    if relative == 'orac_chess_admin.sql':
        item = next(i for i in re.findall(r'create_page_item\((.*?)\n\);', opening, re.S)
                    if "p_name=>'P11_LINK_GAMBIT_ID'" in i)
        assert "p_prompt=>'Gambit'" in item
        assert 'Unlink removes only that association' in item
        assert 'chess_admin_api.link_opening_gambit' in opening
