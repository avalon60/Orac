#!/usr/bin/env bash
################################################################################
#
# Author      : Clive Bostock
# Date        : 2026-05-13
# Description : Launch the local Orac voice assistant from any working directory.
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

cleanup() {
  local exit_code="$?"

  if [[ -n "${PID_FILE:-}" && -f "$PID_FILE" ]]; then
    existing_pid="$(cat "$PID_FILE" 2>/dev/null || true)"

    if [[ "$existing_pid" == "$$" ]]; then
      rm -f "$PID_FILE"
    fi
  fi

  exit "$exit_code"
}

run_voice_ai() {
  local inhibit_sleep="${ORAC_VOICE_INHIBIT_SLEEP:-true}"

  if [[ "$inhibit_sleep" == "true" ]]; then
    if command -v systemd-inhibit >/dev/null 2>&1; then
      if systemd-inhibit \
        --what=sleep \
        --mode=block \
        --who="Orac voice-ai" \
        --why="Orac voice assistant is using microphone/audio devices" \
        true 2>/dev/null; then
        systemd-inhibit \
          --what=sleep \
          --mode=block \
          --who="Orac voice-ai" \
          --why="Orac voice assistant is using microphone/audio devices" \
          "$@"

        return $?
      fi

      echo "Warning: systemd-inhibit failed; system sleep will not be inhibited." >&2
      "$@"
      return $?
    fi

    echo "Warning: systemd-inhibit not found; system sleep will not be inhibited." >&2
  fi

  "$@"
}
SCRIPT_PATH="$(resolve_path "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VOICE_AI_PY="$PROJECT_ROOT/bin/voice_ai.py"
PROJECT_PYTHON="$PROJECT_ROOT/.venv/bin/python"
RUN_DIR="$PROJECT_ROOT/var/run"
PID_FILE="$RUN_DIR/voice-ai.pid"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  if [[ -x "$PROJECT_PYTHON" ]]; then
    exec "$PROJECT_PYTHON" "$VOICE_AI_PY" "$@"
  fi

  if command -v poetry >/dev/null 2>&1; then
    cd "$PROJECT_ROOT"
    exec poetry run python "$VOICE_AI_PY" "$@"
  fi

  exec python3 "$VOICE_AI_PY" "$@"
fi

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
  trap cleanup EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
fi

if [[ -x "$PROJECT_PYTHON" ]]; then
  run_voice_ai "$PROJECT_PYTHON" "$VOICE_AI_PY" "$@"
  exit $?
fi

if command -v poetry >/dev/null 2>&1; then
  cd "$PROJECT_ROOT"
  run_voice_ai poetry run python "$VOICE_AI_PY" "$@"
  exit $?
fi

run_voice_ai python3 "$VOICE_AI_PY" "$@"
exit $?
