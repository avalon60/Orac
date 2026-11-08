"""Render the repeated Chess ECO editor and disclosure components."""

# Author: Clive Bostock
# Date: 07-Nov-2026
# Description: Keep repeated ECO components in the APEX export consistent.
# Purpose: Generate only the marked ECO components from shared templates.
# Usage: python3 plugins/orac_chess/tools/generate_eco_apex.py --check

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "tools/apex_eco"
EXPORT = ROOT / "apex/orac_chess_admin.sql"


def render_component(component: dict[str, object]) -> str:
    """Render one editor or disclosure from its shared template.

    Args:
        component: Component type and replacement values from the manifest.

    Returns:
        The generated APEX export fragment.
    """
    kind = str(component["type"])
    source = (TEMPLATES / f"{kind}.sql.in").read_text(encoding="utf-8")
    if kind == "editor":
        base = int(component["base"])
        source = re.sub(
            r"@OFFSET_(\d+)@", lambda match: str(base + int(match.group(1))), source
        )
        for key in ("page", "owner", "stage"):
            source = source.replace(f"@{key.upper()}@", str(component[key]))
    elif kind == "css":
        pass
    elif kind == "disclosure":
        for key in ("id", "name", "query"):
            source = source.replace(f"@{key.upper()}@", str(component[key]))
    else:
        raise ValueError(f"Unknown ECO component type: {kind}")
    if re.search(r"@[A-Z_0-9]+@", source):
        raise ValueError("Unresolved ECO component template variable")
    return source


def generate(source: str) -> str:
    """Replace the marked ECO components while preserving the rest of the export.

    Args:
        source: Existing APEX export.

    Returns:
        The export with the generated ECO fragments updated.
    """
    components = json.loads((TEMPLATES / "components.json").read_text(encoding="utf-8"))
    for name, component in components.items():
        begin = f"-- BEGIN GENERATED ECO {name}\n"
        end = f"-- END GENERATED ECO {name}\n"
        if source.count(begin) != 1 or source.count(end) != 1:
            raise ValueError(f"Missing or duplicated markers for {name}")
        before, rest = source.split(begin, 1)
        _, after = rest.split(end, 1)
        source = before + begin + render_component(component) + end + after
    return source


def main() -> int:
    """Check or update the generated ECO fragments in the APEX export."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check without writing")
    args = parser.parse_args()
    try:
        existing = EXPORT.read_text(encoding="utf-8")
        generated = generate(existing)
        if args.check:
            if existing != generated:
                raise ValueError(f"{EXPORT}: ECO components are stale")
        elif existing != generated:
            EXPORT.write_text(generated, encoding="utf-8")
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"{exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
