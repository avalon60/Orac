"""Exercise the shipped strict PGN validator against pinned Java dependencies."""
# Author: Clive Bostock
# Date: 02-Nov-2026
# Description: Compile the production Java adapter and run its semantic corpus.
# Purpose: Verify strict consumption, SAN, FEN, RAV, and branch behavior without a database.
# Usage: .venv/bin/python -m pytest tests/test_orac_chess_validator.py

from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1] / 'plugins/orac_chess'


def test_authoritative_validator_corpus(tmp_path: Path) -> None:
    """Compile pinned sources and assert positive and adversarial PGN cases."""
    if not shutil.which('javac') or not shutil.which('java'):
        pytest.skip('Java compiler/runtime is required for the authoritative corpus')
    sources = sorted(ROOT.glob('vendor/*/src/**/*.java'))
    sources += [ROOT / 'java/OracChessValidator.java', ROOT / 'tests/ChessValidatorSpike.java']
    subprocess.run(
        ['javac', '--release', '11', '-d', str(tmp_path), *map(str, sources)],
        check=True, capture_output=True, text=True, timeout=60,
    )
    result = subprocess.run(
        ['java', '-cp', str(tmp_path), 'ChessValidatorSpike'],
        check=True, capture_output=True, text=True, timeout=30,
    )
    assert '29 validator spike checks passed' in result.stdout
