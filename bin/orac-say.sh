#!/usr/bin/env bash
################################################################################
#
# Author      : Clive Bostock
# Date        : 2026-05-14
# Description : Speak ad-hoc text through Orac's configured Piper voice.
#
################################################################################

set -euo pipefail

resolve_path() {
  local target="$1"

  if command -v realpath >/dev/null 2>&1; then
    realpath "$target"
    return
  fi

  if [[ "$target" = /* ]]; then
    printf '%s\n' "$target"
  else
    printf '%s/%s\n' "$PWD" "${target#./}"
  fi
}

SCRIPT_PATH="$(resolve_path "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ORAC_SAY_PY="$PROJECT_ROOT/bin/orac_say.py"
PROJECT_PYTHON="$PROJECT_ROOT/.venv/bin/python"

if [[ ! -f "$ORAC_SAY_PY" ]]; then
  echo "orac_say.py not found: $ORAC_SAY_PY" >&2
  exit 1
fi

export ORAC_HOME="${ORAC_HOME:-$PROJECT_ROOT}"
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

if [[ -x "$PROJECT_PYTHON" ]]; then
  exec "$PROJECT_PYTHON" "$ORAC_SAY_PY" "$@"
fi

if command -v poetry >/dev/null 2>&1; then
  cd "$PROJECT_ROOT"
  exec poetry run python "$ORAC_SAY_PY" "$@"
fi

exec python3 "$ORAC_SAY_PY" "$@"
