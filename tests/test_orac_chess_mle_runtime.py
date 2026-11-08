"""Exercise the fixed production CLOB bridge before Oracle runtime acceptance."""

# Author: Clive Bostock
# Date: 06-Nov-2026
# Description: Cover typed bridge behaviour with genuine policy semantics.
# Purpose: Catch boundary truncation, dispatch or validation regressions locally.
# Usage: .venv/bin/python -m pytest tests/test_orac_chess_mle_runtime.py

from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1] / "plugins/orac_chess"


def test_production_bridge_preserves_clob_and_fixed_operation_semantics() -> None:
    """Null, Unicode, full CLOBs, legal branches and header validation cross bridge."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is needed for the local production bridge checks")
    source = (ROOT / "tools/mle/production_bridge.mjs").read_text().replace(
        "'orac-chess-policy'", repr((ROOT / "tools/mle/validator.mjs").as_uri())
    )
    program = """
import assert from 'node:assert/strict';
const bridge = await import('data:text/javascript;base64,' + Buffer.from(process.env.CHESS_BRIDGE_SOURCE).toString('base64'));
const clob = value => ({length: () => value.length, getData: () => value});
assert.notEqual(bridge.validatePgn(null,0,null),null);
assert.equal(bridge.validatePgn(clob('1.e4 {'+'a'.repeat(64000)+'} *'),0,null),null);
assert.notEqual(bridge.validatePgn({length: () => 4194305, getData: () => {throw Error('must not read oversized input');}},0,null),null);
assert.equal(bridge.pgnHeader(clob('[Event "Unicode ♞"] 1.e4 *'),'Event'),'Unicode ♞');
assert.throws(() => bridge.pgnHeader(clob('[Event "invalid"] 1.e5 *'),'Event'));
assert.equal(bridge.validateBranch(clob('1.e4 *'),clob('1.d4 *'),0,null),null);
assert.notEqual(bridge.validateBranch(clob('1.e4 *'),clob('1.e4 *'),0,null),null);
assert.notEqual(bridge.validatePgn(clob('1.e4 (1.d4) *'),1,null),null);
"""
    import os

    environment = os.environ.copy()
    environment["CHESS_BRIDGE_SOURCE"] = source
    subprocess.run(
        [node, "--input-type=module", "--eval", program],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
