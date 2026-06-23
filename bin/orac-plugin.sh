#!/usr/bin/env bash
# Author: Clive Bostock
# Date: 07-Jun-2026
# Description: Wrapper for the Orac plugin packaging and installation utility.
#
# Purpose: Package and install Orac plugins through the active Orac environment.
# Usage: bin/orac-plugin.sh install --bundled home_assistant
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON_SCRIPT="$PROJECT_DIR/src/controller/orac-plugin.py"

if [[ -x "$PROJECT_DIR/.venv/bin/python" ]]; then
  PYTHON_INTERPRETER="$PROJECT_DIR/.venv/bin/python"
elif command -v poetry >/dev/null 2>&1; then
  PYTHON_INTERPRETER="$(cd "$PROJECT_DIR" && poetry run python -c 'import sys; print(sys.executable)')"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_INTERPRETER="python3"
else
  printf 'Error: no compatible Python interpreter found.\n' >&2
  exit 1
fi

export ORAC_HOME="${ORAC_HOME:-$PROJECT_DIR}"
export PYTHONPATH="$PROJECT_DIR/src:$PROJECT_DIR:${PYTHONPATH:-}"
exec "$PYTHON_INTERPRETER" "$PYTHON_SCRIPT" "$@"
