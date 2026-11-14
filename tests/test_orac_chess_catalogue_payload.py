"""Exercise semantic payload identity, ordering and immutable sync packaging."""
# Author: Clive Bostock
# Date: 11-Nov-2026
# Description: Verify reproducible source desired state independently of Oracle deployment.

import copy
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1] / 'plugins/orac_chess'
sys.path.insert(0, str(ROOT))
from tools.generate_catalogue_sync import normalise, generate  # noqa: E402


def source() -> dict:
    """Return a minimal real opening, MAIN and legal continuation source fixture."""
    return {'source_revision': 'abc', 'openings': [
        {'name': 'Fixture', 'opening_type': 'OPENING', 'description': 'Reference',
         'parent_opening_name': '', 'eco_codes': ['B00', 'A00'], 'aliases': ['Other'],
         'mainline_name': 'Main', 'mainline_pgn': '1.e4 *', 'mainline_annotation': 'Main text',
         'mainline_eco_codes': ['B00'], 'source_key': 'opening_fixture'}],
        'gambits': [], 'opening_gambits': [], 'variations': [
        {'key': 'variation_fixture', 'source_key': 'variation_fixture', 'owner_type': 'OPENING',
         'owner_name': 'Fixture', 'parent_key': 'owner-mainline', 'name': 'Continued',
         'pgn': '1.e4 e5 *', 'annotation': 'Continued text', 'eco_codes': ['B00'],
         'line_kind': 'CONTINUATION', 'branch_ply': 1}]}


def test_semantic_identity_ignores_revision_metadata_and_relationship_order() -> None:
    """No-op source revisions and set reordering retain every desired-state hash."""
    first = source()
    second = copy.deepcopy(first)
    second['source_revision'] = 'different'
    second['provenance'] = {'review_time': 'tomorrow'}
    second['openings'][0]['eco_codes'].reverse()
    second['openings'][0]['is_existing'] = True
    a, b = normalise(first), normalise(second)
    assert a['entries'] == b['entries']
    second['variations'][0]['annotation'] = 'Corrected text'
    changed = normalise(second)
    assert changed['entries'][-1]['key'] == a['entries'][-1]['key']
    assert changed['entries'][-1]['source_hash'] != a['entries'][-1]['source_hash']
    assert changed['entries'][0]['source_hash'] == a['entries'][0]['source_hash']


def test_dependency_order_and_sql_inertness() -> None:
    """Parent references use stable keys and Unicode cannot become executable SQL."""
    data = source()
    data['openings'][0]['description'] = "O'Brien ♞ / --"
    payload = normalise(data)
    assert [e['key'] for e in payload['entries']] == ['opening_fixture', 'opening_fixture__main', 'variation_fixture']
    assert payload['entries'][-1]['desired']['fields']['parent_key'] == 'opening_fixture__main'
    sql = generate(data)
    assert 'hextoraw(' in sql and "O'Brien" not in sql
    assert 'chess_catalogue_api.apply_catalogue' in sql
    assert '--rollback empty' in sql and 'runAlways:' not in sql and 'runOnChange:' not in sql


def test_unknown_and_cyclic_dependencies_fail_before_sql_generation() -> None:
    """Malformed topology never emits a partially ordered batch."""
    data = source()
    data['variations'][0]['parent_key'] = 'missing'
    with pytest.raises(ValueError, match='Unknown/cyclic'):
        normalise(data)
    data = source()
    data['openings'][0]['parent_opening_name'] = 'Fixture'
    with pytest.raises(ValueError, match='Unknown/cyclic'):
        normalise(data)


def test_private_structure_is_reachable_before_catalogue_batches() -> None:
    """The package and private FK-backed ledger install after continuation support."""
    includes = [n.attrib['file'] for n in ET.parse(ROOT / 'db/liquibase/pluginController.xml').getroot()]
    assert includes.index('controllers/17_continuation.xml') < includes.index('controllers/15_eco_seed_batches.xml')
    batches = [n.attrib['file'] for n in ET.parse(ROOT / 'db/liquibase/controllers/15_eco_seed_batches.xml').getroot()]
    assert batches.index('../../schema/seed_data/chess_descriptions_2026_11_10.sql') < batches.index('../../schema/view/chess_opening_v_strategy.sql') < batches.index('18_catalogue_sync.xml') < batches.index('../../schema/seed_data/chess_batch_2026_11_10_comprehensive_catalogue.sql')
    control = ROOT / 'db/liquibase/controllers/18_catalogue_sync.xml'
    paths = [(control.parent / n.attrib['file']).resolve() for n in ET.parse(control).getroot()]
    assert all(path.is_file() for path in paths)
    assert paths.index(ROOT / 'db/schema/table/chess_catalogue_entry.sql') < paths.index(ROOT / 'db/schema/package_body/chess_catalogue_api.sql')


def test_every_generated_hex_chunk_round_trips_utf8_without_split_codepoints() -> None:
    """Per-chunk Oracle RAW decoding preserves accented and four-byte Unicode text."""
    import re

    data = source()
    data['openings'][0]['description'] = 'a' * 399 + '♞😀Grünfeld Réti ' * 100
    sql = generate(data)
    chunks = re.findall(r"(?:hextoraw|append_payload)\('([0-9a-f]+)'\)", sql)
    assert chunks and all(len(chunk) <= 4000 for chunk in chunks)
    # Decode each chunk independently, as UTL_I18N.RAW_TO_CHAR does in deployment.
    decoded = ''.join(bytes.fromhex(chunk).decode('utf-8', errors='strict') for chunk in chunks)
    assert json.loads(decoded) == normalise(data)
    comprehensive = json.loads((ROOT / 'seed/catalogue/2026_11_10_comprehensive_catalogue/catalogue.json').read_text())
    packaged = (ROOT / 'db/schema/seed_data/chess_batch_2026_11_10_comprehensive_catalogue.sql').read_text()
    chunks = re.findall(r"(?:hextoraw|append_payload)\('([0-9a-f]+)'\)", packaged)
    decoded = ''.join(bytes.fromhex(chunk).decode('utf-8', errors='strict') for chunk in chunks)
    assert json.loads(decoded) == normalise(comprehensive)
