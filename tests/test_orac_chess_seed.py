"""Verify the immutable CSV seed contract and packaged deployment boundary."""

# Author: Clive Bostock
# Date: 07-Nov-2026
# Description: Exercise seed validation, Unicode packaging and once-only deployment.
# Purpose: Protect author input and user edits across Chess bootstrap upgrades.
# Usage: .venv/bin/python -m pytest tests/test_orac_chess_seed.py

import csv
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins/orac_chess"))
from tools import generate_seed as seed  # noqa: E402

BATCH = seed.ROOT / "seed/batches/2026_11_07_bootstrap"


def write_csv(
    path: Path, columns: tuple[str, ...], rows: list[dict[str, str]], bom: bool = False
) -> None:
    """Write realistic CSV, including quoted prose and optional BOM."""
    with path.open("w", encoding="utf-8-sig" if bom else "utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, columns)
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def batch(tmp_path: Path) -> Path:
    """Provide an isolated empty versioned batch."""
    path = tmp_path / "test_batch"
    path.mkdir()
    write_csv(path / "videos.csv", seed.VIDEO_REQUIRED + seed.VIDEO_OPTIONAL, [])
    write_csv(path / "openings.csv", seed.OPENING_COLUMNS, [])
    write_csv(path / "gambits.csv", seed.GAMBIT_COLUMNS, [])
    return path


def video(**changes: str) -> dict[str, str]:
    """Return a minimally valid video input with optional overrides."""
    return {
        "Platform": "YouTube",
        "Creator": "  Teacher  ",
        "Title": " A title ",
        "Video URL": "https://www.youtube.com/watch?v=abcdefghijk",
        "Published On": "",
        "Description": "",
        **changes,
    }


def test_real_input_and_hex_round_trip() -> None:
    """The supplied 44 records preserve Unicode/prose and infer no catalogue links."""
    data = seed.load_batch(BATCH)
    assert len(data["videos"]) == 44
    assert len({row["creator"] for row in data["videos"]}) == 6
    assert {row["creator"] for row in data["videos"]} >= {
        "Yellow Rook",
        "ChessTeacher Games",
        "The Chess Giant",
    }
    assert all(
        not row["published_on"] and not row["opening_names"] and not row["gambit_names"]
        for row in data["videos"]
    )
    assert all(row["title"] == row["title"].strip() for row in data["videos"])
    descriptions = [row["description"] for row in data["videos"] if row["description"]]
    assert len(descriptions) == 2
    assert any("Budapest" in text for text in descriptions)
    assert any("Grand Prix" in text for text in descriptions)
    sql = seed.generate(BATCH)
    chunks = re.findall(r"hextoraw\('([0-9a-f]+)'\)", sql)
    decoded = "".join(bytes.fromhex(chunk).decode("utf-8") for chunk in chunks)
    assert json.loads(decoded) == data
    assert any(ord(char) > 127 for char in decoded)
    assert seed.generate(BATCH) == sql


@pytest.mark.parametrize(
    "url",
    [
        "https://youtu.be/abcdefghijk",
        "https://youtube.com/shorts/abcdefghijk",
        "http://youtube.com/embed/abcdefghijk",
        "https://youtube.com/watch?v=abcdefghijk&t=1",
    ],
)
def test_youtube_url_forms(batch: Path, url: str) -> None:
    """Recognised URL forms resolve the same stable identity."""
    write_csv(
        batch / "videos.csv",
        seed.VIDEO_REQUIRED + seed.VIDEO_OPTIONAL,
        [video(**{"Video URL": url})],
    )
    row = seed.load_batch(batch)["videos"][0]
    assert row["external_video_id"] == "abcdefghijk"
    assert row["creator"] == "Teacher" and row["title"] == "A title"


@pytest.mark.parametrize(
    ("changes", "column"),
    [
        ({"Video URL": "ftp://youtube.com/watch?v=abcdefghijk"}, "Video URL"),
        (
            {"Video URL": "https://youtube.com/watch?v=abcdefghijk&v=abcdefghijk"},
            "Video URL",
        ),
        ({"Video URL": "https://youtube.com/watch?v=short"}, "Video URL"),
        ({"Video URL": "https://youtube.com.evil/watch?v=abcdefghijk"}, "Video URL"),
        ({"External Video Id": "different12"}, "External Video Id"),
        ({"Platform": "Other"}, "External Video Id"),
        ({"Title": " "}, "Title"),
        ({"Title": "x" * 501}, "Title"),
        ({"Creator": "x" * 301}, "Creator"),
        ({"Platform": "x" * 51}, "Platform"),
        ({"Video URL": "https://x/" + "a" * 2048}, "Video URL"),
        ({"Published On": "2026-02-29"}, "Published On"),
        ({"Published On": "2026-1-01"}, "Published On"),
        ({"Duration Seconds": "0"}, "Duration Seconds"),
        ({"Duration Seconds": "-1"}, "Duration Seconds"),
        ({"Duration Seconds": "1.5"}, "Duration Seconds"),
        ({"Duration Seconds": "10000000000"}, "Duration Seconds"),
        ({"Opening Names": "One||Two"}, "Opening Names"),
        ({"Gambit Names": "One|One"}, "Gambit Names"),
    ],
)
def test_bad_video_has_location(
    batch: Path, changes: dict[str, str], column: str
) -> None:
    """Invalid scalar values fail with actionable file, row and column context."""
    write_csv(
        batch / "videos.csv",
        seed.VIDEO_REQUIRED + seed.VIDEO_OPTIONAL,
        [video(**changes)],
    )
    with pytest.raises(ValueError, match=rf"videos.csv: row 2, column {column}"):
        seed.load_batch(batch)


def test_csv_prose_bom_newlines_and_inert_sql(batch: Path) -> None:
    """Standard CSV prose and SQL-like text stay inert and lossless."""
    prose = '  café ♞, "quoted"\nsecond line; /\n--rollback delete from chess_video; &name  '
    write_csv(
        batch / "videos.csv",
        seed.VIDEO_REQUIRED + seed.VIDEO_OPTIONAL,
        [
            video(
                **{
                    "Description": prose,
                    "Published On": "2024-02-29",
                    "Duration Seconds": "9999999999",
                }
            )
        ],
        True,
    )
    assert seed.load_batch(batch)["videos"][0]["description"] == prose
    assert prose not in seed.generate(batch)


@pytest.mark.parametrize(
    "header",
    [
        "Platform,Creator,Title,Video URL,Published On,Description,Unknown",
        "Platform,Creator,Title,Video URL,Published On,Description,Title",
        "Platform,Creator,Title,Video URL,Description",
    ],
)
def test_bad_headers(batch: Path, header: str) -> None:
    """Unknown, duplicate and missing columns are rejected."""
    (batch / "videos.csv").write_text(header + "\n")
    with pytest.raises(ValueError, match="row 1, column header"):
        seed.load_batch(batch)


@pytest.mark.parametrize(
    "body",
    [
        'YouTube,Teacher,"unfinished',
        'YouTube,Teacher,"bad"tail,a,b,c\n',
        "YouTube,Teacher\n",
        'YouTube,Tea"cher,a,b,c,d\n',
    ],
)
def test_malformed_csv(batch: Path, body: str) -> None:
    """Broken quoting and record width are rejected before SQL generation."""
    (batch / "videos.csv").write_text(",".join(seed.VIDEO_REQUIRED) + "\n" + body)
    with pytest.raises(ValueError, match="videos.csv: row"):
        seed.load_batch(batch)


def test_duplicate_video_identity(batch: Path) -> None:
    """Alternate YouTube URL spellings cannot create duplicate identities."""
    write_csv(
        batch / "videos.csv",
        seed.VIDEO_REQUIRED + seed.VIDEO_OPTIONAL,
        [video(), video(**{"Video URL": "https://youtu.be/abcdefghijk"})],
    )
    with pytest.raises(ValueError, match="duplicate platform/video identity"):
        seed.load_batch(batch)


def test_catalogue_order_lists_and_external_names(batch: Path) -> None:
    """Forward parent references and many-to-many lists remain explicit and ordered."""
    write_csv(
        batch / "openings.csv",
        seed.OPENING_COLUMNS,
        [
            {
                "name": "Child",
                "parent_opening_name": "Parent",
                "eco_codes": "A00|E99",
                "aliases": "First|Second",
                "mainline_name": "Main",
                "mainline_pgn": "1. e4 e5 *",
                "mainline_annotation": " prose ",
            },
            {
                "name": "Parent",
                "opening_type": "SYSTEM",
                "parent_opening_name": "Existing database name",
            },
        ],
    )
    write_csv(
        batch / "gambits.csv",
        seed.GAMBIT_COLUMNS,
        [{"name": "Gambit", "opening_names": "Parent|Child"}],
    )
    data = seed.load_batch(batch)
    assert data["openings"][0]["eco_codes"] == ["A00", "E99"]
    assert data["openings"][0]["aliases"] == ["First", "Second"]
    assert data["gambits"][0]["opening_names"] == ["Parent", "Child"]
    assert data["openings"][0]["mainline_annotation"] == " prose "


@pytest.mark.parametrize(
    "row",
    [
        {"name": "A", "parent_opening_name": "A"},
        {"name": "A", "eco_codes": "F00"},
        {"name": "A", "aliases": "x|x"},
        {"name": "A|B"},
        {"name": "A", "opening_type": "GAMBIT"},
        {"name": "A", "mainline_pgn": "1.e4 *"},
        {"name": "A", "mainline_name": "Main"},
        {"name": "A", "starting_fen": "fen"},
        {"name": "A", "mainline_annotation": "note"},
        {"name": "A", "mainline_pgn": "1.e4 *", "mainline_name": "x" * 201},
        {
            "name": "A",
            "mainline_pgn": "1.e4 *",
            "mainline_name": "Main",
            "starting_fen": "x" * 201,
        },
    ],
)
def test_catalogue_validation(batch: Path, row: dict[str, str]) -> None:
    """Catalogue errors cannot become silent omissions or inferred data."""
    write_csv(batch / "openings.csv", seed.OPENING_COLUMNS, [row])
    with pytest.raises(ValueError, match="openings.csv: row 2, column"):
        seed.load_batch(batch)


def test_indirect_parent_cycle_and_duplicate_names(batch: Path) -> None:
    """Cycles and repeated exact catalogue identities are rejected."""
    for rows in [
        [
            {"name": "A", "parent_opening_name": "B"},
            {"name": "B", "parent_opening_name": "A"},
        ],
        [{"name": "A"}, {"name": " A "}],
    ]:
        write_csv(batch / "openings.csv", seed.OPENING_COLUMNS, rows)
        with pytest.raises(ValueError):
            seed.load_batch(batch)


def test_once_only_controller_and_check() -> None:
    """Install and upgrade reach the immutable seed once, following compiled APIs."""
    controller = seed.ROOT / "db/liquibase/pluginController.xml"
    includes = [node.attrib["file"] for node in ET.parse(controller).getroot()]
    assert includes.index("controllers/12_seed_batches.xml") > includes.index(
        "controllers/11_admin_compile.xml"
    )
    sql = (
        seed.ROOT / "db/schema/seed_data/chess_batch_2026_11_07_bootstrap.sql"
    ).read_text()
    assert sql == seed.generate(BATCH)
    assert "runAlways:" not in sql and "runOnChange:" not in sql
    assert "--rollback empty" in sql
    assert "savepoint chess_seed_batch" in sql and "rollback to chess_seed_batch" in sql
    assert not re.search(
        r"\b(insert into|update orac_chess|delete from|commit;|execute immediate)\b",
        sql,
        re.I,
    )
    result = subprocess.run(
        [sys.executable, str(seed.ROOT / "tools/generate_seed.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_non_youtube_and_optional_fields(batch: Path) -> None:
    """Other platforms require explicit IDs and optional creator may remain blank."""
    write_csv(
        batch / "videos.csv",
        seed.VIDEO_REQUIRED + seed.VIDEO_OPTIONAL,
        [
            video(
                **{
                    "Platform": "Other",
                    "External Video Id": "  external-1  ",
                    "Creator": "",
                    "Video URL": "https://example.test/video",
                    "Duration Seconds": "1",
                }
            )
        ],
    )
    row = seed.load_batch(batch)["videos"][0]
    assert (
        row["platform"],
        row["external_video_id"],
        row["creator"],
        row["duration_seconds"],
    ) == ("Other", "external-1", "", 1)


def test_large_pgn_is_packaged_losslessly(batch: Path) -> None:
    """A legal-sized long PGN never crosses a varchar2-sized packaging boundary."""
    pgn = "1.e4 {" + "Unicode ♞ " * 15000 + "} e5 *"
    write_csv(
        batch / "openings.csv",
        seed.OPENING_COLUMNS,
        [{"name": "Long line", "mainline_name": "Main", "mainline_pgn": pgn}],
    )
    sql = seed.generate(batch)
    decoded = "".join(
        bytes.fromhex(part).decode("utf-8")
        for part in re.findall(r"hextoraw\('([0-9a-f]+)'\)", sql)
    )
    assert json.loads(decoded)["openings"][0]["mainline_pgn"] == pgn


def test_check_detects_stale_output_without_writing(batch: Path) -> None:
    """Check mode fails closed on stale SQL and preserves the review artefact."""
    output = batch / "output.sql"
    output.write_text("stale")
    result = subprocess.run(
        [
            sys.executable,
            str(seed.ROOT / "tools/generate_seed.py"),
            "--batch",
            str(batch),
            "--output",
            str(output),
            "--check",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert output.read_text() == "stale"


def test_acceptance_is_generated_from_actual_runtime() -> None:
    """The opt-in DB harness stays synchronised with runtime fixes and fixtures."""
    result = subprocess.run(
        [
            sys.executable,
            str(seed.ROOT / "tools/generate_seed_acceptance.py"),
            "--check",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    sql = (seed.ROOT / "db/acceptance/verify_seed_runtime.sql").read_text()
    assert sql.count("savepoint chess_seed_batch;") == 5
    assert "Requires explicit isolated seed acceptance opt-in" in sql


def test_packaged_generators_need_no_declared_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Host installation accepts every packaged tool with the empty dependency contract."""
    monkeypatch.syspath_prepend(str(ROOT / "src"))
    from model.plugin_dependencies import validate_declared_imports

    validate_declared_imports(seed.ROOT, (), plugin_id="orac_chess")


def test_host_import_scanner_rejects_generator_dependency_regression(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Undeclared third-party and bare local tool imports remain detectable by the host."""
    monkeypatch.syspath_prepend(str(ROOT / "src"))
    from model import plugin_dependencies

    plugin = tmp_path / "fixture_plugin"
    tools = plugin / "tools"
    tools.mkdir(parents=True)
    (tools / "__init__.py").write_text("")
    (tools / "generate_seed.py").write_text("import logging\n")
    (tools / "generate_seed_acceptance.py").write_text(
        "from generate_seed import generate\nfrom loguru import logger\n"
    )
    monkeypatch.setattr(
        plugin_dependencies.metadata,
        "packages_distributions",
        lambda: {"generate_seed": ["generate-seed"], "loguru": ["loguru"]},
    )
    with pytest.raises(plugin_dependencies.PluginDependencyError) as error:
        plugin_dependencies.validate_declared_imports(
            plugin, (), plugin_id="fixture_plugin"
        )
    assert "generate_seed" in str(error.value)
    assert "loguru" in str(error.value)
    (tools / "generate_seed_acceptance.py").write_text(
        "from tools.generate_seed import generate\nimport logging\n"
    )
    plugin_dependencies.validate_declared_imports(
        plugin, (), plugin_id="fixture_plugin"
    )


def test_optional_eco_fields_use_post_extension_runtime(batch: Path) -> None:
    """New optional gambit and mainline codes use the additive API contract."""
    write_csv(
        batch / "gambits.csv",
        seed.GAMBIT_COLUMNS + ("eco_codes", "mainline_eco_codes"),
        [{"name": "Vienna Gambit", "eco_codes": "C25|C29", "mainline_eco_codes": "C29", "mainline_pgn": "1.e4 *", "mainline_name": "Main"}],
    )
    data = seed.load_batch(batch)
    assert data["gambits"][0]["eco_codes"] == ["C25", "C29"]
    assert data["gambits"][0]["mainline_eco_codes"] == ["C29"]
    assert seed.is_eco_aware(batch)
    rendered = seed.generate(batch)
    assert "save_gambit_with_eco" in rendered
    assert "save_variation_with_eco" in rendered
    assert not seed.is_eco_aware(BATCH)
    controller = seed.ROOT / "db/liquibase/controllers/14_eco_relationships.xml"
    assert controller.read_text().index("chess_variation_api_eco.sql") < controller.read_text().index(
        "15_eco_seed_batches.xml"
    )
