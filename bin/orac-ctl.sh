#!/usr/bin/env bash
################################################################################
# Author  : Clive Bostock
# Date    : 2025-08-25
# Script  : orac-ctl.sh
# Purpose : Unified script to control Orac (Oracle DB + ORDS + AI engine)
################################################################################

set -e
PROG=$(basename "$0")

# -----------------------------------------------------------------------------#
# Paths
# -----------------------------------------------------------------------------#
realpath() { [[ $1 = /* ]] && echo "$1" || echo "$PWD/${1#./}"; }
SCRIPT_DIR=$(dirname "$(realpath "${BASH_SOURCE[0]}")")
PROJECT_DIR=$(dirname "$SCRIPT_DIR")
CONFIG_DIR=${PROJECT_DIR}/resources/config
CTL_DIR=${PROJECT_DIR}/src/controller
DEFAULTS_FILE="${CONFIG_DIR}/init-defaults.ini"
ORA_DOCKER_DIR=${PROJECT_DIR}/resources/docker/oracle
COMPOSE_FILE="${ORA_DOCKER_DIR}/docker-compose.yaml"
ENV_FILE="${CONFIG_DIR}/orac.env"
RUN_DIR="/run/orac"
DUMP_CONTEXT_FLAG="${RUN_DIR}/dump-context.once"
ORAC_LOG_FILE="${PROJECT_DIR}/logs/orac.log"
ORAC_DEBUG_DIR="${PROJECT_DIR}/logs/_debug"
ORAC_CACHE_DIR="${PROJECT_DIR}/var/cache"
BUILD_LOG_FILE="${PROJECT_DIR}/build.log"
DOCKER_LOG_FILE="${PROJECT_DIR}/docker.log"

# AI server control script (owns PID, /run/orac, logs)
ORAC_SH="${SCRIPT_DIR}/orac.sh"
if [[ ! -x "$ORAC_SH" ]]; then
  echo "❌ Missing or non-executable: $ORAC_SH"
  echo "   Ensure it exists and run:  chmod +x \"$ORAC_SH\""
  exit 1
fi

# -----------------------------------------------------------------------------#
# Secrets / env
# -----------------------------------------------------------------------------#
ORACLE_PASSWORD=$("$SCRIPT_DIR/dbconn-property.sh" -n orac -p password)
if [[ -z "$ORACLE_PASSWORD" ]]; then
  echo "❌ Could not retrieve Oracle password from credential store."
  exit 1
fi

# Load Orac environment settings from orac.env
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
else
  echo "⚠️ Defaults file not found: $ENV_FILE. Using hardcoded values."
  ORADATA_DIR="/u01/orac-db/oradata"
  CONTAINER_NAME="orac-db"
  PORT_SQLNET=1521
  PORT_HTTP=8042    # The meaning of life ;o)
  PORT_EM=5500
  IMAGE_TAG="23.5.0-lite"
fi

# Extract Orac version (controller package)
ORAC_VERSION=$(grep -m1 "__version__" "${CTL_DIR}/__init__.py" 2>/dev/null | cut -d'"' -f2 || echo "dev")

# -----------------------------------------------------------------------------#
# Helpers
# -----------------------------------------------------------------------------#
ensure_env() {
  export ORACLE_PWD="${ORACLE_PASSWORD}"
  export ORADATA_DIR="${ORADATA_DIR}"
  export PORT_SQLNET="${PORT_SQLNET}"
  export PORT_HTTP="${PORT_HTTP}"
  export PORT_EM="${PORT_EM}"
}

declare -a CLEANUP_TARGETS=()
declare -A CLEANUP_SEEN=()

add_cleanup_target() {
  local target="$1"

  if [[ -z "$target" ]]; then
    return 0
  fi

  if [[ ! -e "$target" && ! -L "$target" ]]; then
    return 0
  fi

  if [[ -n "${CLEANUP_SEEN[$target]:-}" ]]; then
    return 0
  fi

  CLEANUP_SEEN["$target"]=1
  CLEANUP_TARGETS+=("$target")
}

is_stale_pid_file() {
  local pid_file="$1"
  local pid=""

  [[ -f "$pid_file" ]] || return 1
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  [[ -n "$pid" ]] || return 0
  [[ "$pid" =~ ^[0-9]+$ ]] || return 0
  kill -0 "$pid" 2>/dev/null && return 1
  return 0
}

collect_cleanup_targets() {
  local mode="$1"
  local path

  CLEANUP_TARGETS=()
  CLEANUP_SEEN=()

  if is_stale_pid_file "${RUN_DIR}/orac.pid"; then
    add_cleanup_target "${RUN_DIR}/orac.pid"
  fi

  add_cleanup_target "$DUMP_CONTEXT_FLAG"
  add_cleanup_target "$ORAC_DEBUG_DIR"
  add_cleanup_target "$ORAC_CACHE_DIR"
  add_cleanup_target "${PROJECT_DIR}/.pytest_cache"
  add_cleanup_target "${PROJECT_DIR}/.mypy_cache"
  add_cleanup_target "$ORAC_LOG_FILE"

  if [[ -d "${PROJECT_DIR}/logs" ]]; then
    for path in "${PROJECT_DIR}/logs"/*.log; do
      [[ -e "$path" ]] || continue
      add_cleanup_target "$path"
    done
  fi

  if [[ -d "$PROJECT_DIR/bin" ]]; then
    while IFS= read -r -d '' path; do
      add_cleanup_target "$path"
    done < <(find "$PROJECT_DIR/bin" -type d -name '__pycache__' -print0)
  fi

  for path in "$PROJECT_DIR/src" "$PROJECT_DIR/tests" "$PROJECT_DIR/plugins" "$PROJECT_DIR/protocol"; do
    if [[ -d "$path" ]]; then
      while IFS= read -r -d '' entry; do
        add_cleanup_target "$entry"
      done < <(find "$path" -type d -name '__pycache__' -print0)
    fi
  done

  if [[ "$mode" == "purge" ]]; then
    add_cleanup_target "$BUILD_LOG_FILE"
    add_cleanup_target "$DOCKER_LOG_FILE"
  fi
}

print_cleanup_targets() {
  local mode="$1"
  local target

  collect_cleanup_targets "$mode"

  if [[ "${#CLEANUP_TARGETS[@]}" -eq 0 ]]; then
    echo "ℹ️  No Orac runtime artefacts found for ${mode}."
    return 0
  fi

  echo "📋 ${mode^} plan:"
  for target in "${CLEANUP_TARGETS[@]}"; do
    echo "  - $target"
  done
}

run_cleanup_targets() {
  local mode="$1"
  local dry_run="$2"
  local target
  local removed=0

  collect_cleanup_targets "$mode"

  if [[ "${#CLEANUP_TARGETS[@]}" -eq 0 ]]; then
    echo "ℹ️  No Orac runtime artefacts found for ${mode}."
    return 0
  fi

  if [[ "$dry_run" == "1" ]]; then
    print_cleanup_targets "$mode"
    return 0
  fi

  for target in "${CLEANUP_TARGETS[@]}"; do
    rm -rf -- "$target"
    removed=$((removed + 1))
  done

  echo "✅ ${mode^} complete. Removed ${removed} path(s)."
}

prompt_for_purge() {
  local response=""

  if [[ ! -t 0 ]]; then
    echo "❌ purge requires --force when run non-interactively."
    exit 1
  fi

  read -r -p "Type PURGE to remove Orac runtime artefacts: " response
  if [[ "$response" != "PURGE" ]]; then
    echo "ℹ️  Purge aborted."
    exit 1
  fi
}

# -----------------------------------------------------------------------------#
# Actions
# -----------------------------------------------------------------------------#
start_orac_stack() {
  echo "🚀 Starting Orac stack (Oracle DB + ORDS + AI)..."
  ensure_env

  if docker ps -a --format '{{.Names}}' | grep -wq "$CONTAINER_NAME"; then
    if [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME")" == "true" ]]; then
      echo "✅ '$CONTAINER_NAME' is already running."
    else
      echo "▶️  Starting existing container '$CONTAINER_NAME'..."
      docker start "$CONTAINER_NAME" >/dev/null
      echo "✅ Database/ORDS started."
    fi
  else
    echo "❌ No container named '$CONTAINER_NAME' found."
    echo "👉 Run the provisioner first: bin/oracdb-init.sh"
    exit 1
  fi
  $SCRIPT_DIR/dbwait.sh
  echo "🤖 Starting Orac AI engine..."
  "$ORAC_SH" start
}

stop_orac_stack() {
  echo "🛑 Stopping Orac AI engine..."
  "$ORAC_SH" stop || true

  echo "🛑 Stopping Orac DB/ORDS container..."
  if docker ps -a --format '{{.Names}}' | grep -wq "$CONTAINER_NAME"; then
    docker stop "$CONTAINER_NAME" >/dev/null || true
    echo "⏹️  '$CONTAINER_NAME' stopped."
  else
    echo "ℹ️ No container named '$CONTAINER_NAME' to stop."
  fi
}

status_orac_stack() {
  echo "📋 Orac DB/ORDS container status:"
  docker ps -a | grep -w "$CONTAINER_NAME" || echo "⚠️  Container '$CONTAINER_NAME' not found."
  echo
  echo "🤖 Orac AI engine status:"
  "$ORAC_SH" status
}

logs_orac_stack() {
  case "${1:-}" in
    ai|orac)
      "$ORAC_SH" logs
      ;;
    db|ords|"")
      echo "📜 Tailing DB/ORDS container logs..."
      docker logs -f "$CONTAINER_NAME"
      ;;
    *)
      echo "Usage: $PROG logs {ai|db}"
      exit 1
      ;;
  esac
}

dump_context_orac_stack() {
  mkdir -p "${PROJECT_DIR}/logs/_debug"

  if [[ ! -d "$RUN_DIR" ]]; then
    echo "⚠️  Runtime directory '$RUN_DIR' does not exist yet."
    echo "   Start Orac first, then rerun '$PROG dump-context'."
    exit 1
  fi

  : > "$DUMP_CONTEXT_FLAG"
  chmod 600 "$DUMP_CONTEXT_FLAG"

  echo "📝 Armed one-shot context dump."
  echo "   The next Orac request will write debug files under:"
  echo "   ${PROJECT_DIR}/logs/_debug"
  echo "   Expected files:"
  echo "   - latest-final-prompt.txt"
  echo "   - latest-history-fetched.txt"
}

clean_orac_runtime() {
  local dry_run=0
  local force=0
  local arg

  shift || true
  for arg in "$@"; do
    case "$arg" in
      --dry-run|-n) dry_run=1 ;;
      --force|-f) force=1 ;;
      --help|-h)
        echo "Usage: $PROG clean [--dry-run|-n] [--force|-f]"
        exit 0
        ;;
      *)
        echo "Usage: $PROG clean [--dry-run|-n] [--force|-f]"
        exit 1
        ;;
    esac
  done

  if [[ "$force" -eq 1 ]]; then
    echo "⚠️  --force is accepted for symmetry but clean remains non-destructive."
  fi

  run_cleanup_targets "clean" "$dry_run"
}

purge_orac_runtime() {
  local dry_run=0
  local force=0
  local arg

  shift || true
  for arg in "$@"; do
    case "$arg" in
      --dry-run|-n) dry_run=1 ;;
      --force|-f) force=1 ;;
      --help|-h)
        echo "Usage: $PROG purge [--dry-run|-n] [--force|-f]"
        exit 0
        ;;
      *)
        echo "Usage: $PROG purge [--dry-run|-n] [--force|-f]"
        exit 1
        ;;
    esac
  done

  if [[ "$dry_run" -ne 1 && "$force" -ne 1 ]]; then
    prompt_for_purge
  fi

  run_cleanup_targets "purge" "$dry_run"
}

print_usage() {
  echo "$PROG - Orac stack control (version: ${ORAC_VERSION})"
  echo "Usage: $0 {start|stop|restart|status|logs [ai|db]|dump-context|clean [--dry-run|-n]|purge [--dry-run|-n] [--force|-f]}"
  echo
  echo "Commands:"
  echo "  start"
  echo "    Start the Oracle DB/ORDS container if needed, wait for it to be ready,"
  echo "    then start the Orac AI engine process."
  echo
  echo "  stop"
  echo "    Stop the Orac AI engine process, then stop the Oracle DB/ORDS container."
  echo
  echo "  restart"
  echo "    Stop and then start the full Orac stack."
  echo
  echo "  status"
  echo "    Show container status for the DB/ORDS tier and process status for the"
  echo "    Orac AI engine."
  echo
  echo "  logs [ai|db]"
  echo "    Tail logs for one part of the stack."
  echo "    ai   - follow the Orac AI engine log."
  echo "    db   - follow the Oracle DB/ORDS container log."
  echo "    If omitted, defaults to db."
  echo
  echo "  dump-context"
  echo "    Arm a one-shot context dump for the next Orac request."
  echo "    The next handled request writes debug files under logs/_debug, then the"
  echo "    trigger is cleared automatically."
  echo
  echo "  clean [--dry-run|-n]"
  echo "    Remove safe Orac runtime artefacts such as stale PID files, debug"
  echo "    dumps, cache files, and generated bytecode caches."
  echo
  echo "  purge [--dry-run|-n] [--force|-f]"
  echo "    Remove Orac runtime artefacts more aggressively, including the Orac"
  echo "    log and other generated runtime files. Requires confirmation or --force."
  exit 1
}

# -----------------------------------------------------------------------------#
# Dispatch
# -----------------------------------------------------------------------------#
case "${1:-}" in
  start)   start_orac_stack ;;
  stop)    stop_orac_stack ;;
  restart) echo "🔄 Restarting Orac stack..."; stop_orac_stack; start_orac_stack ;;
  status)  status_orac_stack ;;
  logs)    shift || true; logs_orac_stack "${1:-}" ;;
  dump-context) dump_context_orac_stack ;;
  clean)   clean_orac_runtime "$@" ;;
  purge)   purge_orac_runtime "$@" ;;
  *)       print_usage ;;
esac
