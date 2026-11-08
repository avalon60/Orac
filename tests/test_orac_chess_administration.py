"""Verify Chess administration deployment and exported security boundaries."""
# Author: Clive Bostock
# Date: 02-Nov-2026
# Description: Protect public grants, authoritative PGN integration and APEX wiring.
# Purpose: Detect boundary regressions without claiming authenticated browser coverage.
# Usage: .venv/bin/python -m pytest tests/test_orac_chess_administration.py

from pathlib import Path
import json
import re
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1] / 'plugins/orac_chess'


def test_consumer_grants_are_only_explicit_reads_and_public_apis() -> None:
    """The parsing schema receives no private entrypoint or base DML grant."""
    text = '\n'.join(p.read_text() for p in (ROOT / 'db/schema/grant').glob('*.sql'))
    grants = re.findall(r'^grant (\w+) on orac_chess\.(\w+) to (\w+);', text, re.M)
    assert len(grants) == 28
    assert ('select', 'chess_content_source_v', 'orac_apx_pub') in grants
    assert ('select', 'chess_eco_code_v', 'orac_apx_pub') in grants
    assert all(grantee == 'orac_apx_pub' for _, _, grantee in grants)
    assert {name for privilege, name, _ in grants if privilege == 'execute'} == {
        'chess_admin_api', 'chess_game_api', 'chess_variation_api', 'chess_image_api',
    }
    assert all(name.endswith('_v') for privilege, name, _ in grants if privilege == 'select')
    assert {privilege for privilege, _, _ in grants} == {'select', 'execute'}


def test_gated_pgn_sources_are_outside_active_migration_chain() -> None:
    """Failed candidate Java assets cannot make safe administration undeployable."""
    tree = ET.parse(ROOT / 'db/liquibase/pluginController.xml')
    active = [n.attrib['file'] for n in tree.getroot() if n.tag.endswith('include')]
    assert all('java' not in path.lower() for path in active)
    assert (ROOT / 'db/diagnostics/javaController.xml').exists()
    for entity in ('game', 'variation'):
        body = (ROOT / f'db/schema/package_body/chess_{entity}_api.sql').read_text()
        assert f'chess_admin_tapi.save_{entity}' in body
        assert f'chess_admin_tapi.delete_{entity}' in body


def test_apex_export_applies_auth_and_uses_controlled_api_processes() -> None:
    """Every business page shares plugin/role checks and has no base-table DML."""
    source = (ROOT / 'apex/orac_chess_admin.sql').read_text()
    assert "'orac_chess'" in source.replace("''", "'")
    assert "has_required_role('ORAC_ADMIN')" in source.replace("''", "'")
    assert "p_caching=>'NOCACHE'" in source
    assert "p_name=>'ORAC_INSTALL_RECEIPT'\n,p_value=>'UNATTESTED'" in source
    assert "p_scheme_type=>'NATIVE_APEX_ACCOUNTS'" in source
    pages = re.split(r'prompt --application/pages/page_(\d+)\n', source)
    count = 0
    for index in range(1, len(pages), 2):
        page_id, content = int(pages[index]), pages[index + 1]
        if page_id not in (0, 9999):
            assert 'p_required_role=>' in content, page_id
            count += 1
        if page_id in (31, 61):
            assert 'PGN maintenance unavailable' not in content
            assert "p_button_name=>'SAVE'" in content
            assert "p_button_name=>'DELETE'" in content
            assert "p_button_execute_validations=>'N'" in content
            assert 'p_confirm_message=>' in content
            assert "p_confirm_style=>'danger'" in content
            assert 'p_button_confirmation=>' not in content
            assert 'p_button_css_classes=>' not in content
            assert "p_display_as=>'NATIVE_DISPLAY_ONLY'" not in content
    assert count == 20
    assert not re.search(r'\b(?:insert into|update|delete from|merge into)\s+orac_chess\.', source, re.I)
    assert 'chess_admin_tapi.' not in source
    assert 'chess_validation_api.' not in source
    assert 'apex_return_nav_api.' in source
    for header in ('Content-Disposition: inline', 'X-Content-Type-Options: nosniff', 'Cache-Control: private, no-store'):
        assert header in source


