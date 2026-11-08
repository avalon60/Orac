"""Generate deterministic production Chess MLE deployment assets."""

# Author: Clive Bostock
# Date: 06-Nov-2026
# Description: Encode pinned runtime modules for SQLcl-safe deployment.
# Purpose: Keep the tested policy and vendor source canonical across installs.
# Usage: python3 plugins/orac_chess/tools/generate_mle_runtime.py --check

from __future__ import annotations

import argparse
from pathlib import Path
import sys

# Support both direct CLI execution and imports through the plugin-local package.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.generate_mle_proof import clob_assignments, generate as verify_proof


def generate(root: Path) -> dict[Path, str]:
    """Build private typed runtime objects from checked canonical sources."""
    verify_proof(root)  # Includes exact pinned upstream hash verification.
    assets: dict[Path, str] = {}
    header = """--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 06-Nov-2026
-- Purpose: Install private authoritative Chess MLE runtime.
-- Usage: Managed plugin deployment through pluginController.xml.
"""
    for name, path in [
        ("lib", root / "vendor/chess.js-1.4.0/chess.mjs"),
        ("policy", root / "tools/mle/validator.mjs"),
        ("bridge", root / "tools/mle/production_bridge.mjs"),
    ]:
        source = path.read_text().replace("'../../vendor/chess.js-1.4.0/chess.mjs'", "'orac-chess-lib'")
        statement = f"create or replace mle module orac_chess.chess_mle_{name}\nlanguage javascript as\n{source}"
        body = header + f"\n--changeset clive:orac_chess_mle_{name} context:plugin,prod labels:plugin runOnChange:true runAlways:true stripComments:false endDelimiter:/\n"
        body += "declare\n  l_source clob;\nbegin\n" + clob_assignments("l_source", statement)
        body += "  execute immediate l_source;\n  if dbms_lob.istemporary(l_source)=1 then dbms_lob.freetemporary(l_source); end if;\nexception\n  when others then\n    if dbms_lob.istemporary(l_source)=1 then dbms_lob.freetemporary(l_source); end if;\n    raise;\nend;\n/\n"
        body += f"--rollback drop mle module orac_chess.chess_mle_{name};\n"
        assets[root / f"db/schema/mle_module/chess_mle_{name}.sql"] = body
    assets[root / "db/schema/mle_env/chess_mle_env.sql"] = header + """
--changeset clive:orac_chess_mle_env context:plugin,prod labels:plugin runOnChange:true runAlways:true stripComments:false
create or replace mle env orac_chess.chess_mle_env
imports (
  'orac-chess-lib' module orac_chess.chess_mle_lib,
  'orac-chess-policy' module orac_chess.chess_mle_policy
) pure;
--rollback drop mle env orac_chess.chess_mle_env;
"""
    for name, params, export in [
        ("validate", "p_pgn clob, p_single number, p_fen varchar2", "validatePgn"),
        ("branch", "p_parent clob, p_child clob, p_ply number, p_fen varchar2", "validateBranch"),
        ("header", "p_pgn clob, p_name varchar2", "pgnHeader"),
    ]:
        assets[root / f"db/schema/function/chess_mle_{name}.sql"] = header + f"""
--changeset clive:orac_chess_mle_{name}_call context:plugin,prod labels:plugin runOnChange:true runAlways:true stripComments:false endDelimiter:/
create or replace function orac_chess.chess_mle_{name}({params}) return varchar2
as mle module orac_chess.chess_mle_bridge
  env orac_chess.chess_mle_env signature '{export}';
/
--rollback drop function orac_chess.chess_mle_{name};
"""
    return assets


def main() -> None:
    """Write assets or report deterministic source drift."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for path, source in generate(Path(__file__).resolve().parents[1]).items():
        if args.check:
            if not path.exists() or path.read_text() != source:
                raise SystemExit(f"Generated runtime differs: {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source)


if __name__ == "__main__":
    main()
