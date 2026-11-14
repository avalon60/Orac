"""Build a deterministic, legally replayed catalogue from pinned opening sources."""

# Author: Clive Bostock
# Date: 11-Nov-2026
# Description: Transform explicit source mappings into an additive catalogue batch.
# Purpose: Keep source attribution, identities and coverage reproducible offline.
# Usage: python3 plugins/orac_chess/tools/generate_comprehensive_catalogue.py --check

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "vendor/lichess-chess-openings-3ba6b20"
MAPPING = ROOT / "seed/mappings/lichess_families.json"
BATCH = ROOT / "seed/catalogue/2026_11_10_comprehensive_catalogue"
CURATED = ROOT / "seed/batches/2026_11_10_starter_catalogue"


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _key(kind: str, owner: str, concept: str, moves: list[str]) -> str:
    identity = _json([kind, owner, concept, moves]).encode()
    return kind.lower() + "_" + hashlib.sha256(identity).hexdigest()[:32]


def _stable_key(
    kind: str,
    owner: str,
    concept: str,
    moves: list[str],
    frozen: dict[str, dict],
    overrides: dict[str, str],
) -> str:
    candidate = _key(kind, owner, concept, moves)
    if candidate in overrides:
        return overrides[candidate]
    # Empty histories identify preserved curated owner references and links,
    # rather than a source-named sequence in the occurrence registry.
    if moves:
        matches = [
            key
            for key, row in frozen.items()
            if (row["owner_type"], row["owner_name"], row["concept"])
            == (kind, owner, concept)
        ]
        if len(matches) > 1:
            raise ValueError("Frozen source context has multiple identities")
        if matches:
            return matches[0]
    return candidate


def _owner_key(
    kind: str,
    name: str,
    concept: str,
    moves: list[str],
    previous: dict,
    frozen: dict[str, dict],
    overrides: dict[str, str],
) -> str:
    collection = "openings" if kind == "OPENING" else "gambits"
    matches = [
        row["source_key"] for row in previous.get(collection, []) if row["name"] == name
    ]
    if len(matches) > 1:
        raise ValueError("Previous catalogue has duplicate canonical owners")
    return (
        matches[0]
        if matches
        else _stable_key(kind, name, concept, moves, frozen, overrides)
    )


def _branch_key(
    candidate: str,
    owner_key: str,
    kind: str,
    owner: str,
    concept: str,
    moves: list[str],
) -> str:
    # An owner's original representative was provenance, not an installed branch.
    # If it becomes a branch later, allocate its distinct branch identity once.
    return (
        _key(kind + "_branch", owner, concept, moves)
        if candidate == owner_key
        else candidate
    )


def _source_hash(record: dict) -> str:
    fields = {
        key: value
        for key, value in record.items()
        if key not in ("source_key", "key", "is_existing")
    }
    return hashlib.sha256(_json(fields).encode()).hexdigest()


def replay(pgns: list[str]) -> list[dict]:
    """Validate PGNs with the production adapter and return UCI histories.

    Args:
        pgns: Complete initial-position PGNs with terminal results.

    Returns:
        Parsed legal histories and positions in input order.
    """
    script = (
        "import {Chess} from "
        + json.dumps((ROOT / "vendor/chess.js-1.4.0/chess.mjs").as_uri())
        + ";import {parse} from "
        + json.dumps((ROOT / "tools/mle/validator.mjs").as_uri())
        + ";"
        "let input='';for await(const c of process.stdin)input+=c;"
        'process.stdout.write(JSON.stringify(JSON.parse(input).map(p=>{const r=parse(p,1);r.position=new Chess(r.positions.at(-1)).fen().split(" ").slice(0,4).join(" ");return r;})));'
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        input=json.dumps(pgns),
        text=True,
        capture_output=True,
        check=True,
        timeout=180,
    )
    return json.loads(result.stdout)


def _csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _prefix(a: list[str], b: list[str]) -> int:
    return next(
        (i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b))
    )


