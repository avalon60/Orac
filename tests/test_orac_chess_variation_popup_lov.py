"""Verify native searchable owner-scoped variation LOVs at catalogue scale."""
# Author: Clive Bostock
# Date: 11-Nov-2026
# Description: Guard popup paging, owner filtering and recovery read-only fields.

from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1] / 'plugins/orac_chess'


def items(relative: str) -> dict[str, str]:
    """Read exported page-item definitions by their native item name."""
    text = (ROOT / 'apex' / relative).read_text()
    return {re.search(r"p_name=>'([^']+)'", block)[1]: block for block in
            re.findall(r'wwv_flow_imp_page\.create_page_item\(.*?\n\);', text, re.S)}


@pytest.mark.parametrize('name', ['P31_OPENING_ID', 'P31_GAMBIT_ID', 'P31_PARENT_VARIATION_ID'])
def test_variation_lovs_use_native_search_and_first_rowset(name: str) -> None:
    """Large catalogues use native server-fetched popup choices instead of full selects."""
    block = items('orac_chess_admin.sql')[name]
    assert "p_display_as=>'NATIVE_POPUP_LOV'" in block
    for attribute in ["'initial_fetch','FIRST_ROWSET'", "'manual_entry','N'",
                      "'match_type','CONTAINS'", "'min_chars','0'"]:
        assert attribute in block
    if name != 'P31_PARENT_VARIATION_ID':
        assert "p_read_only_when=>'P31_VARIATION_ID'" in block
        assert "p_read_only_when_type=>'ITEM_IS_NOT_NULL'" in block
    recovery = items('recovery/orac_chess_admin_readonly.sql')[name]
    assert "p_display_as=>'NATIVE_DISPLAY_ONLY'" in recovery


def test_parent_choices_are_owner_scoped_self_excluding_and_cascading() -> None:
    """The parent lookup submits current owners and never returns the edited row."""
    block = items('orac_chess_admin.sql')['P31_PARENT_VARIATION_ID']
    assert "p_lov_cascade_parent_items=>'P31_OPENING_ID,P31_GAMBIT_ID'" in block
    assert "p_ajax_items_to_submit=>'P31_OPENING_ID,P31_GAMBIT_ID,P31_VARIATION_ID'" in block
    assert ':P31_OPENING_ID is not null and :P31_GAMBIT_ID is null and v.opening_id = :P31_OPENING_ID' in block
    assert ':P31_GAMBIT_ID is not null and :P31_OPENING_ID is null and v.gambit_id = :P31_GAMBIT_ID' in block
    assert ':P31_VARIATION_ID is null or v.variation_id <> :P31_VARIATION_ID' in block
    assert 'v.line_kind' in block
    assert 'from orac_chess.chess_variation_v v' in block


def test_exported_parent_query_executes_only_for_the_selected_owner() -> None:
    """Execute the exported relational predicate against opening and gambit fixtures."""
    import sqlite3

    block = items('orac_chess_admin.sql')['P31_PARENT_VARIATION_ID']
    encoded = block.split('p_lov=>wwv_flow_string.join(wwv_flow_t_varchar2(\n', 1)[1].split('\n,p_lov_cascade_parent_items', 1)[0].removesuffix('))')
    lines = re.findall(r"^'((?:[^']|'')*)'[,]?$", encoded, re.M)
    sql = '\n'.join(line.replace("''", "'") for line in lines)
    assert sql.startswith('select v.name')
    with sqlite3.connect(':memory:') as connection:
        connection.execute("attach database ':memory:' as orac_chess")
        connection.execute('create table orac_chess.chess_variation_v (variation_id integer, opening_id integer, gambit_id integer, name text, line_kind text, parent_variation_id integer)')
        connection.executemany('insert into orac_chess.chess_variation_v values (?,?,?,?,?,?)', [
            (1, 10, None, 'Opening root', 'MAIN', None),
            (2, 10, None, 'Edited child', 'CONTINUATION', 1),
            (3, 10, None, 'Other child', 'ALTERNATIVE', 1),
            (4, 20, None, 'Other opening root', 'MAIN', None),
            (5, None, 10, 'Gambit root', 'MAIN', None),
        ])
        def lookup(opening: int | None, gambit: int | None, current: int | None = None) -> list[int]:
            return [row[1] for row in connection.execute(sql, {
                'P31_OPENING_ID': opening, 'P31_GAMBIT_ID': gambit,
                'P31_VARIATION_ID': current})]
        assert lookup(10, None, 2) == [1, 3]
        assert lookup(20, None) == [4]
        assert lookup(None, 10) == [5]
        assert lookup(None, None) == []
        assert lookup(10, 10) == []
