"""Provide the legacy Orac controller module as a compatibility facade."""
# Author: Clive Bostock
# Date: 2026-09-20
# Description: Exposes the core communications runtime at the historic import path.
# Purpose: Preserve controller.orac imports and the existing executable entrypoint.
# Usage: PYTHONPATH=src python src/controller/orac.py
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

import sys

from orac_core.communications import runtime as _runtime


if __name__ == "__main__":
    _runtime.run_main()
else:
    # Existing integrations patch controller.orac module globals. Aliasing keeps
    # those patch points attached to the authoritative communications runtime.
    sys.modules[__name__] = _runtime
