"""Validate complete PGN branch batches using the packaged chess.js rules engine."""
# Author: Clive Bostock
# Date: 10-Nov-2026
# Description: Validate parent-first named branches before SQL packaging.

from __future__ import annotations

import csv
import json
from pathlib import Path
import re
import subprocess
from collections.abc import Callable

COLUMNS = ("key", "owner_type", "owner_name", "parent_key", "name", "pgn", "annotation")
ROOT = Path(__file__).resolve().parents[1]


def load_variations(batch: Path, openings: list[dict], gambits: list[dict], reader: Callable) -> list[dict]:
    """Load branches, validate all moves and return parents before descendants.

    Args:
        batch: Immutable CSV batch directory.
        openings: Validated opening records in the same batch.
        gambits: Validated gambit records in the same batch.
        reader: Strict CSV reader supplied by the generator.

    Returns:
        Validated branch records with exact divergence ply and expected parent PGN.

    Raises:
        ValueError: If ownership, PGN, hierarchy or divergence is invalid.
    """
    rows = reader(batch / "variations.csv", COLUMNS, ("eco_codes",))
    owners = {(kind, row["name"]): row for kind, items in
              (("OPENING", openings), ("GAMBIT", gambits)) for row in items}
    keys = {}
    identities = set()
    for row in rows:
        for column in COLUMNS:
            if column != "annotation" and not str(row[column]).strip():
                raise ValueError(f'{row["context"]}: {column} is required')
        key = row["key"]
        if not re.fullmatch(r"[a-z0-9_]{1,100}", str(key)) or key == "owner-mainline":
            raise ValueError("Variation key must be a unique local ASCII identifier")
        if len(str(row["pgn"])) > 4194304:
            raise ValueError("Variation PGN exceeds storage limit")
        identity = (row["owner_type"], row["owner_name"], row["name"])
        if key in keys or identity in identities or len(str(row["name"])) > 200:
            raise ValueError(f'{row["context"]}: duplicate key/name or oversized name')
        if identity[:2] not in owners:
            raise ValueError(f'{row["context"]}: unknown owner')
        codes = str(row.get("eco_codes", "")).split("|") if row.get("eco_codes") else []
        if len(set(codes)) != len(codes) or any(not re.fullmatch(r"[A-E][0-9]{2}", c) for c in codes):
            raise ValueError(f'{row["context"]}: invalid ECO codes')
        row["eco_codes"] = codes
        keys[key] = row
        identities.add(identity)
    result = []
    visiting = set()
    done = set()

    def visit(key: str) -> None:
        if key in visiting:
            raise ValueError(f"Variation cycle: {key}")
        if key in done:
            return
        visiting.add(key)
        row = keys[key]
        parent_key = row["parent_key"]
        if parent_key == "owner-mainline":
            parent = owners[(row["owner_type"], row["owner_name"])]
            row["parent_pgn"] = parent["mainline_pgn"]
            row["depth"] = 1
        else:
            if parent_key not in keys:
                raise ValueError(f"Unknown parent: {parent_key}")
            visit(parent_key)
            parent = keys[parent_key]
            if (parent["owner_type"], parent["owner_name"]) != (row["owner_type"], row["owner_name"]):
                raise ValueError("Branch parent belongs to a different owner")
            row["parent_pgn"] = parent["pgn"]
            row["depth"] = parent["depth"] + 1
        if row["depth"] > 2 or not row["parent_pgn"]:
            raise ValueError("Branch requires a mainline and at most two parent edges")
        visiting.remove(key)
        done.add(key)
        result.append(row)

    for key in keys:
        visit(key)
    if any(row.get("starting_fen") for row in owners.values()):
        raise ValueError("Branch batches require initial-position mainlines")
    pgns = [str(row["mainline_pgn"]) for row in owners.values() if row["mainline_pgn"]]
    pgns += [str(row[column]) for row in result for column in ("pgn", "parent_pgn")]
    script = '''import {parse} from %s;
let input=''; for await (const c of process.stdin) input+=c;
const histories=JSON.parse(input).map(pgn=>{const parsed=parse(pgn,1);
if(parsed.tags.FEN || !parsed.moves.length) throw Error('Expected initial-position complete PGN');
return parsed.moves;}); process.stdout.write(JSON.stringify(histories));''' % json.dumps((ROOT / "tools/mle/validator.mjs").as_uri())
    try:
        process = subprocess.run(["node", "--input-type=module", "-e", script],
                                 input=json.dumps(pgns), text=True, capture_output=True,
                                 check=True, timeout=60)
    except (subprocess.SubprocessError, OSError) as exc:
        raise ValueError(f"chess.js PGN validation failed: {getattr(exc, 'stderr', str(exc))}") from exc
    histories = dict(zip(pgns, json.loads(process.stdout)))
    with (ROOT / "seed/eco/2026_11_07/eco_codes.csv").open(encoding="utf-8") as stream:
        known_codes = {row["eco_code"] for row in csv.DictReader(stream)}
    for row in list(owners.values()) + result:
        for column in ("eco_codes", "mainline_eco_codes"):
            if set(row.get(column, [])) - known_codes:
                raise ValueError(f"Unknown ECO reference in {column}")
    for row in result:
        parent, child = histories[row["parent_pgn"]], histories[row["pgn"]]
        ply = next((i for i, (a, b) in enumerate(zip(parent, child)) if a != b), None)
        if ply is None:
            raise ValueError(f'{row["context"]}: extension/truncation is not a branch')
        row["branch_ply"] = ply
    return result