def test_opening_eco_editor_uses_one_complete_set_save() -> None:
    """Opening page loads selected codes and sends the entire set on Save."""
    source = (ROOT / 'apex/orac_chess_admin.sql').read_text()
    page = source.split('prompt --application/pages/page_00011', 1)[1].split(
        'prompt --application/pages/page_00020', 1
    )[0]
    assert "p_display_as=>'NATIVE_POPUP_LOV'" in page
    assert "p_multi_value_type=>'SEPARATED'" in page
    assert "p_multi_value_separator=>':'" in page
    assert 'orac_chess.chess_eco_code_v' in page
    assert 'dbms_lob.substr(description' in page
    assert 'dbms_lob.instr(lower(description),lower(:P11_ECO_SEARCH))' in page
    assert "p_ajax_items_to_submit=>'P11_ECO_SEARCH,P11_ECO_EDITOR'" in page
    assert "p_lov_cascade_parent_items=>'P11_ECO_SEARCH'" not in page
    assert 'listagg(eco_code' in page
    assert 'chess_opening_eco_v where opening_id=:P11_OPENING_ID' in page
    assert 'chess_admin_api.save_opening_with_eco' in page
    assert ':P11_LINK_ECO_CODE, l_version' in page
    assert "p_button_name=>'LINK_2'" not in page
    assert "p_button_name=>'UNLINK_2'" not in page
    assert "p_button_name=>'CANCEL'" in page
    assert "p_button_action=>'REDIRECT_PAGE'" in page


def test_transactions_remain_owned_by_callers() -> None:
    """Business maintenance never commits or uses autonomous transactions."""
    for path in (ROOT / 'db/schema/package_body').glob('*.sql'):
        source = re.sub(r'--[^\n]*', '', path.read_text())
        assert not re.search(r'\bcommit\b|\bautonomous_transaction\b', source, re.I), path


def test_mle_runtime_is_reproducible_and_ordered_before_writers() -> None:
    """Fresh and upgrade chains share typed private runtime and pinned sources."""
    import subprocess
    import sys

    for generator in ('generate_mle_runtime.py', 'generate_mle_recovery.py', 'generate_mle_acceptance.py'):
        subprocess.run([sys.executable, str(ROOT / 'tools' / generator), '--check'], check=True)
    controller = (ROOT / 'db/liquibase/pluginController.xml').read_text()
    assert controller.index('09_mle_runtime.xml') < controller.index('10_admin_api.xml')
    bridge = (ROOT / 'tools/mle/production_bridge.mjs').read_text()
    assert 'JSON.parse' not in bridge
    assert '4194304' in bridge
    assert not re.search(r"import .*?(?:fs|fetch|sql)", bridge)
    facade = (ROOT / 'db/schema/package_body/chess_validation_api.sql').read_text()
    assert 'l_root := l_node' in facade
    assert 'validate_branch(l_parent.pgn,l_node.pgn' in facade
    assert '-20020' in facade


def test_variation_dialog_closes_and_refreshes_and_headers_are_explicit() -> None:
    """Successful variation actions use modal close and header extraction is opt-in."""
    source = (ROOT / 'apex/orac_chess_admin.sql').read_text()
    pages = dict(zip(*[iter(re.split(r'prompt --application/pages/page_(\d+)\n', source)[1:])]*2))
    assert "p_process_type=>'NATIVE_CLOSE_WINDOW'" in pages['00031']
    assert "p_branch_type=>'REDIRECT_URL'" not in pages['00031']
    assert 'apexafterclosedialog' in pages['00030']
    assert "p_process_when=>'HEADERS'" in pages['00061']
    assert ':P61_WHITE_PLAYER is null' in pages['00061']
    assert "p_item_default=>'O'" in pages['00031']
    assert "p_item_default_type=>'STATIC'" not in source


def test_canonical_runtime_is_reapplied_after_withdrawal() -> None:
    """Managed repair recreates withdrawn objects without history/checksum resets."""
    for directory in ('mle_module', 'mle_env', 'function'):
        for path in (ROOT / 'db/schema' / directory).glob('*.sql'):
            assert 'runAlways:true' in path.read_text()
    for name in ('chess_validation_api', 'chess_game_api', 'chess_variation_api'):
        assert 'runAlways:true' in (ROOT / f'db/schema/package_body/{name}.sql').read_text()
    recovery = (ROOT / 'db/recovery/mle/withdraw.sql').read_text()
    assert recovery.index('@@chess_validation_api.sql') < recovery.index('drop function')
    assert not re.search(r'(?i)delete.*databasechangelog|clearchecksums|drop table', recovery)


def test_welcome_matches_runtime_and_renders_static_html() -> None:
    """Forward and withdrawal home pages accurately describe writer availability."""
    for relative, expected in (
        ('apex/orac_chess_admin.sql', 'PGN is validated before saving.'),
        ('apex/recovery/orac_chess_admin_readonly.sql', 'PGN validator runtime is withdrawn.'),
    ):
        source = (ROOT / relative).read_text()
        welcome = next(part for part in re.findall(r'wwv_flow_imp_page.create_page_plug\(.*?\n\);', source, re.S) if ",p_plug_name=>'Welcome'" in part)
        assert expected in welcome
        assert "'output_as', 'HTML'" in welcome
        assert 'compatibility gate remains unresolved' not in welcome


