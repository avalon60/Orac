#!/usr/bin/env bash
################################################################################
# Author  : Clive Bostock
# Date    : 2025-08-01
# Purpose : Initialise and start the Orac database container (db-local).
################################################################################

set -e
PROG=$(basename "$0")

# realpath shim
realpath() { [[ $1 = /* ]] && echo "$1" || echo "$PWD/${1#./}"; }

# Paths
SCRIPT_DIR=$(dirname "$(realpath "${BASH_SOURCE[0]}")")
ORAC_PROJECT_HOME=$(dirname "$SCRIPT_DIR")
BIN_DIR="${ORAC_PROJECT_HOME}/bin"
CONFIG_DIR="${ORAC_PROJECT_HOME}/resources/config"
ORA_DOCKER_DIR="${ORAC_PROJECT_HOME}/resources/docker/oracle"
CTL_DIR="${ORAC_PROJECT_HOME}/src/controller"
ENV_FILE="${CONFIG_DIR}/orac.env"
CREDENTIALS_FILE="${HOME}/.Orac/dsn_credentials.ini"

usage() {
  cat <<EOF
Usage: $PROG [--dry-run|-n] [--force|-f] [--no-cache] [--help|-h]
Initialise and start the Orac database container (db-local topology).
EOF
  exit 0
}

# Flags
DRY_RUN=0; FORCE=0; NO_CACHE=0
for arg in "$@"; do
  case $arg in
    --dry-run|-n) DRY_RUN=1 ;;
    --force|-f)   FORCE=1 ;;
    --no-cache)   NO_CACHE=1 ;;
    --help|-h)    usage ;;
    *) echo "❌ Unknown option: $arg"; usage ;;
  esac
done

# Load env
[[ -f "$ENV_FILE" ]] || { echo "❌ Missing env: $ENV_FILE"; exit 1; }
# shellcheck source=/dev/null
source "$ENV_FILE"

# Defaults / sanity
: "${TOPOLOGY:=db-local}"
: "${CONTAINER_NAME:=orac-db}"
: "${ORADATA_DIR:=/u01/orac-db/oradata}"
: "${PORT_SQLNET:=1521}"
: "${PORT_HTTP:=8080}"
: "${PORT_EM:=5500}"
: "${ORAC_IMAGE_NAME:=orac}"
: "${ORAC_IMAGE_TAG:=latest}"

DOCKER_IMAGE="${ORAC_IMAGE_NAME}:${ORAC_IMAGE_TAG}"

if [[ "$TOPOLOGY" != "db-local" ]]; then
  echo "❌ This init script is for db-local only. Current TOPOLOGY=$TOPOLOGY"
  echo "   (Skip DB container when using remote topologies.)"
  exit 1
fi

# Version
ORAC_VERSION=$(grep -m1 "__version__" "${CTL_DIR}/__init__.py" | cut -d'"' -f2 || true)

echo "$PROG"
echo "Orac version     : ${ORAC_VERSION:-n/a}"
echo "🔧 Env file      : ${ENV_FILE}"
echo "📋 Config:"
echo " CONTAINER_NAME  : ${CONTAINER_NAME}"
echo " DOCKER_IMAGE    : ${DOCKER_IMAGE}"
echo " ORADATA_DIR     : ${ORADATA_DIR}"
echo " PORTS           : sqlnet=${PORT_SQLNET}, http=${PORT_HTTP}, em=${PORT_EM}"
echo " TOPOLOGY        : ${TOPOLOGY}"
echo

[[ $DRY_RUN -eq 1 ]] && { echo "🧪 Dry run. Exiting."; exit 0; }

# Docker up?
command -v docker >/dev/null || { echo "❌ Docker not installed"; exit 1; }
docker info >/dev/null 2>&1 || { echo "❌ Docker daemon not running"; exit 1; }

# Existing container
if docker ps -a --format '{{.Names}}' | grep -qw "$CONTAINER_NAME"; then
  if [[ $FORCE -eq 1 ]]; then
    echo "♻️  Removing existing container: $CONTAINER_NAME"
    docker rm -f "$CONTAINER_NAME" >/dev/null
  else
    echo "⚠️  Container '$CONTAINER_NAME' already exists. Use --force to recreate."
    exit 1
  fi
fi

# Clean oradata (optional, destructive bits only when --force)
if [[ $FORCE -eq 1 ]]; then
  echo "🧹 Cleaning old DB markers under ${ORADATA_DIR}..."
  sudo rm -f  "${ORADATA_DIR}/.FREE.created" || true
  sudo rm -rf "${ORADATA_DIR}/dbconfig" "${ORADATA_DIR}/FREE" || true
fi

# Ensure oradata dir with oracle uid/gid (54321)
if [[ -d "${ORADATA_DIR}" ]]; then
  echo "📁 Oracle data dir exists: ${ORADATA_DIR}"
else
  echo "📁 Creating Oracle data dir: ${ORADATA_DIR}"
  sudo mkdir -p "${ORADATA_DIR}"
fi
sudo chown -R 54321:54321 "${ORADATA_DIR}"

# Ensure credentials
if [[ ! -f "$CREDENTIALS_FILE" ]] || ! grep -q "^\[orac\]" "$CREDENTIALS_FILE"; then
  echo "🔐 Initializing credentials for 'orac'..."
  "${BIN_DIR}/dbconn-mgr.sh" -c orac
fi

# Get Oracle password
ORACLE_PASSWORD=$("${BIN_DIR}/dbconn-property.sh" -n orac -p password)
[[ -n "$ORACLE_PASSWORD" ]] || { echo "❌ Could not retrieve Oracle password"; exit 1; }
export ORACLE_PWD="$ORACLE_PASSWORD"

# Build image via bake (tag from env)
pushd "$ORA_DOCKER_DIR" >/dev/null
echo "🔨 Building image ${DOCKER_IMAGE} ..."
BAKE_ARGS=(orac --allow="fs.read=${ORAC_PROJECT_HOME}" --set "orac.tags=${DOCKER_IMAGE}")
[[ $NO_CACHE -eq 1 ]] && BAKE_ARGS+=(--no-cache)
docker buildx bake "${BAKE_ARGS[@]}"
popd >/dev/null

# Run container
echo "🚀 Launching container '${CONTAINER_NAME}' ..."
docker run -d \
  --name "${CONTAINER_NAME}" \
  -p "${PORT_SQLNET}:1521" \
  -p "${PORT_HTTP}:8080" \
  -p "${PORT_EM}:5500" \
  -e ORACLE_PWD="${ORACLE_PASSWORD}" \
  -v "${ORADATA_DIR}:/opt/oracle/oradata" \
  "${DOCKER_IMAGE}"

echo "🎉 '${CONTAINER_NAME}' is up"
echo "📡 SQL*Net  : ${PORT_SQLNET}"
echo "🌐 ORDS/HTTP: http://localhost:${PORT_HTTP}"
echo "📂 Oradata  : ${ORADATA_DIR}"

