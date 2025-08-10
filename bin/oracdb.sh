#!/usr/bin/env bash
################################################################################
# Author  : Clive Bostock
# Date    : 2025-07-25
#   Script: oracdb.sh
# Purpose : Unified script to control Orac (Oracle DB + ORDS + LLM etc.)
################################################################################

set -e
PROG=$(basename "$0")

# Paths
realpath() { [[ $1 = /* ]] && echo "$1" || echo "$PWD/${1#./}"; }
SCRIPT_DIR=$(dirname "$(realpath "${BASH_SOURCE[0]}")")
PROJECT_DIR=$(dirname "$SCRIPT_DIR")
CONFIG_DIR=${PROJECT_DIR}/resources/config
CTL_DIR=${PROJECT_DIR}/src/controller
DEFAULTS_FILE="${CONFIG_DIR}/init-defaults.ini"
ORA_DOCKER_DIR=${PROJECT_DIR}/resources/docker/oracle
COMPOSE_FILE="${ORA_DOCKER_DIR}/docker-compose.yaml"
ENV_FILE="${CONFIG_DIR}/orac.env"

ORACLE_PASSWORD=$("$SCRIPT_DIR/dbconn-property.sh" -n orac -p password)
if [[ -z "$ORACLE_PASSWORD" ]]
then
  echo "❌ Could not retrieve Oracle password from credential store."
  exit 1
fi

# Default values
# Load Orac environment settings from orac.env
if [[ -f "$ENV_FILE" ]]; then
  source $ENV_FILE
else
  echo "⚠️ Defaults file not found: $ENV_FILE. Using hardcoded values."
  ORADATA_DIR="/u01/orac-db/oradata"
  CONTAINER_NAME="orac-db"
  PORT_SQLNET=1521
  PORT_HTTP=8042    # The meaning of life ;o)
  PORT_EM=5500
  IMAGE_TAG="23.5.0-lite"
fi


# Extract Orac version
ORAC_VERSION=$(grep "__version__" "${CTL_DIR}/__init__.py" | cut -d'"' -f2)

stop_orac_stack() {
  echo "🛑 Stopping Orac stack..."
  if docker ps -a --format '{{.Names}}' | grep -wq "$CONTAINER_NAME"; then
    docker stop "$CONTAINER_NAME" >/dev/null || true
    echo "⏹️  '$CONTAINER_NAME' stopped."
  else
    echo "ℹ️ No container named '$CONTAINER_NAME' to stop."
  fi
}

start_orac_stack() {
  echo "🚀 Starting Orac stack (Oracle DB + ORDS + LLM)..."
  ensure_env

  if docker ps -a --format '{{.Names}}' | grep -wq "$CONTAINER_NAME"; then
    if [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME")" == "true" ]]; then
      echo "✅ '$CONTAINER_NAME' is already running."
    else
      echo "▶️  Starting existing container '$CONTAINER_NAME'..."
      docker start "$CONTAINER_NAME" >/dev/null
      echo "✅ Started."
    fi
  else
    echo "❌ No container named '$CONTAINER_NAME' found."
    echo "👉 Run the provisioner first: bin/oracdb-init.sh"
    exit 1
  fi

  echo "🧠 (optional) Starting Orac AI engine..."
  # TODO
}

print_usage() {
  echo "$PROG - Orac stack control"
  echo "Usage: $0 {start|stop|restart|status|logs}"
  exit 1
}

ensure_env() {
  export ORACLE_PWD="${ORACLE_PASSWORD}"
  export ORADATA_DIR="${ORADATA_DIR}"
  export PORT_SQLNET="${PORT_SQLNET}"
  export PORT_HTTP="${PORT_HTTP}"
  export PORT_EM="${PORT_EM}"
}


case "$1" in
  start)   start_orac_stack ;;
  stop)    stop_orac_stack ;;
  restart)
    echo "🔄 Restarting Orac stack..."
    "$0" stop
    "$0" start
    ;;
  status)
    echo "📋 Orac stack status:"
    docker ps -a | grep "$CONTAINER_NAME" || echo "⚠️  Container '$CONTAINER_NAME' not found."
    ;;
  logs)
    echo "📜 Tailing Orac container logs..."
    docker logs -f "$CONTAINER_NAME"
    ;;
  *)
    print_usage
    ;;
esac

