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
LISTENER_HOST="${ORAC_LISTENER_HOST:-127.0.0.1}"
LISTENER_PORT="${ORAC_LISTENER_PORT:-8765}"
LISTENER_START_TIMEOUT="${ORAC_LISTENER_START_TIMEOUT:-60}"

# --- Helpers ------------------------------------------------------------------
setup_run_dir() {
  if [[ -d "$RUN_DIR" && -w "$RUN_DIR" && -O "$RUN_DIR" ]]; then
    chmod 700 "$RUN_DIR"
  else
    sudo mkdir -p "$RUN_DIR"
    sudo chown "$(id -un)":"$(id -gn)" "$RUN_DIR"
    sudo chmod 700 "$RUN_DIR"
  fi

  mkdir -p "$LOG_DIR"
  chmod 700 "$LOG_DIR"

  # Generate an ephemeral HMAC secret if missing (defence-in-depth)
  if [[ ! -f "$SECRET_FILE" ]]; then
    if [[ -w "$RUN_DIR" && -O "$RUN_DIR" ]]; then
      umask 077
      openssl rand -base64 32 > "$SECRET_FILE"
    else
      # 32 bytes, base64
      openssl rand -base64 32 | sudo install -m 600 /dev/stdin "$SECRET_FILE"
      sudo chown "$(id -un)":"$(id -gn)" "$SECRET_FILE"
    fi
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

listener_ready() {
  local python_bin="$1"
  local host="$2"
  local port="$3"

  "$python_bin" -c 'import socket, sys
host = sys.argv[1]
port = int(sys.argv[2])
with socket.create_connection((host, port), timeout=1.0):
    pass
' "$host" "$port" >/dev/null 2>&1
}

wait_for_listener() {
  local python_bin="$1"
  local pid="$2"
  local deadline=$((SECONDS + LISTENER_START_TIMEOUT))

  echo "⏳ Waiting for Orac TCP bridge at ${LISTENER_HOST}:${LISTENER_PORT}..."
  while (( SECONDS < deadline )); do
    if listener_ready "$python_bin" "$LISTENER_HOST" "$LISTENER_PORT"; then
      echo "✅ Orac TCP bridge ready at ${LISTENER_HOST}:${LISTENER_PORT}"
      return 0
    fi

    if ! kill -0 "$pid" 2>/dev/null; then
      echo "❌ orac.py exited before the TCP bridge became ready. Check logs: $LOG_FILE" >&2
      rm -f "$PID_FILE" || true
      return 1
    fi

    sleep 1
  done

  echo "❌ orac.py is running, but the TCP bridge did not become ready within ${LISTENER_START_TIMEOUT}s." >&2
  echo "   Expected listener: ${LISTENER_HOST}:${LISTENER_PORT}" >&2
  echo "   Check logs: $LOG_FILE" >&2
  return 1
}

find_python() {
  if command -v poetry >/dev/null 2>&1; then
    local poetry_python
    poetry_python="$(cd "$PROJECT_DIR" && poetry run python -c 'import sys; print(sys.executable)' 2>/dev/null || true)"
    if [[ -n "$poetry_python" ]]; then echo "$poetry_python"; return; fi
  fi
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

  export PYTHONPATH="${PROJECT_DIR}/src:${PROJECT_DIR}:${PYTHONPATH:-}"
  export ORAC_RUN_DIR="$RUN_DIR"
  export ORAC_HMAC_SECRET_FILE="$SECRET_FILE"

  mkdir -p "$(dirname "$LOG_FILE")"
  echo "🚀 Starting Orac (version ${ORAC_VERSION})..."
  if command -v setsid >/dev/null 2>&1; then
    setsid "$PYTHON" "${CONTROL_DIR}/${ENTRY_POINT}" >>"$LOG_FILE" 2>&1 < /dev/null &
  else
    nohup "$PYTHON" "${CONTROL_DIR}/${ENTRY_POINT}" >>"$LOG_FILE" 2>&1 &
  fi
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

  wait_for_listener "$PYTHON" "$pid"

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
    local PYTHON
    PYTHON="$(find_python)"
    if [[ -n "$PYTHON" ]] && listener_ready "$PYTHON" "$LISTENER_HOST" "$LISTENER_PORT"; then
      echo "✅ Orac TCP bridge listening at ${LISTENER_HOST}:${LISTENER_PORT}"
    else
      echo "🟨 Orac TCP bridge not reachable at ${LISTENER_HOST}:${LISTENER_PORT}"
    fi
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
