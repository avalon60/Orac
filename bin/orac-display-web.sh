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
HOST="${ORAC_DISPLAY_WEB_HOST:-127.0.0.1}"
PORT="${ORAC_DISPLAY_WEB_PORT:-5173}"
APP_URL="http://${HOST}:${PORT}"

if [[ ! -d "$WEB_ROOT" ]]; then
  echo "Orac display web tree not found: $WEB_ROOT" >&2
  exit 1
fi

open_browser() {
  if command -v google-chrome >/dev/null 2>&1; then
    google-chrome \
      --app="$APP_URL" \
      --new-window \
      --no-first-run \
      --disable-infobars \
      --disable-session-crashed-bubble >/dev/null 2>&1 &
    return 0
  fi

  if command -v chromium >/dev/null 2>&1; then
    chromium \
      --app="$APP_URL" \
      --new-window \
      --no-first-run \
      --disable-infobars \
      --disable-session-crashed-bubble >/dev/null 2>&1 &
    return 0
  fi

  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$APP_URL" >/dev/null 2>&1 &
    return 0
  fi

  echo "Open $APP_URL in a browser." >&2
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

cleanup() {
  if kill -0 "$VITE_PID" 2>/dev/null; then
    kill "$VITE_PID" 2>/dev/null || true
    wait "$VITE_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if wait_for_http_port; then
  open_browser
else
  echo "Vite server did not open ${APP_URL} in time." >&2
  echo "You can still open ${APP_URL} manually." >&2
fi

wait "$VITE_PID"
