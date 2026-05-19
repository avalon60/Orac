#!/usr/bin/env bash
################################################################################
#
# Author  : Clive Bostock
# Date    : 2026-05-12
# Purpose : Launch the Orac React display from the web/orac-display tree.
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
WEB_ROOT="$PROJECT_ROOT/web/orac-display"
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/orac-display-web.log"
HOST="${ORAC_DISPLAY_WEB_HOST:-127.0.0.1}"
PORT="${ORAC_DISPLAY_WEB_PORT:-5173}"
FULLSCREEN=false
MAXIMIZED=false

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Options:
  --fullscreen   Launch in kiosk mode (full screen, no browser UI).
  --maximized    Launch the window maximized.
  --host <host>  Override the Vite/Browser host (default: 127.0.0.1).
  --port <port>  Override the Vite/Browser port (default: 5173).
  --help         Show this help message.

Environment Variables:
  ORAC_DISPLAY_WEB_HOST  Default host.
  ORAC_DISPLAY_WEB_PORT  Default port.
EOF
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fullscreen)
      FULLSCREEN=true
      shift
      ;;
    --maximized)
      MAXIMIZED=true
      shift
      ;;
    --host)
      HOST="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --help|-h)
      usage
      ;;
    *)
      shift
      ;;
  esac
done

APP_URL="http://${HOST}:${PORT}"
export VITE_ORAC_SHOW_TRANSCRIPT_PANELS="${VITE_ORAC_SHOW_TRANSCRIPT_PANELS:-true}"
LAUNCHED_BROWSER_PID=""
BROWSER_PROFILE_DIR=""
BROWSER_CMD_PATTERN=""
BROWSER_WATCHDOG_PID=""

mkdir -p "$LOG_DIR"
touch "$LOG_FILE"
exec > >(tee -a "$LOG_FILE") 2>&1

if [[ ! -d "$WEB_ROOT" ]]; then
  echo "Orac display web tree not found: $WEB_ROOT" >&2
  exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Orac React display at $APP_URL"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Writing display launcher log to $LOG_FILE"

open_browser() {
  BROWSER_PROFILE_DIR="$(mktemp -d -t orac-display-web-browser.XXXXXX)"
  BROWSER_CMD_PATTERN="--user-data-dir=$BROWSER_PROFILE_DIR"

  local extra_flags=()
  if [[ "$FULLSCREEN" == "true" ]]; then
    extra_flags+=("--kiosk")
  elif [[ "$MAXIMIZED" == "true" ]]; then
    extra_flags+=("--start-maximized")
  fi

  if command -v google-chrome >/dev/null 2>&1; then
    setsid google-chrome \
      "${extra_flags[@]}" \
      --user-data-dir="$BROWSER_PROFILE_DIR" \
      --app="$APP_URL" \
      --new-window \
      --no-first-run \
      --enable-logging=stderr \
      --v=0 \
      --disable-infobars \
      --disable-session-crashed-bubble >>"$LOG_FILE" 2>&1 &
    LAUNCHED_BROWSER_PID="$!"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Launched google-chrome PID $LAUNCHED_BROWSER_PID"
    return 0
  fi

  if command -v chromium >/dev/null 2>&1; then
    setsid chromium \
      "${extra_flags[@]}" \
      --user-data-dir="$BROWSER_PROFILE_DIR" \
      --app="$APP_URL" \
      --new-window \
      --no-first-run \
      --enable-logging=stderr \
      --v=0 \
      --disable-infobars \
      --disable-session-crashed-bubble >>"$LOG_FILE" 2>&1 &
    LAUNCHED_BROWSER_PID="$!"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Launched chromium PID $LAUNCHED_BROWSER_PID"
    return 0
  fi

  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$APP_URL" >>"$LOG_FILE" 2>&1 &
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Opened display URL via xdg-open"
    return 0
  fi

  echo "Open $APP_URL in a browser." >&2
}

cleanup_browser() {
  if [[ -z "$BROWSER_PROFILE_DIR" ]]; then
    return 0
  fi

  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Browser cleanup target: pid=${LAUNCHED_BROWSER_PID:-none} profile=$BROWSER_PROFILE_DIR"
  if command -v pgrep >/dev/null 2>&1; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Browser processes before cleanup:"
    pgrep -a -f -- "$BROWSER_CMD_PATTERN" || true
  fi

  if [[ -n "$LAUNCHED_BROWSER_PID" ]] && kill -0 "$LAUNCHED_BROWSER_PID" 2>/dev/null; then
    browser_pgid="$(ps -o pgid= -p "$LAUNCHED_BROWSER_PID" 2>/dev/null | tr -d ' ' || true)"
    if [[ "$browser_pgid" =~ ^[0-9]+$ ]]; then
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] Killing browser process group $browser_pgid"
      kill -TERM -- "-$browser_pgid" 2>/dev/null || true
    fi
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Killing browser PID $LAUNCHED_BROWSER_PID"
    kill -TERM "$LAUNCHED_BROWSER_PID" 2>/dev/null || true
    wait "$LAUNCHED_BROWSER_PID" 2>/dev/null || true
  fi

  if command -v pkill >/dev/null 2>&1; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sending TERM to browser profile matches"
    pkill -TERM -f -- "$BROWSER_CMD_PATTERN" >/dev/null 2>&1 || true
    sleep 0.5
    if pgrep -f -- "$BROWSER_CMD_PATTERN" >/dev/null 2>&1; then
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sending KILL to remaining browser profile matches"
      pkill -KILL -f -- "$BROWSER_CMD_PATTERN" >/dev/null 2>&1 || true
    fi
  fi

  rm -rf "$BROWSER_PROFILE_DIR" >/dev/null 2>&1 || true
  if command -v pgrep >/dev/null 2>&1; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Browser processes after cleanup:"
    pgrep -a -f -- "$BROWSER_CMD_PATTERN" || true
  fi
}

