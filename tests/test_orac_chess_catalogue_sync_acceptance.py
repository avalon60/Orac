"""Validate legal, isolated fixtures used by the live rollback sync acceptance."""

# Author: Clive Bostock
# Date: 11-Nov-2026
# Description: Check acceptance JSON identities, references and legal branches.
# Purpose: Prevent malformed fixtures from obscuring live reconciliation failures.
# Usage: pytest tests/test_orac_chess_catalogue_sync_acceptance.py

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "plugins/orac_chess/db/acceptance/verify_catalogue_sync.sql"
GENERATOR = ROOT / "plugins/orac_chess/tools/generate_comprehensive_catalogue.py"
SPEC = importlib.util.spec_from_file_location("catalogue_fixture_validator", GENERATOR)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _fixture() -> dict:
    match = re.search(r"return to_clob\(q'~(\{.*?\})~'\);", HARNESS.read_text(), re.S)
    assert match, "Live acceptance must expose its actual baseline JSON fixture"
    return json.loads(match.group(1))


def test_live_sync_fixture_has_distinct_owned_keys_and_resolvable_contexts():
    """Every test entity and relationship must resolve within the fixture."""
    payload = _fixture()
    entries = payload["entries"]
    by_key = {entry["key"]: entry for entry in entries}
    assert len(by_key) == len(entries) == 6
    assert all(key.startswith("sync_accept_") for key in by_key)
    assert all(
        entry["desired"]["fields"]["name"].startswith("__SYNC_ACCEPT_")
        for entry in entries
    )
    for entry in entries:
        fields = entry["desired"]["fields"]
        if entry["kind"] == "VARIATION":
            assert by_key[fields["owner_key"]]["kind"] == fields["owner_kind"]
            if fields["parent_key"]:
                parent = by_key[fields["parent_key"]]
                assert parent["kind"] == "VARIATION"
                assert parent["desired"]["fields"]["owner_key"] == fields["owner_key"]
        for key in entry["desired"]["relationships"].get("opening_keys", []):
            assert by_key[key]["kind"] == "OPENING"
        assert all(
            re.fullmatch(r"[A-E][0-9]{2}", code)
            for code in entry["desired"]["relationships"]["eco_codes"]
        )


def test_live_sync_fixture_replays_with_production_continuation_policy():
    """The baseline branch is legal and its mutation remains a legal user edit."""
    entries = _fixture()["entries"]
    lines = [entry for entry in entries if entry["kind"] == "VARIATION"]
    parsed = MODULE.replay([entry["desired"]["fields"]["pgn"] for entry in lines])
    histories = {entry["key"]: result["moves"] for entry, result in zip(lines, parsed)}
    for entry in lines:
        fields = entry["desired"]["fields"]
        if fields["parent_key"]:
            parent = histories[fields["parent_key"]]
            child = histories[entry["key"]]
            assert fields["line_kind"] == "CONTINUATION"
            assert child[: len(parent)] == parent
            assert len(child) > len(parent) == fields["branch_ply"]
    main, edited = MODULE.replay(["1. e4 *", "1. e4 c5 *"])
    assert edited["moves"][: len(main["moves"])] == main["moves"]
    with pytest.raises(subprocess.CalledProcessError):
        MODULE.replay(["1. e4 e5 2. Ke3 *"])
