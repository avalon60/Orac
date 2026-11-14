"""Check the pinned comprehensive catalogue and sequence-based hierarchy."""

# Author: Clive Bostock
# Date: 10-Nov-2026
# Description: Exercise legal source generation and additive catalogue invariants.
# Purpose: Detect mapping, provenance and hierarchy regressions before packaging.
# Usage: pytest tests/test_orac_chess_comprehensive_catalogue.py

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "plugins/orac_chess/tools/generate_comprehensive_catalogue.py"
SPEC = importlib.util.spec_from_file_location("comprehensive_catalogue", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.fixture(scope="module")
def catalogue():
    """Generate every source row through the production legal-move validator."""
    return MODULE.build_catalogue()


def test_generated_bytes_are_reproducible(catalogue):
    """The checked-in batch must exactly match its offline source transformation."""
    payload, report = catalogue
    assert (MODULE.BATCH / "catalogue.json").read_text() == MODULE._json(payload)
    assert (MODULE.BATCH / "coverage.json").read_text() == MODULE._json(report)
    assert report["source_rows"] == 3865
    assert report["source_names"] == 3177
    assert len(report["eco_assigned"]) == 500
    assert report["eco_unassigned"] == []
    assert report["rejected_invalid_moves"] == []


def test_curated_fields_and_mandatory_identities_are_preserved(catalogue):
    """Source additions must preserve curated identities and user-visible roots."""
    payload, _ = catalogue
    for kind in ("openings", "gambits"):
        owners = {r["name"]: r for r in payload[kind]}
        for old in MODULE._csv(MODULE.CURATED / f"{kind}.csv"):
            new = owners[old["name"]]
            for field in (
                "description",
                "mainline_name",
                "mainline_pgn",
                "starting_fen",
                "mainline_annotation",
            ):
                assert new[field] == old[field]
            if kind == "openings":
                assert new["opening_type"] == old["opening_type"]
                assert new["parent_opening_name"] == old["parent_opening_name"]
    assert (
        next(r for r in payload["openings"] if r["name"] == "Black Lion")[
            "opening_type"
        ]
        == "SYSTEM"
    )
    assert sum(r["name"] == "Alien Gambit" for r in payload["gambits"]) == 1
    queen = next(r for r in payload["gambits"] if r["name"] == "Queen's Gambit")
    assert {"Queen's Gambit Accepted", "Queen's Gambit Declined"} <= set(
        queen["opening_names"]
    )
    assert not any(r["name"].startswith("Queen's Gambit (") for r in payload["gambits"])


def test_relationships_and_unbounded_hierarchy_are_consistent(catalogue):
    """Every edge must obey the production continuation or divergence contract."""
    payload, report = catalogue
    owners = {
        (kind, r["name"]): r
        for kind, key in [("OPENING", "openings"), ("GAMBIT", "gambits")]
        for r in payload[key]
    }
    branches = {r["key"]: r for r in payload["variations"]}
    assert len(branches) == len(payload["variations"])
    histories = MODULE.replay(
        [r["mainline_pgn"] for r in owners.values()]
        + [r["pgn"] for r in branches.values()]
    )
    moves = {k: h["moves"] for k, h in zip(list(owners) + list(branches), histories)}
    identities = set()
    depths = {}
    for key, row in branches.items():
        owner = (row["owner_type"], row["owner_name"])
        assert owner in owners
        identity = (*owner, row["name"])
        assert identity not in identities
        identities.add(identity)
        parent = owner if row["parent_key"] == "owner-mainline" else row["parent_key"]
        assert parent in moves
        if isinstance(parent, str):
            assert (
                branches[parent]["owner_type"],
                branches[parent]["owner_name"],
            ) == owner
        p, c = moves[parent], moves[key]
        assert MODULE._prefix(p, c) == row["branch_ply"]
        if row["line_kind"] == "CONTINUATION":
            assert len(c) > len(p) == row["branch_ply"]
        else:
            assert row["branch_ply"] < min(len(p), len(c))
        seen = {key}
        ancestor = row["parent_key"]
        while ancestor != "owner-mainline":
            assert ancestor not in seen
            seen.add(ancestor)
            ancestor = branches[ancestor]["parent_key"]
        depths[key] = len(seen)
        assert row["annotation"].strip() and row["eco_codes"]
    assert max(depths.values()) > 2
    assert report["counts"]["existing_variations"] == 190
    assert report["counts"]["new_mainlines"] == 650
    assert report["counts"]["new_branches"] == 3718
    assert report["counts"]["new_variations"] == 4368
    assert report["counts"]["projected_total_variations"] == 4558
    assert report["counts"]["all_parent_child_relationships"] == 3818
    assert report["counts"]["nested_named_parent_relationships"] == 1595
    for row in payload["opening_gambits"]:
        assert ("OPENING", row["opening_name"]) in owners
        assert ("GAMBIT", row["gambit_name"]) in owners


def test_aliases_source_accounting_and_context_qualifications(catalogue):
    """Report every source occurrence while keeping separate named concepts."""
    payload, report = catalogue
    aliases = {}
    canonical = {r["name"] for r in payload["openings"]}
    for row in payload["openings"]:
        for alias in row.get("aliases", []):
            assert alias not in canonical
            assert alias not in aliases
            aliases[alias] = row["name"]
    occurrences = report["source_occurrences"]
    assert (
        len(
            {i["source"] for row in occurrences for i in row["occurrences"]}
            | {r["source"] for r in report["deferred_source_rows"]}
        )
        == 3865
    )
    names = {r["name"] for r in payload["gambits"]}
    assert len([n for n in names if n.startswith("Wing Gambit")]) >= 5
    assert len([n for n in names if n.startswith("Zilbermints Gambit")]) >= 11
    assert all(
        r["description"].strip() for r in payload["openings"] + payload["gambits"]
    )
    assert isinstance(report["transposition_position_groups"], list)
    assert len(
        {
            r["source_key"]
            for r in payload["openings"] + payload["gambits"] + payload["variations"]
        }
    ) == sum(len(payload[k]) for k in ("openings", "gambits", "variations"))


def test_transposition_ignores_clocks_and_ineffective_en_passant():
    """Equal boards reached by distinct legal histories share position identity."""
    first, second = MODULE.replay(["1. Nf3 Nf6 2. g3 g6 *", "1. g3 g6 2. Nf3 Nf6 *"])
    assert first["moves"] != second["moves"]
    assert first["position"] == second["position"]


def test_frozen_identity_survives_a_legal_source_move_correction():
    """A corrected sequence changes content while retaining its released ID."""
    before, after = MODULE.replay(["1. e4 e5 *", "1. e4 c5 *"])
    released = MODULE._key(
        "OPENING", "Fixture Opening", "Fixture Named Line", before["moves"]
    )
    frozen = {
        released: dict(
            owner_type="OPENING",
            owner_name="Fixture Opening",
            concept="Fixture Named Line",
        )
    }
    corrected = MODULE._stable_key(
        "OPENING", "Fixture Opening", "Fixture Named Line", after["moves"], frozen, {}
    )
    assert corrected == released
    assert (
        MODULE._key("OPENING", "Fixture Opening", "Fixture Named Line", after["moves"])
        != released
    )
    assert MODULE._source_hash(
        dict(source_key=released, pgn="1. e4 e5 *")
    ) != MODULE._source_hash(dict(source_key=corrected, pgn="1. e4 c5 *"))
    renamed = "Fixture Renamed Line"
    candidate = MODULE._key("OPENING", "Fixture Opening", renamed, after["moves"])
    assert (
        MODULE._stable_key(
            "OPENING",
            "Fixture Opening",
            renamed,
            after["moves"],
            frozen,
            {candidate: released},
        )
        == released
    )


def test_owner_binding_survives_a_different_shorter_representative():
    """Changing a new owner's representative preserves owner and MAIN IDs."""
    spec = importlib.util.spec_from_file_location(
        "catalogue_sync_owner_fixture", PATH.parent / "generate_catalogue_sync.py"
    )
    sync = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sync)
    old_moves, new_moves = MODULE.replay(["1. e4 e5 2. Nf3 *", "1. e4 c5 *"])
    owner_key = MODULE._key(
        "OPENING", "Fixture Family", "Fixture Family: Longer Line", old_moves["moves"]
    )
    old_owner = dict(
        name="Fixture Family",
        source_key=owner_key,
        description="Fixture source",
        opening_type="OPENING",
        mainline_name="Fixture Main",
        mainline_pgn="1. e4 e5 2. Nf3 *",
    )
    previous = dict(
        source_revision="old", openings=[old_owner], gambits=[], variations=[]
    )
    retained_key = MODULE._owner_key(
        "OPENING",
        "Fixture Family",
        "Fixture Family: Different Short Line",
        new_moves["moves"],
        previous,
        {},
        {},
    )
    assert retained_key == owner_key
    assert (
        MODULE._key(
            "OPENING",
            "Fixture Family",
            "Fixture Family: Different Short Line",
            new_moves["moves"],
        )
        != owner_key
    )
    changed_owner = old_owner | dict(source_key=retained_key, mainline_pgn="1. e4 c5 *")
    changed = previous | dict(source_revision="new", openings=[changed_owner])
    old_entries = sync.normalise(previous)["entries"]
    new_entries = sync.normalise(changed)["entries"]
    assert [row["key"] for row in old_entries] == [row["key"] for row in new_entries]
    assert new_entries[1]["key"] == owner_key + "__main"
    assert old_entries[1]["source_hash"] != new_entries[1]["source_hash"]


def test_new_branch_from_a_prior_owner_representative_has_distinct_identity():
    """An old representative newly stored as a branch cannot reuse its owner ID."""
    moves = MODULE.replay(["1. e4 e5 2. Nf3 *"])[0]["moves"]
    owner = MODULE._key("OPENING", "Fixture Family", "Old Representative", moves)
    branch = MODULE._branch_key(
        owner, owner, "OPENING", "Fixture Family", "Old Representative", moves
    )
    assert branch != owner
    frozen = {
        branch: dict(
            owner_type="OPENING",
            owner_name="Fixture Family",
            concept="Old Representative",
        )
    }
    corrected = MODULE.replay(["1. e4 e5 2. Nc3 *"])[0]["moves"]
    assert (
        MODULE._stable_key(
            "OPENING", "Fixture Family", "Old Representative", corrected, frozen, {}
        )
        == branch
    )