def test_game_date_conversion_only_applies_to_save_input() -> None:
    """Date formatting cannot replace a SELECT INTO target with a function call."""
    source = (ROOT / 'apex/orac_chess_admin.sql').read_text()
    load = next(part for part in re.findall(r'wwv_flow_imp_page.create_page_process\(.*?\n\);', source, re.S) if ",p_process_name=>'Load game'" in part)
    assert 'to_char(game_date,' in load
    assert 'to_date(' not in load
    save = next(part for part in re.findall(r'wwv_flow_imp_page.create_page_process\(.*?\n\);', source, re.S) if ",p_process_name=>'Save game'" in part)
    assert 'to_date(:P61_GAME_DATE,' in save


def test_dynamic_hierarchies_declare_plsql_language() -> None:
    """Native dynamic content must supply its code language for region execution."""
    source = (ROOT / 'apex/orac_chess_admin.sql').read_text()
    regions = [part for part in re.findall(r'wwv_flow_imp_page.create_page_plug\(.*?\n\);', source, re.S) if "p_plug_source_type=>'NATIVE_DYNAMIC_CONTENT'" in part]
    assert len(regions) >= 2
    assert all("p_function_body_language=>'PLSQL'" in part for part in regions)


def test_video_url_defaults_only_recognised_youtube_ids() -> None:
    """Execute exported JavaScript to protect provider and manual-entry behaviour."""
    import json
    import subprocess

    source = (ROOT / 'apex/orac_chess_admin.sql').read_text()
    page = source.split(" p_id=>41\n", 1)[1].split('prompt --application/pages/', 1)[0]
    action = page.split("p_name=>'Default YouTube video ID'", 1)[1]
    assert "p_triggering_element=>'P41_VIDEO_URL,P41_PLATFORM'" in action
    assert "p_execute_on_page_init=>'N'" in action
    code = action.split('p_attribute_01=>wwv_flow_string.join(wwv_flow_t_varchar2(\n', 1)[1].split('\n);', 1)[0]
    javascript = '\n'.join(re.findall(r"^'((?:[^']|'')*)'(?:,|\)\))?$", code, re.M)).replace("''", "'")
    assert javascript
    cases = [
        ('YouTube', 'https://www.youtube.com/watch?t=3&v=dQw4w9WgXcQ&list=abc', 'dQw4w9WgXcQ'),
        ('YouTube', 'https://youtu.be/Abc_123-xyz?t=10', 'Abc_123-xyz'),
        ('YouTube', 'http://www.youtu.be/dQw4w9WgXcQ', 'dQw4w9WgXcQ'),
        ('YouTube', 'https://m.youtube.com/shorts/dQw4w9WgXcQ', 'dQw4w9WgXcQ'),
        ('YouTube', 'https://youtube.com/embed/dQw4w9WgXcQ?start=4', 'dQw4w9WgXcQ'),
    ]
    rejected = [
        '', 'not a URL', '/watch?v=dQw4w9WgXcQ',
        'https:youtube.com/watch?v=dQw4w9WgXcQ',
        'https://youtube.com/wa\ntch?v=dQw4w9WgXcQ',
        'https://example.com/watch?v=dQw4w9WgXcQ',
        'https://youtube.com.evil/watch?v=dQw4w9WgXcQ',
        'https://notyoutube.com/watch?v=dQw4w9WgXcQ',
        'https://youtube.com@evil.test/watch?v=dQw4w9WgXcQ',
        'https://evil@youtube.com/watch?v=dQw4w9WgXcQ',
        'ftp://youtube.com/watch?v=dQw4w9WgXcQ',
        'https://youtube.com/watch', 'https://youtube.com/watch?v=short',
        'https://youtube.com/watch?v=dQw4w9WgXcQ&v=Abc_123-xyz',
        'https://youtube.com/watch?v=abcdefghij!',
        'https://youtube.com/other?v=dQw4w9WgXcQ',
        'https://youtu.be/dQw4w9WgXcQ/extra',
        'https://youtube.com/embed/short',
    ]
    cases.extend(('YouTube', url, 'manual-value') for url in rejected)
    cases.extend((platform, 'https://youtube.com/watch?v=dQw4w9WgXcQ', 'manual-value')
                 for platform in ('Other', 'youtube', ''))
    harness = '''const assert = require("node:assert/strict");
const code = CODE;
for (const [platform, url, expected] of CASES) {
    const values = {P41_PLATFORM: platform, P41_VIDEO_URL: url,
                    P41_EXTERNAL_VIDEO_ID: "manual-value"};
    const apex = {item: name => ({getValue: () => values[name],
                                setValue: value => {values[name] = value;}})};
    new Function("apex", code)(apex);
    assert.equal(values.P41_EXTERNAL_VIDEO_ID, expected, platform + ": " + url);
}
'''.replace('CODE', json.dumps(javascript)).replace('CASES', json.dumps(cases))
    subprocess.run(['node', '-e', harness], check=True, text=True)


