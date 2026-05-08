#!/usr/bin/env bash
################################################################################
#
# Author  : Clive Bostock
# Date    : 2026-05-08
# Purpose : Launch and manage the optional Orac atom display process.
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
PROJECT_PYTHON="$PROJECT_ROOT/.venv/bin/python"
RUN_DIR="$PROJECT_ROOT/var/run"
LOG_DIR="$PROJECT_ROOT/logs"
PID_FILE="$RUN_DIR/orac-display.pid"
LOG_FILE="$LOG_DIR/orac-display.log"

export ORAC_HOME="${ORAC_HOME:-$PROJECT_ROOT}"
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

display_is_running() {
  local pid=""

  [[ -f "$PID_FILE" ]] || return 1
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

require_graphical_session() {
  if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
    echo "No graphical session found. Set DISPLAY or WAYLAND_DISPLAY." >&2
    exit 1
  fi
}

run_display() {
  require_graphical_session
  cd "$PROJECT_ROOT"
  if [[ -x "$PROJECT_PYTHON" ]]; then
    exec "$PROJECT_PYTHON" -m view.orac_atom_display --listen-display-events "$@"
  fi
  if command -v poetry >/dev/null 2>&1; then
    exec poetry run python -m view.orac_atom_display --listen-display-events "$@"
  fi
  exec python3 -m view.orac_atom_display --listen-display-events "$@"
}

start_display() {
  require_graphical_session
  mkdir -p "$RUN_DIR" "$LOG_DIR"

  if display_is_running; then
    echo "Orac display already running as PID $(cat "$PID_FILE")."
    return 0
  fi

  cd "$PROJECT_ROOT"
  if [[ -x "$PROJECT_PYTHON" ]]; then
    nohup "$PROJECT_PYTHON" -m view.orac_atom_display --listen-display-events "$@" \
      >>"$LOG_FILE" 2>&1 &
  elif command -v poetry >/dev/null 2>&1; then
    nohup poetry run python -m view.orac_atom_display --listen-display-events "$@" \
      >>"$LOG_FILE" 2>&1 &
  else
    nohup python3 -m view.orac_atom_display --listen-display-events "$@" \
      >>"$LOG_FILE" 2>&1 &
  fi
  echo "$!" >"$PID_FILE"
  echo "Started Orac display as PID $(cat "$PID_FILE")."
  echo "Log: $LOG_FILE"
}

stop_display() {
  local pid=""

  if ! [[ -f "$PID_FILE" ]]; then
    echo "Orac display is not running."
    return 0
  fi

  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if ! [[ "$pid" =~ ^[0-9]+$ ]]; then
    rm -f "$PID_FILE"
    echo "Removed stale Orac display PID file."
    return 0
  fi

  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
    for _ in {1..30}; do
      if ! kill -0 "$pid" 2>/dev/null; then
        break
      fi
      sleep 0.1
    done
  fi

  rm -f "$PID_FILE"
  echo "Stopped Orac display."
}

status_display() {
  if display_is_running; then
    echo "Orac display running as PID $(cat "$PID_FILE")."
    return 0
  fi

  if [[ -f "$PID_FILE" ]]; then
    echo "Orac display is not running; removing stale PID file."
    rm -f "$PID_FILE"
    return 1
  fi

  echo "Orac display is not running."
  return 1
}

usage() {
  cat <<'EOF'
Usage:
  bin/orac-display.sh [run] [display args...]
  bin/orac-display.sh start [display args...]
  bin/orac-display.sh stop
  bin/orac-display.sh restart [display args...]
  bin/orac-display.sh status

Display args are passed to:
  python -m view.orac_atom_display --listen-display-events

Examples:
  bin/orac-display.sh
  bin/orac-display.sh start --mode compact
  bin/orac-display.sh run --mode dev --display-port 8766
EOF
}

command="${1:-run}"
if [[ $# -gt 0 ]]; then
  shift
fi

case "$command" in
  run)
    run_display "$@"
    ;;
  start)
    start_display "$@"
    ;;
  stop)
    stop_display
    ;;
  restart)
    stop_display
    start_display "$@"
    ;;
  status)
    status_display
    ;;
  help|--help|-h)
    usage
    ;;
  *)
    set -- "$command" "$@"
    run_display "$@"
    ;;
esac