start_browser_watchdog() {
  local shell_pid="$$"
  local vite_pid="$VITE_PID"
  local browser_pid="$LAUNCHED_BROWSER_PID"
  local browser_profile="$BROWSER_PROFILE_DIR"
  local browser_pattern="$BROWSER_CMD_PATTERN"
  local watchdog_script=""

  if [[ -z "$browser_profile" ]]; then
    return 0
  fi

  watchdog_script="$(mktemp -t orac-display-web-watchdog.XXXXXX)"
  cat >"$watchdog_script" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

shell_pid="$1"
vite_pid="$2"
browser_pid="$3"
browser_profile="$4"
browser_pattern="$5"
log_file="$6"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

while kill -0 "$shell_pid" 2>/dev/null && kill -0 "$vite_pid" 2>/dev/null; do
  sleep 0.5
done

{
  log "Browser watchdog triggered: shell_pid=$shell_pid vite_pid=$vite_pid browser_pid=${browser_pid:-none} profile=$browser_profile"
  if command -v pgrep >/dev/null 2>&1; then
    log "Browser processes before watchdog cleanup:"
    pgrep -a -f -- "$browser_pattern" || true
  fi

  if [[ -n "$browser_pid" ]] && kill -0 "$browser_pid" 2>/dev/null; then
    browser_pgid="$(ps -o pgid= -p "$browser_pid" 2>/dev/null | tr -d ' ' || true)"
    if [[ "$browser_pgid" =~ ^[0-9]+$ ]]; then
      log "Watchdog killing browser process group $browser_pgid"
      kill -TERM -- "-$browser_pgid" 2>/dev/null || true
    fi
    log "Watchdog killing browser PID $browser_pid"
    kill -TERM "$browser_pid" 2>/dev/null || true
  fi

  if command -v pkill >/dev/null 2>&1; then
    log "Watchdog sending TERM to browser profile matches"
    pkill -TERM -f -- "$browser_pattern" >/dev/null 2>&1 || true
    sleep 0.5
    if pgrep -f -- "$browser_pattern" >/dev/null 2>&1; then
      log "Watchdog sending KILL to remaining browser profile matches"
      pkill -KILL -f -- "$browser_pattern" >/dev/null 2>&1 || true
    fi
  fi

  rm -rf "$browser_profile" >/dev/null 2>&1 || true
  if command -v pgrep >/dev/null 2>&1; then
    log "Browser processes after watchdog cleanup:"
    pgrep -a -f -- "$browser_pattern" || true
  fi
} >>"$log_file" 2>&1

rm -f "$0" >/dev/null 2>&1 || true
EOF
  chmod +x "$watchdog_script"
  nohup "$watchdog_script" "$shell_pid" "$vite_pid" "$browser_pid" "$browser_profile" "$browser_pattern" "$LOG_FILE" >/dev/null 2>&1 &

  BROWSER_WATCHDOG_PID="$!"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Started browser watchdog PID $BROWSER_WATCHDOG_PID"
}

wait_for_http_port() {
  local attempt=0
  local max_attempts=100
  while (( attempt < max_attempts )); do
    if (exec 3<>"/dev/tcp/${HOST}/${PORT}") >/dev/null 2>&1; then
      exec 3>&-
      exec 3<&-
      return 0
    fi
    sleep 0.1
    attempt=$((attempt + 1))
  done

  return 1
}

cd "$WEB_ROOT"
npm run dev -- --host "$HOST" --port "$PORT" &
VITE_PID="$!"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Started Vite PID $VITE_PID"

cleanup() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Stopping Orac React display"

  if [[ -n "$BROWSER_WATCHDOG_PID" ]] && kill -0 "$BROWSER_WATCHDOG_PID" 2>/dev/null; then
    kill "$BROWSER_WATCHDOG_PID" 2>/dev/null || true
    wait "$BROWSER_WATCHDOG_PID" 2>/dev/null || true
  fi

  if kill -0 "$VITE_PID" 2>/dev/null; then
    kill "$VITE_PID" 2>/dev/null || true
    wait "$VITE_PID" 2>/dev/null || true
  fi

  cleanup_browser
}
trap cleanup EXIT INT TERM HUP

if wait_for_http_port; then
  open_browser
  start_browser_watchdog
else
  echo "Vite server did not open ${APP_URL} in time." >&2
  echo "You can still open ${APP_URL} manually." >&2
fi

wait "$VITE_PID"