def test_video_url_precedes_editable_external_id_as_requested() -> None:
    """The stakeholder explicitly requested URL before the editable ID field."""
    source = (ROOT / 'apex/orac_chess_admin.sql').read_text()
    for item, sequence in (('P41_VIDEO_URL', 11), ('P41_EXTERNAL_VIDEO_ID', 12)):
        definition = source.split(f"p_name=>'{item}'", 1)[1].split('\n);', 1)[0]
        assert f'p_item_sequence=>{sequence}\n' in definition
        assert "p_display_as=>'NATIVE_TEXT_FIELD'" in definition
        assert "'disabled', 'N'" in definition


def test_video_report_urls_open_in_a_safe_new_tab() -> None:
    """Video references remain native report links with an isolated new tab."""
    source = (ROOT / 'apex/orac_chess_admin.sql').read_text()
    page = source.split(" p_id=>40\n", 1)[1].split('prompt --application/pages/', 1)[0]
    column = page.split("p_db_column_name=>'VIDEO_URL'", 1)[1].split('\n);', 1)[0]
    assert "p_column_link=>'#VIDEO_URL#'" in column
    assert "p_column_linktext=>'#VIDEO_URL#'" in column
    assert 'target="_blank" rel="noopener noreferrer"' in column


def test_duration_input_is_server_converted_and_report_remains_numeric() -> None:
    """Friendly duration input preserves the numeric API and report operations."""
    source = (ROOT / 'apex/orac_chess_admin.sql').read_text()
    item = source.split("p_name=>'P41_DURATION_SECONDS'", 1)[1].split('\n);', 1)[0]
    assert "p_display_as=>'NATIVE_TEXT_FIELD'" in item
    assert "p_prompt=>'Duration (MM:SS or HH:MM:SS)'" in item
    process = source.split("p_process_name=>'Save video'", 1)[1].split('\n);', 1)[0]
    assert 'parse_duration(:P41_DURATION_SECONDS)' in process
    assert 'l_seconds < 1 or l_seconds > 9999999999' in process
    assert 'l_duration_seconds, l_published_on, l_version)' in process
    assert "p_process_when=>'SAVE'" in process
    assert "p_page_item_name => ''P41_DURATION_SECONDS''" in process
    column = source.split("p_db_column_name=>'DURATION_SECONDS'", 1)[1].split('\n);', 1)[0]
    assert "p_column_type=>'NUMBER'" in column
    assert "p_column_html_expression=>'#DURATION_DISPLAY#'" in column
    helper = source.split("p_db_column_name=>'DURATION_DISPLAY'", 1)[1].split('\n);', 1)[0]
    assert "p_display_text_as=>'HIDDEN_ESCAPE_SC'" in helper


def test_all_chess_product_date_surfaces_use_english_day_month_year() -> None:
    """Reports, pickers and save/load conversions share the user's date format."""
    for path in ('apex/orac_chess_admin.sql', 'apex/recovery/orac_chess_admin_readonly.sql'):
        source = (ROOT / path).read_text()
        assert "p_flow_language=>'en'" in source
        assert "p_date_format=>'DD-Mon-YYYY'" in source
        assert "p_timestamp_format=>'DD-Mon-YYYY HH24:MI:SS.FF'" in source
        assert "p_timestamp_tz_format=>'DD-Mon-YYYY HH24:MI:SS.FF TZH:TZM'" in source
        for name in ('P41_PUBLISHED_ON', 'P61_GAME_DATE'):
            item = source.split(f"p_name=>'{name}'", 1)[1].split('\n);', 1)[0]
            assert "p_format_mask=>'DD-Mon-YYYY'" in item
        for name in ('PUBLISHED_ON', 'GAME_DATE'):
            column = source.split(f"p_db_column_name=>'{name}'", 1)[1].split('\n);', 1)[0]
            assert "p_column_type=>'DATE'" in column
            assert "p_format_mask=>'DD-Mon-YYYY'" in column
        assert "to_char(game_date,''DD-Mon-YYYY'',''NLS_DATE_LANGUAGE=English'')" in source
        assert "to_char(published_on,''DD-Mon-YYYY'',''NLS_DATE_LANGUAGE=English'')" in source
        assert "to_date(:P61_GAME_DATE,''FXDD-Mon-YYYY'',''NLS_DATE_LANGUAGE=English'')" in source
        assert "to_date(:P41_PUBLISHED_ON,''FXDD-Mon-YYYY'',''NLS_DATE_LANGUAGE=English'')" in source
        assert 'YYYY-MM-DD' not in source


