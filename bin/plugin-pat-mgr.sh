#!/usr/bin/env bash
# Author: Clive Bostock
# Date: 05-Jun-2026
# Description: Wrapper shell for calling plugin-pat-mgr.py.
set -euo pipefail

realpath() {
  [[ $1 = /* ]] && printf '%s\n' "$1" || printf '%s/%s\n' "$PWD" "${1#./}"
}

ENTRY_POINT="$(basename "$0" .sh).py"
SCRIPT_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
CONTROL_DIR="${PROJECT_DIR}/src/controller"
PYTHON_SCRIPT="${CONTROL_DIR}/${ENTRY_POINT}"

POETRY_PYTHON=""
if command -v poetry >/dev/null 2>&1; then
  POETRY_PYTHON="$(cd "$PROJECT_DIR" && poetry run python -c 'import sys; print(sys.executable)' 2>/dev/null || true)"
fi

VENV_DIR="${PROJECT_DIR}/.venv"
if [[ "$(uname -s)" =~ ^MINGW64_NT ]]; then
  ACTIVATE_SCRIPT="${VENV_DIR}/Scripts/activate"
else
  ACTIVATE_SCRIPT="${VENV_DIR}/bin/activate"
fi

if [[ -f "$ACTIVATE_SCRIPT" ]]; then
  # shellcheck source=/dev/null
  source "$ACTIVATE_SCRIPT"
else
  printf 'WARNING: Unable locate a venv directory or activate script; no virtual environment activated.\n' >&2
fi

PYTHON_INTERPRETER="${POETRY_PYTHON:-}"
if [[ -z "$PYTHON_INTERPRETER" ]] && command -v python >/dev/null 2>&1; then
  PYTHON_INTERPRETER="python"
elif [[ -z "$PYTHON_INTERPRETER" ]] && command -v py >/dev/null 2>&1; then
  PYTHON_INTERPRETER="py"
elif [[ -z "$PYTHON_INTERPRETER" ]] && command -v python3 >/dev/null 2>&1; then
  PYTHON_INTERPRETER="python3"
fi

if [[ -z "$PYTHON_INTERPRETER" ]]; then
  printf 'Error: No compatible Python interpreter found (python3, python, or py)!\n' >&2
  exit 1
fi

export PYTHONPATH="${PROJECT_DIR}/src:${PROJECT_DIR}:${PYTHONPATH:-}"
"$PYTHON_INTERPRETER" "$PYTHON_SCRIPT" "$@"
