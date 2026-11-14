"""Protect the narrow once-only description repair and catalogue text coverage."""
# Author: Clive Bostock
# Date: 10-Nov-2026
# Description: Check complete packaged text and API-only missing-description repair.

import csv
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1] / 'plugins/orac_chess'


def test_all_starter_subjects_and_lines_have_text() -> None:
    """All 50 openings, 40 gambits and 190 instructional lines carry original prose."""
    batch = ROOT / 'seed/batches/2026_11_10_starter_catalogue'
    for filename, count in [('openings.csv', 50), ('gambits.csv', 40)]:
        rows = list(csv.DictReader((batch / filename).open()))
        assert len(rows) == count
        assert all(row['description'].strip() and row['mainline_annotation'].strip() for row in rows)
    branches = list(csv.DictReader((batch / 'variations.csv').open()))
    assert len(branches) == 100 and all(row['annotation'].strip() for row in branches)


def test_description_repair_is_narrow_atomic_and_api_mediated() -> None:
    """Vienna resets canonical fields/ECO while video text remains blank-only."""
    sql = (ROOT / 'db/schema/seed_data/chess_descriptions_2026_11_10.sql').read_text()
    assert "where name = 'Vienna Game'" in sql
    assert "where platform = 'YouTube' and external_video_id = '0ehLrDd2pn4'" in sql
    assert "not regexp_like(p_value,'[^[:space:]]')" in sql
    assert 'p_value is null or dbms_lob.getlength(p_value) = 0' in sql
    assert 'blank(l_video.description)' in sql
    assert 'dbms_lob.compare(l_opening.description' in sql
    assert 'l_eco_count != 1 or l_canonical_eco_count != 1' in sql
    assert "'Vienna Game','OPENING'" in sql and "null,'C25',l_next" in sql
    assert 'l_video.duration_seconds,l_video.published_on,l_next' in sql
    assert 'save_opening_with_eco(' in sql and 'save_video(' in sql
    assert 'save_variation' not in sql and 'link_' not in sql
    assert 'savepoint chess_description_backfill' in sql and 'rollback to chess_description_backfill' in sql
    assert '--rollback empty' in sql and 'runAlways:' not in sql and 'runOnChange:' not in sql
    assert not re.search(r'\b(insert into|update orac_chess|delete from|commit;)\b', sql, re.I)
    # Missing lookup handling ends before each writer: API errors cannot be swallowed.
    assert sql.index('l_opening.opening_id := null') < sql.index('  end;\n  if l_opening') < sql.index('save_opening_with_eco(')
    assert sql.index('l_video.video_id := null') < sql.index('  end;\n  if l_video') < sql.index('save_video(')


def test_description_repair_follows_the_released_starter_changeset() -> None:
    """The existing post-ECO controller reaches exactly one later immutable repair."""
    controller = ROOT / 'db/liquibase/controllers/15_eco_seed_batches.xml'
    includes = [node.attrib['file'] for node in ET.parse(controller).getroot()]
    repair = '../../schema/seed_data/chess_descriptions_2026_11_10.sql'
    starter = '../../schema/seed_data/chess_batch_2026_11_10_starter_catalogue.sql'
    assert includes.count(repair) == 1 and includes.index(starter) < includes.index(repair)
    assert (controller.parent / repair).is_file()
