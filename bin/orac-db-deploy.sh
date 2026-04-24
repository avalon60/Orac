#!/usr/bin/env bash
################################################################################
#
# Author  : Clive Bostock
# Date    : 2025-08-01
# Purpose : Deploy and start the Orac database container for the db-local
#           topology.
#
#           This script is primarily intended to facilitate a fresh
#           installation or forced rebuild of Orac's database container.
#
################################################################################

set -e
# ------------------------------------------------------------------------------
# Timing
# ------------------------------------------------------------------------------
SCRIPT_START_EPOCH=$(date +%s)
SCRIPT_START_HUMAN=$(date "+%Y-%m-%d %H:%M:%S")

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


print_runtime_summary() {
  local end_epoch end_human elapsed mins secs

  end_epoch=$(date +%s)
  end_human=$(date "+%Y-%m-%d %H:%M:%S")

  elapsed=$(( end_epoch - SCRIPT_START_EPOCH ))
  mins=$(( elapsed / 60 ))
  secs=$(( elapsed % 60 ))

  echo
  echo "⏱  Script start : ${SCRIPT_START_HUMAN}"
  echo "⏱  Script end   : ${end_human}"
  printf "⏱  Duration     : %02dm %02ds\n" "$mins" "$secs"
}

usage() {
  cat <<EOF
Usage: $PROG [--dry-run|-n] [--force|-f] [--no-cache] [--check-prereqs] [--help|-h]
Initialise and start the Orac database container (db-local topology).
EOF
  exit 0
}

require_command() {
  local command_name="$1"
  local error_message="$2"

  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "❌ ${error_message}"
    return 1
  fi
}

validate_port() {
  local port_name="$1"
  local port_value="$2"

  if [[ ! "$port_value" =~ ^[0-9]+$ ]] || (( port_value < 1 || port_value > 65535 )); then
    echo "❌ ${port_name} must be a numeric TCP port in the range 1-65535. Current value: ${port_value}"
    return 1
  fi
}

