"""Protect complete, reproducible ECO reference data and its install boundary."""

# Author: Clive Bostock
# Date: 07-Nov-2026
# Description: Verify pinned ECO aggregation and packaged deployment.
# Purpose: Prevent incomplete codes, Unicode loss and accidental reference overwrites.
# Usage: .venv/bin/python -m pytest tests/test_orac_chess_eco.py

import csv
import hashlib
import json
import re
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins/orac_chess"))
from tools import generate_eco_reference as eco  # noqa: E402


def test_complete_source_names_and_unicode() -> None:
    """Every description retains all distinct source names, including Vienna variants."""
    reference = eco.load_reference()
    assert len(reference) == 500
    expected: dict[str, set[str]] = {}
    rows = 0
    for path in eco.SOURCE.glob("*.tsv"):
        with path.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                expected.setdefault(row["eco"], set()).add(row["name"])
                rows += 1
    assert rows == 3865
    assert reference == {
        code: "\n".join(sorted(names)) for code, names in sorted(expected.items())
    }
    assert all("Vienna" in reference[f"C{number}"] for number in range(25, 30))
    assert any(ord(char) > 127 for text in reference.values() for char in text)


def test_outputs_reproduce_and_preserve_existing_rows() -> None:
    """Packaged CSV and once-only SQL match validated source without overwriting edits."""
    reference = eco.load_reference()
    assert eco.CSV_PATH.read_bytes() == eco.render_csv(reference).encode()
    sql = eco.render_sql(reference)
    assert eco.SQL_PATH.read_bytes() == sql.encode()
    assert sql.count("insert into orac_chess.chess_eco_code") == 500
    assert sql.count("where not exists") == 500
    assert "runOnChange" not in sql and "runAlways" not in sql
    assert "\n  commit" not in sql and "--rollback empty" in sql
    assert "update orac_chess" not in sql.lower()
    decoded: dict[str, str] = {}
    for block in sql.split("  l_description := empty_clob();")[1:]:
        code = re.search(r"select '([A-E][0-9]{2})', l_description", block).group(1)
        decoded[code] = "".join(
            bytes.fromhex(chunk).decode("utf-8")
            for chunk in re.findall(r"hextoraw\('([0-9A-F]+)'\)", block)
        )
    assert decoded == reference
    assert "savepoint chess_eco_reference;" in sql
    assert "rollback to chess_eco_reference;" in sql
    with eco.CSV_PATH.open(encoding="utf-8", newline="") as stream:
        assert {
            row["eco_code"]: row["description"] for row in csv.DictReader(stream)
        } == reference


@pytest.mark.parametrize(
    "mutation,error",
    [
        ("hash", "hash mismatch"),
        ("header", "header"),
        ("empty", "Empty"),
        ("code", "Invalid ECO"),
        ("duplicate", "Duplicate"),
        ("missing", "cover every"),
    ],
)
def test_source_rejects_invalid_input(
    tmp_path: Path, mutation: str, error: str
) -> None:
    """Reject corrupt source bytes and invalid rows even when a manifest is refreshed."""
    source = tmp_path / "source"
    shutil.copytree(eco.SOURCE, source)
    path = source / "a.tsv"
    lines = path.read_text(encoding="utf-8").splitlines()
    if mutation == "header":
        lines[0] = "eco\tname\twrong"
    elif mutation == "empty":
        parts = lines[1].split("\t")
        parts[1] = ""
        lines[1] = "\t".join(parts)
    elif mutation == "code":
        lines[1] = "Z99" + lines[1][3:]
    elif mutation == "duplicate":
        lines.append(lines[1])
    elif mutation == "missing":
        lines = [line for line in lines if not line.startswith("A00\t")]
    else:
        lines.append("corrupt")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if mutation != "hash":
        manifest_path = source / "PROVENANCE.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"]["a.tsv"]["sha256"] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match=error):
        eco.load_reference(source)


