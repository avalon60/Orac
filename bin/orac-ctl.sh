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

print_usage() {
  echo "$PROG - Orac stack control (version: ${ORAC_VERSION})"
  echo "Usage: $0 {start|stop|restart|status|logs [ai|db]|dump-context}"
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
  *)       print_usage ;;
esac