def build_catalogue(
    source: Path = SOURCE,
    mapping_path: Path = MAPPING,
    output: Path = BATCH,
    previous_catalogue: Path | None = None,
    identities: Path | None = None,
) -> tuple[dict, dict]:
    """Build the additive batch and its complete source-accounting report.

    Args:
        source: Pinned bundled dataset directory with its hash manifest.
        mapping_path: Reviewed family, alias and identity override mappings.
        output: Intended new release directory; used for its batch identity.
        previous_catalogue: Released owner bindings to retain across representative changes.
        identities: Released source context registry; defaults beside the previous catalogue.

    Returns:
        Catalogue payload and coverage/provenance report.

    Raises:
        ValueError: If pinned bytes, mappings or catalogue invariants differ.
    """
    provenance = json.loads((source / "PROVENANCE.json").read_text())
    for filename, details in provenance["files"].items():
        if (
            hashlib.sha256((source / filename).read_bytes()).hexdigest()
            != details["sha256"]
        ):
            raise ValueError(f"Pinned source hash differs: {filename}")
    mapping = json.loads(mapping_path.read_text())

    previous_path = previous_catalogue or output / "catalogue.json"
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
    identity_path = identities or previous_path.parent / "SOURCE_IDENTITIES.json"
    if (
        identities is not None or previous_path.exists()
    ) and not identity_path.exists():
        raise ValueError(
            "Released source identity registry is required for an existing catalogue"
        )
    frozen = json.loads(identity_path.read_text()) if identity_path.exists() else {}

    def stable_key(kind: str, owner: str, concept: str, moves: list[str]) -> str:
        return _stable_key(
            kind, owner, concept, moves, frozen, mapping.get("source_key_overrides", {})
        )

    sources: list[dict] = []
    row: dict
    for path in sorted(source.glob("?.tsv")):
        with path.open(encoding="utf-8", newline="") as stream:
            for number, row in enumerate(csv.DictReader(stream, delimiter="\t"), 2):
                row.update(
                    source=f"{path.name}:{number}",
                    family=row["name"].split(":")[0],
                    pgn=row["pgn"].strip() + " *",
                )
                sources.append(row)
    if set(mapping["families"]) != {s["family"] for s in sources}:
        raise ValueError("Every source top label requires an explicit mapping")
    parsed = replay([s["pgn"] for s in sources])
    for row, history in zip(sources, parsed):
        row.update(
            moves=history["moves"],
            position=history["position"],
            opening=mapping["families"][row["family"]],
        )
    all_sources = sources
    deferred = [
        dict(
            source=r["source"],
            name=r["name"],
            eco=r["eco"],
            pgn=r["pgn"],
            reason="Unresolved broad Lion Defense / Black Lion mapping: insufficient compatible root moves",
        )
        for r in sources
        if r["name"] in mapping.get("deferred_names", [])
    ]
    sources = [r for r in sources if r["name"] not in mapping.get("deferred_names", [])]
    openings, gambits = _csv(CURATED / "openings.csv"), _csv(CURATED / "gambits.csv")
    curated_links = {
        (a, g["name"])
        for g in gambits
        for a in g.get("opening_names", "").split("|")
        if a
    }
    existing_variations = _csv(CURATED / "variations.csv")
    for kind, owner_rows in [("OPENING", openings), ("GAMBIT", gambits)]:
        for row in owner_rows:
            row.update(
                is_existing=True,
                source_key=stable_key(kind, row["name"], row["name"], []),
            )
            for column in (
                "eco_codes",
                "mainline_eco_codes",
                "aliases",
                "opening_names",
            ):
                if column in row:
                    row[column] = row[column].split("|") if row[column] else []
    opening_by_name = {r["name"]: r for r in openings}
    gambit_by_name = {r["name"]: r for r in gambits}
    contexts: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in sources:
        contexts[("OPENING", row["opening"])].append(row)
    # Source syntax uses colon for the family, comma for named descendants.
    candidates = defaultdict(list)
    for row in sources:
        segments = re.split(r": |, ", row["name"])
        for segment in segments:
            name = re.sub(r" (Accepted|Declined)$", "", segment)
            if re.fullmatch(r".+(?:Gambit|Countergambit)", name):
                candidates[
                    (mapping["gambit_synonyms"].get(name, name), row["opening"])
                ].append(row)
    by_concept = defaultdict(set)
    for name, family in candidates:
        by_concept[name].add(family)
    for (concept, family), rows in sorted(candidates.items()):
        if concept in gambit_by_name:
            preferred = mapping["curated_contexts"].get(concept)
            existing = gambit_by_name[concept]
            known = set(existing.get("opening_names", []))
            qualifies = (
                len(by_concept[concept]) > 1
                and family != preferred
                and family not in known
            )
        else:
            qualifies = len(by_concept[concept]) > 1
        if family in mapping.get("shared_gambit_contexts", {}).get(concept, []):
            qualifies = False
        name = f"{concept} ({family})" if qualifies else concept
        contexts[("GAMBIT", name)].extend(rows)

    def owner_record(kind: str, name: str, rows: list[dict]) -> dict:
        representative = min(
            rows, key=lambda r: (len(r["moves"]), r["moves"], r["name"])
        )
        row = dict(
            name=name,
            description=f"{name}: source-defined line {representative['name']}; moves {representative['pgn']}",
            mainline_name=f"{name} Main Line",
            mainline_pgn=representative["pgn"],
            starting_fen="",
            mainline_annotation=f"Canonical shortest source line for {name}: {representative['name']}.",
            mainline_eco_codes=[representative["eco"]],
            eco_codes=sorted({r["eco"] for r in rows}),
            is_existing=False,
            source_key=_owner_key(
                kind,
                name,
                representative["name"],
                representative["moves"],
                previous,
                frozen,
                mapping.get("source_key_overrides", {}),
            ),
        )
        if kind == "OPENING":
            row.update(
                opening_type=mapping.get("opening_types", {}).get(name, "OPENING"),
                parent_opening_name="",
                aliases=mapping["opening_aliases"].get(name, []),
            )
        else:
            row["opening_names"] = sorted({r["opening"] for r in rows})
        return row

    for (kind, name), rows in sorted(contexts.items()):
        owner_map = opening_by_name if kind == "OPENING" else gambit_by_name
        if name not in owner_map:
            owner_map[name] = owner_record(kind, name, rows)
        owner_map[name]["eco_codes"] = sorted(
            set(owner_map[name]["eco_codes"]) | {r["eco"] for r in rows}
        )
        if kind == "GAMBIT":
            owner_map[name]["opening_names"] = sorted(
                set(owner_map[name]["opening_names"]) | {r["opening"] for r in rows}
            )
    owners = {("OPENING", k): v for k, v in opening_by_name.items()}
    owners.update({("GAMBIT", k): v for k, v in gambit_by_name.items()})
    roots = replay([v["mainline_pgn"] for v in owners.values()])
    for owner, history in zip(owners.values(), roots):
        owner["_moves"] = history["moves"]
    existing_ids = {
        (v["owner_type"], v["owner_name"], v["name"]) for v in existing_variations
    }
    variations, omitted, occurrences = [], [], []
    for identity, rows in sorted(contexts.items()):
        kind, owner_name = identity
        owner = owners[identity]
        concepts: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            concepts[row["name"]].append(row)
        branches: list[dict] = []
        for concept, instances in sorted(concepts.items()):
            row = min(instances, key=lambda r: (len(r["moves"]), r["moves"]))
            key = stable_key(kind, owner_name, concept, row["moves"])
            occurrences.append(
                dict(
                    key=key,
                    owner_type=kind,
                    owner_name=owner_name,
                    concept=concept,
                    canonical_source=row["source"],
                    occurrences=[
                        dict(
                            source=r["source"],
                            eco=r["eco"],
                            moves=r["moves"],
                            position=r["position"],
                        )
                        for r in instances
                    ],
                )
            )
            reason = None
            if (kind, owner_name, concept) in existing_ids:
                reason = "preserved_existing_variation"
            elif row["moves"] == owner["_moves"]:
                reason = "represented_by_owner_mainline"
            elif concept == row["family"] and kind == "OPENING":
                reason = "represented_by_opening_family"
            elif _prefix(row["moves"], owner["_moves"]) == len(row["moves"]):
                reason = "shorter_prefix_of_preserved_mainline"
            if reason:
                omitted.append(
                    dict(
                        key=key,
                        source=row["source"],
                        reason=reason,
                        owner_type=kind,
                        owner_name=owner_name,
                        name=concept,
                    )
                )
                continue
            key = _branch_key(
                key, owner["source_key"], kind, owner_name, concept, row["moves"]
            )
            occurrences[-1]["key"] = key
            branches.append(
                dict(
                    key=key,
                    owner_type=kind,
                    owner_name=owner_name,
                    name=concept,
                    pgn=row["pgn"],
                    annotation=f"{concept}; source move sequence {row['pgn']}",
                    eco_codes=sorted({i["eco"] for i in instances}),
                    _moves=row["moves"],
                )
            )
        # Source-named ancestor must have a compatible sequence; no artificial depth cap.
        branches.sort(key=lambda r: (len(r["_moves"]), r["name"], r["key"]))
        done: list[dict] = []
        for branch in branches:
            ancestors = [
                p
                for p in done
                if branch["name"].startswith(p["name"] + ", ")
                and _prefix(p["_moves"], branch["_moves"]) == len(p["_moves"])
                and len(p["_moves"]) < len(branch["_moves"])
            ]
            parent = max(
                ancestors,
                key=lambda p: (len(p["name"]), len(p["_moves"])),
                default=None,
            )
            moves = parent["_moves"] if parent else owner["_moves"]
            ply = _prefix(moves, branch["_moves"])
            branch.update(
                parent_key=parent["key"] if parent else "owner-mainline",
                parent_pgn=parent["pgn"] if parent else owner["mainline_pgn"],
                line_kind="CONTINUATION" if ply == len(moves) else "ALTERNATIVE",
                branch_ply=ply,
                source_key=branch["key"],
            )
            done.append(branch)
        variations.extend(done)
    all_codes = {f"{letter}{number:02d}" for letter in "ABCDE" for number in range(100)}
    assigned = {r["eco"] for r in sources}
    links = sorted(
        {
            (family, name)
            for name, owner in gambit_by_name.items()
            for family in owner["opening_names"]
        }
    )
    sequence_groups, position_groups = defaultdict(list), defaultdict(list)
    for row in sources:
        sequence_groups[" ".join(row["moves"])].append(row["source"])
        position_groups[row["position"]].append(row["source"])
    report = dict(
        source_rows=len(all_sources),
        mapped_source_rows=len(sources),
        deferred_source_rows=deferred,
        source_names=len({r["name"] for r in all_sources}),
        source_top_labels=len(mapping["families"]),
        source_revision=provenance["commit"],
        source_accounting_summary=dict(
            legally_replayed_source_rows=len(all_sources),
            deferred_unresolved_source_rows=len(deferred),
            shorter_prefix_named_branch_omissions=sum(
                r["reason"] == "shorter_prefix_of_preserved_mainline" for r in omitted
            ),
            represented_family_concepts=sum(
                r["reason"] == "represented_by_opening_family" for r in omitted
            ),
            represented_owner_mainline_concepts=sum(
                r["reason"] == "represented_by_owner_mainline" for r in omitted
            ),
            represented_prior_variation_concepts=sum(
                r["reason"] == "preserved_existing_variation" for r in omitted
            ),
            distinction="Named-branch omissions count owner/concept contexts; family/mainline/prior-variation contexts are represented, not rejected source data",
        ),
        duplicate_name_summary=dict(
            repeated_name_groups=sum(
                n > 1 for n in Counter(r["name"] for r in all_sources).values()
            ),
            source_rows_in_repeated_name_groups=sum(
                n for n in Counter(r["name"] for r in all_sources).values() if n > 1
            ),
            additional_occurrences_beyond_first=sum(
                n - 1 for n in Counter(r["name"] for r in all_sources).values() if n > 1
            ),
            handling="Canonical shortest/UCI representative per owner and source concept; all occurrences retained in provenance, distinct named concepts never position-merged",
        ),
        counts=dict(
            openings=len(opening_by_name),
            gambits=len(gambit_by_name),
            new_branches=len(variations),
            new_mainlines=sum(not row["is_existing"] for row in owners.values()),
            new_variations=len(variations)
            + sum(not row["is_existing"] for row in owners.values()),
            existing_variations=len(existing_variations) + len(openings) + len(gambits),
            protected_untracked_existing_branches=len(existing_variations),
            payload_variations=len(owners) + len(variations),
            projected_total_variations=len(owners)
            + len(variations)
            + len(existing_variations),
            all_parent_child_relationships=len(variations) + len(existing_variations),
            opening_gambit_relationships=len(links),
            nested_named_parent_relationships=sum(
                v["parent_key"] != "owner-mainline" for v in variations
            ),
        ),
        eco_assigned=sorted(assigned),
        eco_unassigned=sorted(all_codes - assigned),
        variation_count_definitions=dict(
            new_branches="New named branches only; excludes new owner mainlines",
            new_mainlines="One MAIN for each newly created opening/gambit owner",
            existing_variations="90 curated MAIN records plus 100 curated named branches",
            payload_variations="All 740 owner MAIN references plus new named branches",
            protected_untracked_existing_branches="100 prior curated branches absent from sync payload and protected as untracked user data",
            projected_total_variations="Payload variation references plus the 100 preserved untracked curated branches",
            all_parent_child_relationships="All new branch edges plus the 100 prior curated branch edges",
            nested_named_parent_relationships="New branches whose parent is another named branch, excluding owner MAIN parents",
        ),
        opening_eco={n: r["eco_codes"] for n, r in sorted(opening_by_name.items())},
        eco_groups=dict(Counter(r["eco"][0] for r in sources)),
        opening_source_counts=dict(Counter(r["opening"] for r in sources)),
        rejected_invalid_moves=[],
        omissions=omitted,
        omission_reasons=dict(Counter(r["reason"] for r in omitted)),
        duplicate_sequence_groups=[v for v in sequence_groups.values() if len(v) > 1],
        transposition_position_groups=[
            v for v in position_groups.values() if len(v) > 1
        ],
        source_occurrences=occurrences,
        potential_eco_conflicts=[
            dict(
                owner_type=r["owner_type"],
                owner_name=r["owner_name"],
                concept=r["concept"],
                eco_codes=sorted({i["eco"] for i in r["occurrences"]}),
                reason="Same source-named concept has multiple ECO codes; retained for review, not presumed incorrect",
            )
            for r in occurrences
            if len({i["eco"] for i in r["occurrences"]}) > 1
        ],
        classification_ambiguities=mapping.get("ambiguities", []),
        limitations=[
            "Source ECO assignments retained; no independent theoretical reassessment.",
            "Fresh-install, upgrade, user-edit preservation and rerun require database acceptance checks.",
        ],
    )
    for row in list(owners.values()) + variations:
        row.pop("_moves", None)
        row["source_hash"] = _source_hash(row)
    payload = dict(
        batch_key=output.name,
        source_revision=provenance["commit"],
        openings=list(opening_by_name.values()),
        gambits=list(gambit_by_name.values()),
        variations=variations,
        opening_gambits=[
            dict(
                opening_name=a,
                gambit_name=b,
                source_key=stable_key("LINK", a, b, []),
                source_hash=hashlib.sha256(_json([a, b]).encode()).hexdigest(),
                source_references=sorted(
                    {
                        r["source"]
                        for r in contexts.get(("GAMBIT", b), [])
                        if r["opening"] == a
                    }
                ),
                curated_relationship=(a, b) in curated_links,
            )
            for a, b in links
        ],
        provenance=dict(
            source="lichess-org/chess-openings",
            licence="CC0-1.0",
            source_manifest=str(
                (
                    source.relative_to(ROOT)
                    if source.is_relative_to(ROOT)
                    else Path(source.name)
                )
                / "PROVENANCE.json"
            ),
        ),
    )
    return payload, report


