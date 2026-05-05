"""Development checkout shim for the src/orac_voice package.

# Author: Clive Bostock
# Date: 2026-05-04
# Description: Allows python -m orac_voice... from an uninstalled checkout.
"""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
SRC_PACKAGE = SRC_ROOT / "orac_voice"

if SRC_ROOT.exists() and str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

if SRC_PACKAGE.exists():
  __path__.append(str(SRC_PACKAGE))
