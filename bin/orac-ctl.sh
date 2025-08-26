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

print_usage() {
  echo "$PROG - Orac stack control (version: ${ORAC_VERSION})"
  echo "Usage: $0 {start|stop|restart|status|logs [ai|db]}"
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
  *)       print_usage ;;
esac