def main() -> None:
    """Generate packaged offline artefacts or verify their deterministic bytes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Fail if packaged artefacts differ"
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=SOURCE,
        help="Pinned dataset directory containing PROVENANCE.json",
    )
    parser.add_argument(
        "--mapping",
        type=Path,
        default=MAPPING,
        help="Reviewed declarative mapping JSON",
    )
    parser.add_argument(
        "--output", type=Path, default=BATCH, help="New release output directory"
    )
    parser.add_argument(
        "--previous-catalogue",
        type=Path,
        help="Released catalogue JSON supplying owner identity bindings",
    )
    parser.add_argument(
        "--identities", type=Path, help="Released SOURCE_IDENTITIES.json registry"
    )
    args = parser.parse_args()
    payload, report = build_catalogue(
        args.source, args.mapping, args.output, args.previous_catalogue, args.identities
    )
    manifest = {
        r["key"]: {
            k: r[k] for k in ("owner_type", "owner_name", "concept", "canonical_source")
        }
        for r in report["source_occurrences"]
    }
    outputs = {
        args.output / "catalogue.json": _json(payload),
        args.output / "coverage.json": _json(report),
        args.output / "SOURCE_IDENTITIES.json": _json(manifest),
    }
    for path, text in outputs.items():
        if args.check:
            if not path.exists() or path.read_text() != text:
                raise SystemExit(f"Generated artefact differs: {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)


if __name__ == "__main__":
    main()
