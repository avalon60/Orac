"""Protect native Report/Variations Hierarchy selection on Chess page 30."""
# Author: Clive Bostock
# Date: 10-Nov-2026
# Description: Verify selector targets while preserving worksheet and dialog actions.

from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1] / 'plugins/orac_chess'


@pytest.mark.parametrize('relative', ['orac_chess_admin.sql',
                                     'recovery/orac_chess_admin_readonly.sql'])
def test_variation_selector_has_only_two_ordered_views(relative: str) -> None:
    """Both exports offer only the existing report and variation tree as targets."""
    text = (ROOT / 'apex' / relative).read_text()
    page = text.split('prompt --application/pages/page_00030\n', 1)[1].split(
        'prompt --application/pages/page_00031\n', 1)[0]
    regions = re.findall(r'wwv_flow_imp_page\.create_page_plug\((.*?)\n\);', page, re.S)
    selectors = [region for region in regions if "p_plug_source_type=>'NATIVE_DISPLAY_SELECTOR'" in region]
    assert len(selectors) == 1
    selector = selectors[0]
    assert 'p_plug_display_sequence=>5' in selector
    for setting in ["'include_show_all', 'N'", "'remember_selection', 'N'",
                    "'rds_mode', 'STANDARD'", "'display_region_icons', 'N'"]:
        assert setting in selector
    targets = [region for region in regions if "p_include_in_reg_disp_sel_yn=>'Y'" in region]
    assert len(targets) == 2
    report = next(region for region in targets if 'id(27430604072874975)' in region)
    tree = next(region for region in targets if 'id(33072953942781208)' in region)
    assert "p_plug_name=>'Report'" in report and 'p_plug_display_sequence=>10' in report
    assert "p_plug_source_type=>'NATIVE_IR'" in report
    assert "p_plug_name=>'Variations Hierarchy'" in tree and 'p_plug_display_sequence=>20' in tree
    assert 'connect by nocycle prior variation_id=parent_variation_id' in tree
    assert "p_page=>31,p_items=>''P31_VARIATION_ID''" in tree
    assert "p_name=>'Variations'" in page  # Page and worksheet names remain unchanged.
    assert "p_action=>'NATIVE_REFRESH'" in page
    assert 'p_affected_region_id=>wwv_flow_imp.id(27430604072874975)' in page
    if relative == 'orac_chess_admin.sql':
        assert "p_button_name=>'CREATE'" in page
        assert 'p_button_plug_id=>wwv_flow_imp.id(27430604072874975)' in page