def test_install_reachability_and_host_import_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The host can package the plugin and install final contracts before compilation."""
    monkeypatch.syspath_prepend(str(ROOT / "src"))
    from model.plugin_dependencies import validate_declared_imports

    validate_declared_imports(eco.ROOT, ("oracledb>=4.0.0,<5.0.0",), plugin_id="orac_chess")
    ns = {"lb": "http://www.liquibase.org/xml/ns/dbchangelog"}
    main = eco.ROOT / "db/liquibase/pluginController.xml"
    includes = ET.parse(main).findall("lb:include", ns)
    paths = [item.attrib["file"] for item in includes]
    dependency_order = [
        "controllers/13_eco_reference.xml",
        "controllers/10_admin_api.xml",
        "controllers/14_eco_relationships.xml",
        "controllers/11_admin_compile.xml",
        "controllers/12_seed_batches.xml",
        "controllers/15_eco_seed_batches.xml",
    ]
    positions = [paths.index(path) for path in dependency_order]
    assert positions == sorted(positions)
    assert paths.count("controllers/15_eco_seed_batches.xml") == 1
    reference = next(item for item in includes if item.attrib["file"] == "controllers/13_eco_reference.xml")
    controller = main.parent / reference.attrib["file"]
    assets = [
        (controller.parent / item.attrib["file"]).resolve()
        for item in ET.parse(controller).findall("lb:include", ns)
    ]
    assert len(assets) == len(set(assets)) == 9
    assert all(path.is_file() for path in assets)
    assert assets.index(eco.ROOT / "db/schema/seed_data/chess_eco_code.sql") > next(
        i for i, path in enumerate(assets) if path.parent.name == "constraint_pk"
    )
    assert assets.index(eco.ROOT / "db/schema/seed_data/chess_eco_code.sql") < next(
        i for i, path in enumerate(assets) if path.parent.name == "view"
    )


def test_additive_relationship_controller_and_atomic_wrappers() -> None:
    """The extension compiles final ECO contracts and retains independent save paths."""
    ns = {"lb": "http://www.liquibase.org/xml/ns/dbchangelog"}
    root = eco.ROOT
    controller = root / "db/liquibase/controllers/14_eco_relationships.xml"
    assets = [
        (controller.parent / item.attrib["file"]).resolve()
        for item in ET.parse(controller).findall("lb:include", ns)
    ]
    assert all(path.is_file() for path in assets)
    assert assets[0].name == "chess_eco_preflight.sql"
    assert assets[-1].name == "chess_admin_eco_compile.sql"
    assert not any(path.name == "15_eco_seed_batches.xml" for path in assets)
    ddl = "\n".join(path.read_text() for path in assets if path.suffix == ".sql")
    for subject, abbrev in (("gambit", "gec"), ("variation", "vec")):
        assert f"primary key ({subject}_id, eco_code)" in ddl
        assert f"on orac_chess.chess_{subject}_eco (eco_code, {subject}_id)" in ddl
        assert f"grant select on orac_chess.chess_{subject}_eco_v to orac_apx_pub" in ddl
        assert f"constraint chs_{abbrev}_eco_fk foreign key (eco_code)" in ddl
    assert "expectedResult:500 select count(*) from orac_chess.chess_eco_code" in ddl
    tapi = (root / "db/schema/package_body/chess_admin_tapi_eco.sql").read_text()
    for subject in ("gambit", "variation"):
        combined = tapi.split(f"  procedure save_{subject}_with_eco(", 1)[1].split(
            f"  procedure delete_{subject}(", 1
        )[0]
        assert combined.index("select count(*) into l_count from chess_eco_code") < combined.index(
            f"    save_{subject}("
        ) < combined.index(f"    delete from chess_{subject}_eco")
        assert f"rollback to chess_{subject}_and_eco" in combined
        ordinary = tapi.split(f"  procedure save_{subject}(", 1)[1].split(
            f"  procedure save_{subject}_with_eco(", 1
        )[0]
        assert f"chess_{subject}_eco" not in ordinary