def test_content_source_maintenance_uses_protected_identity_and_version() -> None:
    """Source rename and delete target the original key with optimistic locking."""
    source = (ROOT / 'apex/orac_chess_admin.sql').read_text()
    pages = dict(zip(*[iter(re.split(r'prompt --application/pages/page_(\d+)\n', source)[1:])]*2))
    assert 'orac_chess.chess_content_source_v' in pages['00110']
    form = pages['00111']
    for name in ('ORIGINAL_CREATOR', 'ROW_VERSION'):
        item = re.search(r"create_page_item\(.*?p_name=>'P111_" + name + r"'.*?\n\);", form, re.S)[0]
        assert "p_protection_level=>'S'" in item
        assert "'value_protected', 'Y'" in item
    assert 'save_content_source(:P111_ORIGINAL_CREATOR, :P111_ROW_VERSION, :P111_CREATOR, :P111_AUTHOR, :P111_NOTES, l_version)' in form
    assert 'delete_content_source(:P111_ORIGINAL_CREATOR, :P111_ROW_VERSION)' in form
    assert "p_data_type=>'CLOB'" in form
    assert "p_process_when=>'SAVE'" in form
    assert "p_process_when=>'DELETE'" in form
    assert "p_button_action=>'REDIRECT_PAGE'" in form
    assert "p_confirm_style=>'danger'" in form
    assert "p_button_condition=>'P111_ORIGINAL_CREATOR'" in form


def test_video_creator_popup_searches_source_and_author_but_returns_creator() -> None:
    """Video selection uses source identity while author remains a searchable column."""
    source = (ROOT / 'apex/orac_chess_admin.sql').read_text()
    lov = source.split('prompt --application/shared_components/user_interface/lovs/chess_content_sources\n')[1].split('prompt --application/pages/')[0]
    assert 'select creator, author from orac_chess.chess_content_source_v' in lov
    assert "p_return_column_name=>'CREATOR'" in lov
    assert "p_display_column_name=>'CREATOR'" in lov
    columns = re.findall(r'create_list_of_values_cols\(.*?\n\);', lov, re.S)
    assert len(columns) == 2
    for name, column in zip(('CREATOR', 'AUTHOR'), columns):
        assert f"p_query_column_name=>'{name}'" in column
        assert "p_is_visible=>'Y'" in column
        assert "p_is_searchable=>'Y'" in column
    items = re.findall(r'create_page_item\(.*?\n\);', source, re.S)
    item = next(item for item in items if "p_name=>'P41_CREATOR'" in item)
    assert "p_display_as=>'NATIVE_POPUP_LOV'" in item
    assert "p_named_lov=>'CHESS_CONTENT_SOURCES'" in item
    assert "p_lov_display_null=>'YES'" in item
    assert "p_lov_display_extra=>'NO'" in item
    assert "'manual_entry', 'N'" in item


def test_eco_editors_stage_changes_and_keep_context_read_only() -> None:
    """Every form gates its atomic writer behind an explicit dialog save."""
    source = (ROOT / 'apex/orac_chess_admin.sql').read_text()
    for page, subject, api in ((11, 'opening', 'chess_admin_api'), (21, 'gambit', 'chess_admin_api'), (31, 'variation', 'chess_variation_api')):
        part = source.split(f'prompt --application/pages/page_{page:05}', 1)[1].split('prompt --application/pages/', 1)[0]
        stage = 'P11_LINK_ECO_CODE' if page == 11 else f'P{page}_ECO_CODES'
        assert "p_plug_name=>'Edit ECO Codes'" in part
        assert "p_action=>'NATIVE_OPEN_REGION'" in part
        assert "p_action=>'NATIVE_CLOSE_REGION'" in part
        assert f"p_attribute_07=>'{stage}'" in part
        for item_name in (stage, f'P{page}_ECO_EDIT_REQUESTED'):
            item = part.split(f"p_name=>'{item_name}'", 1)[1].split('\n);', 1)[0]
            assert "p_protection_level=>'N'" in item
            assert "'value_protected','N'" in item
        assert f"p_attribute_07=>'P{page}_ECO_EDITOR'" in part
        assert f"if :P{page}_ECO_EDIT_REQUESTED = ''Y'' then" in part
        assert f'{api}.save_{subject}_with_eco' in part
        assert f'{api}.save_{subject}(' in part
        assert f":P{page}_ECO_EDIT_REQUESTED := ''N''" in part
        assert "apex_escape.html(dbms_lob.substr(r.description, 1000, l_offset))" in part
        assert f"dbms_lob.instr(lower(description),lower(:P{page}_ECO_SEARCH))" in part
        assert f"p_ajax_items_to_submit=>'P{page}_ECO_SEARCH,P{page}_ECO_EDITOR'" in part
    assert source.count("p_plug_name=>'Related ECO Codes (context only)'") == 2


