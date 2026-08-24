#!/usr/bin/env bash
# Author: Clive Bostock
# Date: 14-Aug-2026
# Purpose: Run read-only knowledge inspection and bounded legacy migrations.
# Usage: bin/orac-knowledge.sh reconcile --json
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON_SCRIPT="$PROJECT_DIR/src/controller/orac-knowledge.py"

if [[ -x "$PROJECT_DIR/.venv/bin/python" ]]; then
  PYTHON_INTERPRETER="$PROJECT_DIR/.venv/bin/python"
elif command -v poetry >/dev/null 2>&1; then
  PYTHON_INTERPRETER="$(
    cd "$PROJECT_DIR"
    poetry run python -c 'import sys; print(sys.executable)'
  )"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_INTERPRETER="python3"
else
  printf 'Error: no compatible Python interpreter found.\n' >&2
  exit 1
fi

export ORAC_HOME="${ORAC_HOME:-$PROJECT_DIR}"
export PYTHONPATH="$PROJECT_DIR/src:$PROJECT_DIR:${PYTHONPATH:-}"
exec "$PYTHON_INTERPRETER" "$PYTHON_SCRIPT" "$@"
