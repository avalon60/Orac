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
RUN_DIR="$PROJECT_ROOT/var/run"
PID_FILE="$RUN_DIR/voice-ai.pid"

if [[ ! -f "$VOICE_AI_PY" ]]; then
  echo "voice_ai.py not found: $VOICE_AI_PY" >&2
  exit 1
fi

export ORAC_HOME="${ORAC_HOME:-$PROJECT_ROOT}"
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

if [[ "${ORAC_VOICE_ALLOW_MULTIPLE:-false}" != "true" ]]; then
  mkdir -p "$RUN_DIR"
  if [[ -f "$PID_FILE" ]]; then
    existing_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ "$existing_pid" =~ ^[0-9]+$ ]] && kill -0 "$existing_pid" 2>/dev/null; then
      echo "voice-ai is already running as PID $existing_pid." >&2
      echo "Stop that process first, or set ORAC_VOICE_ALLOW_MULTIPLE=true." >&2
      exit 1
    fi
    rm -f "$PID_FILE"
  fi
  echo "$$" >"$PID_FILE"
fi

if [[ -x "$PROJECT_PYTHON" ]]; then
  exec "$PROJECT_PYTHON" "$VOICE_AI_PY" "$@"
fi

if command -v poetry >/dev/null 2>&1; then
  cd "$PROJECT_ROOT"
  exec poetry run python "$VOICE_AI_PY" "$@"
fi

exec python3 "$VOICE_AI_PY" "$@"