def test_generated_eco_apex_components_are_current() -> None:
    """The three editors and disclosures remain generated from shared sources."""
    import subprocess
    import sys

    subprocess.run(
        [sys.executable, str(ROOT / 'tools/generate_eco_apex.py'), '--check'],
        check=True,
    )


def test_eco_disclosure_layout_is_shared_and_responsive() -> None:
    """All ECO disclosures use the same wrapping layout and native controls."""
    templates = ROOT / 'tools/apex_eco'
    css = (templates / 'css.sql.in').read_text()
    assert 'display: flex' in css and 'flex-wrap: wrap' in css
    assert 'details[open] { flex-basis: 100%' in css
    assert 'white-space: pre-wrap' in css and 'overflow-wrap: anywhere' in css
    for name in ('disclosure.sql.in', 'editor.sql.in'):
        source = (templates / name).read_text()
        assert '<div class="chess-eco-list">' in source
        assert '<div class="chess-eco-description">' in source
        assert '<details><summary>' in source
        assert 'apex_escape.html(dbms_lob.substr(r.description, 1000, l_offset))' in source
    source = (ROOT / 'apex/orac_chess_admin.sql').read_text()
    for page in (11, 21, 31):
        part = source.split(f'prompt --application/pages/page_{page:05}', 1)[1].split('prompt --application/pages/', 1)[0]
        assert 'p_inline_css=>' in part and '.chess-eco-list > details[open]' in part


def test_chess_declared_application_and_exports_use_reserved_id() -> None:
    """Normal installation and recovery both target the reserved Chess ID."""
    manifest = json.loads((ROOT.parent / 'orac_chess.json').read_text())
    app, = manifest['apex_apps']
    assert (app['application_id'], app['app_alias'], app['workspace'], app['parsing_schema']) == (
        10030, 'ORAC_CHESS_ADMIN', 'ORAC', 'ORAC_APX_PUB')
    for export in (ROOT / 'apex/orac_chess_admin.sql', ROOT / 'apex/recovery/orac_chess_admin_readonly.sql'):
        source = export.read_text()
        assert ',p_default_application_id=>10030\n' in source
        assert not re.search(r'(?:set_application_id\(|p_default_application_id=>)100(?:\)|\s)', source)
        assert source.count('<div class="chess-eco-list">') == 8


def test_subject_video_api_contract_survives_eco_replacement() -> None:
    """Both install stages expose the same atomic, caller-owned video operations."""
    for package in ('chess_admin_api', 'chess_admin_tapi'):
        for folder in ('package_spec', 'package_body'):
            baseline = (ROOT / f'db/schema/{folder}/{package}.sql').read_text()
            eco = (ROOT / f'db/schema/{folder}/{package}_eco.sql').read_text()
            for operation in ('set_subject_video_link', 'create_video_for_subject'):
                signature = re.search(rf'  procedure {operation}\([^\n]+', baseline).group()
                assert signature in eco
            if folder == 'package_body':
                added = baseline.split('  procedure set_subject_video_link(', 1)[1].split(f'end {package};', 1)[0]
                assert added == eco.split('  procedure set_subject_video_link(', 1)[1].split(f'end {package};', 1)[0]
                assert not re.search(r'\bcommit\b', added, re.I)
    acceptance = (ROOT / 'db/acceptance/verify_subject_videos.sql').read_text()
    assert '@@verify_subject_videos.sql' in (ROOT / 'db/acceptance/verify_admin_api.sql').read_text()
    for contract in ('no orphan video', 'Caller rollback removes', 'Stale subject link',
                     'Stale video link', 'Missing link', 'Unlink retains shared video',
                     'Metadata edits leave subject version unchanged'):
        assert contract in acceptance


