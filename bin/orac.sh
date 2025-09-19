#!/usr/bin/env bash
# Author  : Clive Bostock
# Date    : 2025-08-25
# Script  : orac.sh
# Purpose : Start/stop/status for the orac.py server (local process, not Docker). Named after the uber computer, Orac
#           in the sci-fi series, Blake's 7.

set -euo pipefail
IFS=$'\n\t'

PROG="$(basename "$0")"

# --- Paths --------------------------------------------------------------------
realpath() { [[ $1 = /* ]] && echo "$1" || echo "$PWD/${1#./}"; }
ENTRY_POINT="$(basename "$0" .sh).py"     # expects orac.py next to this script
SCRIPT_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BIN_DIR="${PROJECT_DIR}/bin"
CONTROL_DIR="${PROJECT_DIR}/src/controller"   # where orac.py lives
LOG_DIR="${PROJECT_DIR}/logs"

# Version (optional; tolerate missing)
ORAC_VERSION="$(grep -m1 '__version__' "${CONTROL_DIR}/__init__.py" 2>/dev/null | cut -d'"' -f2 || echo 'dev')"

# Runtime dir + files
RUN_DIR="/run/orac"
PID_FILE="${RUN_DIR}/orac.pid"
SECRET_FILE="${RUN_DIR}/slave.secret"
TOKEN_FILE="${RUN_DIR}/slave.token"   # only if you choose the simple-token path
SOCK_FILE="${RUN_DIR}/orac.sock"    # if you later use UDS
LOG_FILE="${LOG_DIR}/orac.log"

# --- Helpers ------------------------------------------------------------------
setup_run_dir() {
  sudo mkdir -p "$RUN_DIR"
  sudo chown "$(id -un)":"$(id -gn)" "$RUN_DIR"
  sudo chmod 700 "$RUN_DIR"

  mkdir -p "$LOG_DIR"
  chmod 700 "$LOG_DIR"

  # Generate an ephemeral HMAC secret if missing (defence-in-depth)
  if [[ ! -f "$SECRET_FILE" ]]; then
    # 32 bytes, base64
    openssl rand -base64 32 | sudo install -m 600 /dev/stdin "$SECRET_FILE"
    sudo chown "$(id -un)":"$(id -gn)" "$SECRET_FILE"
  fi
}

cleanup_run_files() {
  [[ -S "$SOCK_FILE" ]] && rm -f "$SOCK_FILE" || true
  # Don’t delete SECRET_FILE by default; keep it for the lifetime of the process.
  # If you prefer to rotate it every start, uncomment the next line:
  # rm -f "$SECRET_FILE" || true
}

# Return 0 if PID corresponds to our orac.py process, else 1
_pid_matches_orac() {
  local pid="$1"
  # Fast existence check
  [[ -d "/proc/${pid}" ]] || return 1

  # Read the command line safely (Linux)
  # shellcheck disable=SC2002
  local cmdline
  cmdline="$(tr -d '\0' < "/proc/${pid}/cmdline" 2>/dev/null || true)"
  if [[ -z "$cmdline" ]]; then
    # Fall back to ps if /proc isn’t readable for some reason
    cmdline="$(ps -p "$pid" -o args= 2>/dev/null || true)"
  fi
  [[ -n "$cmdline" ]] || return 1

  # Consider it a match if it’s python …/src/controller/orac.py
  # or directly …/src/controller/orac.py (shebang execution).
  if grep -qE "(python[0-9]*\s+)?${CONTROL_DIR}/${ENTRY_POINT}(\s|$)" <<<"$cmdline"; then
    return 0
  fi
  # Also allow a looser check for ENTRY_POINT alone (in case paths are resolved)
  if grep -qE "(python[0-9]*\s+)?${ENTRY_POINT}(\s|$)" <<<"$cmdline"; then
    return 0
  fi
  return 1
}

is_running() {
  [[ -f "$PID_FILE" ]] || return 1
  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || echo "")"
  [[ -n "$pid" ]] || return 1
  _pid_matches_orac "$pid"
}

find_python() {
  if command -v python >/dev/null 2>&1; then echo python; return; fi
  if command -v python3 >/dev/null 2>&1; then echo python3; return; fi
  if command -v py >/dev/null 2>&1; then echo py; return; fi
  echo ""
}

activate_venv() {
  local VENV_DIR="${PROJECT_DIR}/.venv"
  local ACTIVATE_SCRIPT
  if [[ "$(uname -s)" =~ ^MINGW64_NT ]]; then
    ACTIVATE_SCRIPT="${VENV_DIR}/Scripts/activate"
  else
    ACTIVATE_SCRIPT="${VENV_DIR}/bin/activate"
  fi
  if [[ -f "$ACTIVATE_SCRIPT" ]]; then
    # shellcheck disable=SC1090
    source "$ACTIVATE_SCRIPT"
  else
    echo "⚠️  No virtualenv found at $ACTIVATE_SCRIPT; continuing with system Python."
  fi
}

# --- Commands -----------------------------------------------------------------
start_orac() {
  setup_run_dir
  cleanup_run_files

  # If PID file exists but doesn't match our process, clean it
  if [[ -f "$PID_FILE" ]]; then
    if ! is_running; then
      echo "🧹 Removing stale PID file."
      rm -f "$PID_FILE" || true
    fi
  fi

  if is_running; then
    echo "✅ Orac already running (PID $(cat "$PID_FILE"))."
    return 0
  fi

  activate_venv
  local PYTHON
  PYTHON="$(find_python)"
  if [[ -z "$PYTHON" ]]; then
    echo "❌ No Python interpreter found in PATH." >&2
    exit 1
  fi

  export PYTHONPATH="${PROJECT_DIR}:${PYTHONPATH:-}"
  export ORAC_RUN_DIR="$RUN_DIR"
  export ORAC_HMAC_SECRET_FILE="$SECRET_FILE"

  mkdir -p "$(dirname "$LOG_FILE")"
  echo "🚀 Starting Orac (version ${ORAC_VERSION})..."
  nohup "$PYTHON" "${CONTROL_DIR}/${ENTRY_POINT}" >>"$LOG_FILE" 2>&1 &
  local pid=$!
  echo "$pid" > "$PID_FILE"

  # Sanity check: give it a moment to start, then verify the PID belongs to us
  sleep 1
  if ! _pid_matches_orac "$pid"; then
    echo "❌ Launch failed (PID $pid is not ${ENTRY_POINT}). Check logs: $LOG_FILE" >&2
    rm -f "$PID_FILE" || true
    exit 1
  fi
  # Extra: ensure it’s still alive
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "❌ orac.py exited immediately. Check logs: $LOG_FILE" >&2
    rm -f "$PID_FILE" || true
    exit 1
  fi

  echo "✅ Started orac.py as PID $pid"
  echo "📝 Logs: $LOG_FILE"
}

stop_orac() {
  # If PID file exists but doesn’t match our process, treat as not running
  if [[ -f "$PID_FILE" ]] && ! _pid_matches_orac "$(cat "$PID_FILE" 2>/dev/null || echo "")"; then
    echo "ℹ️  Stale PID file detected; removing."
    rm -f "$PID_FILE" || true
  fi

  if ! is_running; then
    echo "ℹ️  Orac is not running."
    cleanup_run_files
    return 0
  fi

  local pid
  pid="$(cat "$PID_FILE")"
  echo "🛑 Stopping Orac (PID $pid)..."
  kill "$pid" 2>/dev/null || true

  # Wait up to 10s, then SIGKILL
  for _ in {1..10}; do
    if ! kill -0 "$pid" 2>/dev/null; then
      break
    fi
    sleep 1
  done
  if kill -0 "$pid" 2>/dev/null; then
    echo "⚠️  Still running, sending SIGKILL."
    kill -9 "$pid" 2>/dev/null || true
  fi

  rm -f "$PID_FILE" || true
  cleanup_run_files
  echo "✅ Stopped."
}

status_orac() {
  if is_running; then
    echo "✅ Orac running (PID $(cat "$PID_FILE"))"
  else
    echo "🟨 Orac not running"
  fi
  echo "📄 Log file: $LOG_FILE"
}

logs_orac() {
  [[ -f "$LOG_FILE" ]] || { echo "ℹ️  No log file yet at $LOG_FILE"; return 0; }
  tail -n 200 -f "$LOG_FILE"
}

print_usage() {
  echo "${PROG}  (Orac ${ORAC_VERSION})"
  echo "Usage: $0 {start|stop|restart|status|logs}"
  exit 1
}

# --- Dispatch -----------------------------------------------------------------
case "${1:-}" in
  start)   start_orac ;;
  stop)    stop_orac ;;
  restart) stop_orac; start_orac ;;
  status)  status_orac ;;
  logs)    logs_orac ;;
  *)       print_usage ;;
esac

