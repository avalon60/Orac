#!/usr/bin/env bash
################################################################################
#
# Author  : Clive Bostock
# Date    : 2026-05-08
# Purpose : Launch the local Orac voice assistant from any working directory.
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
VOICE_AI_PY="$PROJECT_ROOT/bin/voice_ai.py"
PROJECT_PYTHON="$PROJECT_ROOT/.venv/bin/python"

if [[ ! -f "$VOICE_AI_PY" ]]; then
  echo "voice_ai.py not found: $VOICE_AI_PY" >&2
  exit 1
fi

export ORAC_HOME="${ORAC_HOME:-$PROJECT_ROOT}"
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

if [[ -x "$PROJECT_PYTHON" ]]; then
  exec "$PROJECT_PYTHON" "$VOICE_AI_PY" "$@"
fi

if command -v poetry >/dev/null 2>&1; then
  cd "$PROJECT_ROOT"
  exec poetry run python "$VOICE_AI_PY" "$@"
fi

exec python3 "$VOICE_AI_PY" "$@"