def test_related_video_returns_preserve_observed_subject_state() -> None:
    """Execute exported JS: only the matching origin may adopt an exact mutation result."""
    import subprocess

    source = (ROOT / 'apex/orac_chess_admin.sql').read_text()
    for page, subject in ((11, 'OPENING'), (21, 'GAMBIT')):
        content = source.split(f'prompt --application/pages/page_{page:05d}', 1)[1].split('prompt --application/pages/', 1)[0]
        code = content.split('p_javascript_code_onload=>wwv_flow_string.join(wwv_flow_t_varchar2(\n', 1)[1].split('\n,p_step_title', 1)[0]
        javascript = '\n'.join(re.findall(r"^'((?:[^']|'')*)'(?:,|\)\)(?:.*)?)?$", code, re.M)).replace("''", "'")
        assert 'chessVideoAction' in javascript
        harness = r'''const assert = require('node:assert/strict');
const values = {KEY:'7', VERSION:'3', UNSAVED:'Unsaved subject text'};
let response, request, closed, beforeSubmit, options, refreshed=0, alerts=0;
const chain = {off:()=>chain,on:(name,handler)=>{if(name.startsWith('apexafterclosedialog.chessVideo'))closed=handler;if(name.startsWith('apexbeforepagesubmit.chessVideo'))beforeSubmit=handler;return chain;}};
const apex = {
 item:name=>({getValue:()=>values[name],setValue:value=>{values[name]=String(value);}}),
 region:()=>({refresh:()=>{refreshed++;}}),jQuery:()=>chain,
 server:{process:(name,data,callbacks)=>{request=data;options=callbacks;response=data=>{callbacks.success(data);callbacks.complete();};}},
 navigation:{dialog:()=>{}},message:{alert:()=>{alerts++;},confirm:(message,callback)=>callback(true)}
};
const window = {};
// Deliberately provide no randomUUID: HTTP development pages still have getRandomValues.
const crypto = {getRandomValues:array=>{array.fill(10);return array;}};
new Function('window','apex','crypto',CODE)(window,apex,crypto);
assert.match(window.chessVideoToken,/^[0-9a-f-]{36}$/);
window.chessVideoAction('LINK',20,5);
assert.equal(request.x06,'7');
assert.equal(beforeSubmit(),false); // Save must not submit the old observed version.
assert.equal(alerts,1);
const firstRequest=request;
window.chessVideoAction('LINK',21,5);
assert.equal(request,firstRequest); assert.equal(alerts,2); // serialise mutations
alerts=0;
response({subjectId:7,expected:3,token:window.chessVideoToken,version:4});
assert.equal(values.VERSION,'4'); assert.equal(refreshed,1);
assert.equal(values.UNSAVED,'Unsaved subject text');
assert.equal(beforeSubmit(),undefined); // Save may proceed after adopting the result.
window.chessVideoAction('LINK',21,5);
response({error:'Failed'});
assert.equal(values.VERSION,'4'); assert.equal(refreshed,1); assert.equal(alerts,1);
assert.equal(beforeSubmit(),undefined);
window.chessVideoAction('LINK',21,5);
options.error(); options.complete();
assert.equal(values.VERSION,'4'); assert.equal(refreshed,1); assert.equal(alerts,2);
assert.equal(beforeSubmit(),undefined); alerts=0;
// An older asynchronous result must not replace the now-observed version.
response({subjectId:7,expected:3,token:window.chessVideoToken,version:99});
assert.equal(values.VERSION,'4'); assert.equal(refreshed,1);
window.chessVideoAction('DIALOG',20);
response({url:'signed-modal-url'});
closed({}, {P41_ORIGIN_ID:7,P41_ORIGIN_EXPECTED:4,P41_ORIGIN_TOKEN:window.chessVideoToken});
assert.equal(values.VERSION,'4'); assert.equal(refreshed,2); // metadata-only edit
closed({}, {P41_ORIGIN_ID:8,P41_ORIGIN_EXPECTED:4,P41_ORIGIN_TOKEN:window.chessVideoToken,P41_ORIGIN_NEW_VERSION:9});
assert.equal(values.VERSION,'4'); assert.equal(refreshed,2);
closed({}, {P41_ORIGIN_ID:7,P41_ORIGIN_EXPECTED:4,P41_ORIGIN_TOKEN:'different',P41_ORIGIN_NEW_VERSION:9});
assert.equal(values.VERSION,'4');
closed({}, {P41_ORIGIN_ID:7,P41_ORIGIN_EXPECTED:4,P41_ORIGIN_TOKEN:window.chessVideoToken,P41_ORIGIN_NEW_VERSION:5});
assert.equal(values.VERSION,'5'); assert.equal(refreshed,3);
values.KEY=''; window.chessVideoAction('DIALOG'); assert.equal(alerts,1);
'''.replace('KEY', f'P{page}_{subject}_ID').replace('VERSION', f'P{page}_ROW_VERSION').replace('CODE', json.dumps(javascript))
        # Replacement above also affects the returned P41 property names; restore them.
        harness = harness.replace(f'ORIGIN_NEW_P{page}_ROW_VERSION', 'ORIGIN_NEW_VERSION')
        subprocess.run(['node', '-e', harness], check=True, text=True)


