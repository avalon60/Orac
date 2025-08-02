#!/usr/bin/env bash
################################################################################
# Author  : Clive Bostock
# Date    : 2025-07-25
#   Script: oracledb.sh
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
  start)
    echo "🚀 Starting Orac stack (Oracle DB + ORDS + LLM)..."
    ensure_env
    docker compose --project-name "$CONTAINER_NAME" -f "$COMPOSE_FILE" up -d
    echo "🧠 Starting Orac AI engine..."
    # TODO: Launch LLM and Orac Python modules here
    ;;
  stop)
    echo "🛑 Stopping Orac stack..."
    docker compose --project-name "$CONTAINER_NAME" -f "$COMPOSE_FILE" down
    ;;
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