ensure_oradata_directory() {
  local desired_owner="54321"
  local desired_group="54321"
  local desired_mode="750"
  local current_owner=""
  local current_group=""
  local current_mode=""

  if [[ -z "$ORADATA_DIR" || "$ORADATA_DIR" != /* ]]; then
    echo "❌ ORADATA_DIR must be set to an absolute host path. Current value: ${ORADATA_DIR:-<unset>}"
    return 1
  fi

  if [[ -d "${ORADATA_DIR}" ]]; then
    echo "📁 Oracle data dir exists: ${ORADATA_DIR}"
  else
    echo "📁 Creating Oracle data dir: ${ORADATA_DIR}"
    sudo mkdir -p "${ORADATA_DIR}"
  fi

  current_owner=$(stat -c '%u' "${ORADATA_DIR}")
  current_group=$(stat -c '%g' "${ORADATA_DIR}")
  current_mode=$(stat -c '%a' "${ORADATA_DIR}")

  if [[ "$current_owner" != "$desired_owner" || "$current_group" != "$desired_group" ]]; then
    echo "🔧 Setting Oracle data dir ownership to ${desired_owner}:${desired_group}"
    sudo chown -R "${desired_owner}:${desired_group}" "${ORADATA_DIR}"
  fi

  if [[ "$current_mode" != "$desired_mode" ]]; then
    echo "🔧 Setting Oracle data dir permissions to ${desired_mode}"
    sudo chmod "${desired_mode}" "${ORADATA_DIR}"
  fi
}

check_prerequisites() {
  local failed=0

  echo "🔍 Checking prerequisites..."

  if [[ "$(uname -s)" != "Linux" ]]; then
    echo "❌ Orac server deployment is supported on Linux only."
    failed=1
  fi

  if [[ ! -f "$ENV_FILE" ]]; then
    echo "❌ Missing env file: $ENV_FILE"
    failed=1
  fi

  require_command docker "Docker is not installed or not available in PATH." || failed=1
  require_command sudo "sudo is required by this script to manage the Oracle data directory." || failed=1
  require_command grep "grep is required by this script." || failed=1

  if command -v docker >/dev/null 2>&1; then
    docker info >/dev/null 2>&1 || {
      echo "❌ Docker daemon not running or not accessible."
      failed=1
    }

    docker buildx version >/dev/null 2>&1 || {
      echo "❌ Docker Buildx is required. Install or enable the buildx plugin."
      failed=1
    }
  fi

  if [[ ! -d "$ORA_DOCKER_DIR" ]]; then
    echo "❌ Docker build directory not found: $ORA_DOCKER_DIR"
    failed=1
  fi

  if [[ ! -x "${BIN_DIR}/dbconn-mgr.sh" ]]; then
    echo "❌ Missing executable helper: ${BIN_DIR}/dbconn-mgr.sh"
    failed=1
  fi

  if [[ ! -x "${BIN_DIR}/dbconn-property.sh" ]]; then
    echo "❌ Missing executable helper: ${BIN_DIR}/dbconn-property.sh"
    failed=1
  fi

  validate_port "PORT_SQLNET" "${PORT_SQLNET}" || failed=1
  validate_port "PORT_HTTP" "${PORT_HTTP}" || failed=1
  validate_port "PORT_EM" "${PORT_EM}" || failed=1

  if [[ -n "$ORADATA_DIR" && "$ORADATA_DIR" == /* ]]; then
    ensure_oradata_directory || failed=1
  else
    echo "❌ ORADATA_DIR must be set to an absolute host path. Current value: ${ORADATA_DIR:-<unset>}"
    failed=1
  fi

  if [[ "$TOPOLOGY" != "db-local" ]]; then
    echo "❌ This init script is for db-local only. Current TOPOLOGY=$TOPOLOGY"
    failed=1
  fi

  if (( failed )); then
    echo "❌ Prerequisite check failed."
    return 1
  fi

  echo "✅ Prerequisite check passed."
}

wait_for_orac_deploy() {
  local container="${CONTAINER_NAME:-orac-db}"
  local interval=60
  local timeout=1800   # 30 minutes
  local marker="=  ORAC deployment complete ="
  local failure_patterns=(
    "!! Halting due to STOP_ON_ERROR=1."
    "ERROR at line 1:"
    "Database configuration failed. Check logs under '/opt/oracle/cfgtoollogs/dbca'."
    "DATABASE SETUP WAS NOT SUCCESSFUL!"
  )

  local start_time
  start_time=$(date +%s)

  echo "⏳ Waiting for Orac deployment to complete..."

  while true; do
    if docker logs "$container" 2>&1 | grep -q "$marker"; then
      echo "Orac is deployed!"
      return 0
    fi

    local pattern
    for pattern in "${failure_patterns[@]}"; do
      if docker logs "$container" 2>&1 | grep -q "$pattern"; then
        echo "❌ Detected deployment failure in container logs."
        echo "   Check container logs: docker logs $container"
        return 1
      fi
    done

    # Check container still running
    if ! docker ps --format '{{.Names}}' | grep -qw "$container"; then
      echo "❌ Container '$container' stopped unexpectedly."
      return 1
    fi

    local now elapsed
    now=$(date +%s)
    elapsed=$((now - start_time))

    if (( elapsed >= timeout )); then
      echo "⚠️ WARNING: Orac deployment did not complete within 30 minutes."
      echo "   Check container logs: docker logs $container"
      return 1
    fi

    echo "Deployment still in progress. Checking again in ${interval}s..."
    sleep "$interval"
  done
}

cleanup_oradata_markers() {
  echo "🧹 Cleaning old DB markers under ${ORADATA_DIR}..."
  sudo rm -f "${ORADATA_DIR}/.FREE.created" || true
  sudo rm -rf "${ORADATA_DIR}/dbconfig" "${ORADATA_DIR}/FREE" || true
}

is_retryable_oracle_boot_failure() {
  local container="$1"

  docker logs "$container" 2>&1 | grep -q "ORA-12721: operation cannot execute when other sessions are active" &&
    docker logs "$container" 2>&1 | grep -q "Database configuration failed. Check logs under '/opt/oracle/cfgtoollogs/dbca'."
}

retry_oracle_bootstrap() {
  local container="$1"
  local attempt="$2"
  local max_retries="$3"

  if (( attempt > max_retries )); then
    return 1
  fi

  if ! is_retryable_oracle_boot_failure "$container"; then
    return 1
  fi

  echo "⚠️  Detected intermittent Oracle bootstrap failure (ORA-12721)."
  echo "🔁 Retrying container creation (${attempt}/${max_retries})..."

  docker rm -f "$container" >/dev/null 2>&1 || true
  cleanup_oradata_markers
  ensure_oradata_directory

  return 0
}

run_container_with_retries() {
  local max_retries=2
  local attempt=0

  while true; do
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
    echo -e "⏳ Deploying Orac components..."

    if wait_for_orac_deploy; then
      return 0
    fi

    attempt=$(( attempt + 1 ))
    if ! retry_oracle_bootstrap "${CONTAINER_NAME}" "${attempt}" "${max_retries}"; then
      return 1
    fi
  done
}

trap print_runtime_summary EXIT

# Flags
DRY_RUN=0; FORCE=0; NO_CACHE=0; CHECK_PREREQS=0
for arg in "$@"; do
  case $arg in
    --dry-run|-n) DRY_RUN=1 ;;
    --force|-f)   FORCE=1 ;;
    --no-cache)   NO_CACHE=1 ;;
    --check-prereqs) CHECK_PREREQS=1 ;;
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

check_prerequisites

[[ $CHECK_PREREQS -eq 1 ]] && { echo "🔎 Prerequisites only. Exiting."; exit 0; }
[[ $DRY_RUN -eq 1 ]] && { echo "🧪 Dry run. Exiting."; exit 0; }

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
  cleanup_oradata_markers
fi

# Ensure oradata dir with oracle uid/gid (54321) and expected permissions
ensure_oradata_directory

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

run_container_with_retries

echo -e "\nDone."