def test_related_video_search_filters_choices_after_region_refresh() -> None:
    """Search titles, creators and platforms without hiding linked videos."""
    import subprocess

    source = (ROOT / 'apex/orac_chess_admin.sql').read_text()
    for page in (11, 21):
        content = source.split(f'prompt --application/pages/page_{page:05d}', 1)[1].split('prompt --application/pages/', 1)[0]
        # Decode the export string and then the dynamic PL/SQL HTML literal.
        exported_line = next(line for line in content.splitlines() if 'oninput=' in line)
        plsql = re.fullmatch(r"'((?:[^']|'')*)',?", exported_line).group(1).replace("''", "'")
        html = re.search(r"l_html := l_html \|\| '((?:[^']|'')*)';", plsql).group(1).replace("''", "'")
        javascript = re.search(r'oninput="([^"]+)"', html).group(1)
        harness = r'''const assert = require('node:assert/strict');
const linked = {textContent:'Already linked lesson', hidden:false};
const row = textContent => ({textContent, hidden:false});
let choices = [row('Queen Gambit basics — Alice — YouTube'),
               row('Sicilian lesson — ChessVibes — Vimeo'),
               row('Endgame ideas — Bob — PeerTube')];
let query = '';
const apex = {region:name=>{
  assert.equal(name,'related_videos');
  return {widget:()=>null, element:{find:selector=>({each:callback=>{
    const rows = selector === '.chess-video-choice' ? choices : [...choices, linked];
    rows.forEach(item=>callback.call(item));
  }})}};
}};
const document = {getElementById:id=>{
  assert.equal(id,'video_search'); return {value:query};
}};
const filter = new Function('apex','document',CODE);
const search = (value, expected) => {
  query=value; filter(apex,document);
  assert.deepEqual(choices.map(item=>item.hidden),expected);
  assert.equal(linked.hidden,false);
};
search('gAmBiT',[false,true,true]);
search('cHeSsViBeS',[true,false,true]);
search('pEeRtUbE',[true,true,false]);
search('no matching lesson',[true,true,true]);
search('',[false,false,false]);
// A region refresh replaces the available rows; subsequent input uses those rows.
const previousChoices = choices;
choices = [row('New opening — Carol — Vimeo'),row('Fresh gambit — Dan — YouTube')];
search('GaMbIt',[true,false]);
assert.deepEqual(previousChoices.map(item=>item.hidden),[false,false,false]);
search('',[false,false]);
'''.replace('CODE', json.dumps(javascript))
        subprocess.run(['node', '-e', harness], check=True, text=True, timeout=30)


def test_video_modal_uses_protected_origin_and_safe_subject_links() -> None:
    """Protect the modal identity, cancellation, cross-tab checks and outbound-link boundary."""
    source = (ROOT / 'apex/orac_chess_admin.sql').read_text()
    video = source.split('prompt --application/pages/page_00041', 1)[1].split('prompt --application/pages/', 1)[0]
    assert "p_page_mode=>'MODAL'" in video
    assert "p_process_type=>'NATIVE_CLOSE_WINDOW'" in video
    assert "javascript:apex.navigation.dialog.cancel(true);" in video
    assert 'create_page_branch(' not in video
    for item in ('ORIGIN_TYPE', 'ORIGIN_ID', 'ORIGIN_EXPECTED', 'ORIGIN_TOKEN'):
        definition = next(block for block in re.findall(r'create_page_item\(.*?\n\);', video, re.S)
                          if f"p_name=>'P41_{item}'" in block)
        assert "p_protection_level=>'S'" in definition
        assert "'value_protected','Y'" in definition
    for page, subject in ((11, 'OPENING'), (21, 'GAMBIT')):
        content = source.split(f'prompt --application/pages/page_{page:05d}', 1)[1].split('prompt --application/pages/', 1)[0]
        assert 'rel="noopener noreferrer"' in content
        assert "regexp_like(r.video_url,''^https?://''" in content
        assert "apex_escape.html_attribute(r.video_url)" in content
        assert f'to_number(apex_application.g_x06) != :P{page}_{subject}_ID' in content
        assert "regexp_like(apex_application.g_x02,''^[0-9]+$'')" in content
        assert "p_clear_cache=>''41''" in content
        assert 'apex_escape.html(r.platform)' in content
        assert 'not exists (select 1 from orac_chess.chess_video_' in content
