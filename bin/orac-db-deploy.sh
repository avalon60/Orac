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

set -euo pipefail
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
DEFAULT_STACK_DIR="${ORA_DOCKER_DIR}"
ORAC_STACK_DIR="${ORAC_STACK_DIR:-$DEFAULT_STACK_DIR}"
ORAC_COMPOSE_FILE="${ORAC_COMPOSE_FILE:-${ORAC_STACK_DIR}/docker-compose.yaml}"
ORAC_ENV_FILE="${ORAC_ENV_FILE:-${CONFIG_DIR}/orac.env}"
ENV_FILE="$ORAC_ENV_FILE"
COMPOSE_FILE="$ORAC_COMPOSE_FILE"
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

Stack files:
  ORAC_STACK_DIR defaults to ${DEFAULT_STACK_DIR}
  ORAC_COMPOSE_FILE defaults to \$ORAC_STACK_DIR/docker-compose.yaml
  ORAC_ENV_FILE defaults to ${CONFIG_DIR}/orac.env
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

compose_cmd() {
  docker compose \
    --env-file "$ORAC_ENV_FILE" \
    -f "$ORAC_COMPOSE_FILE" \
    "$@"
}

docker_container_exists() {
  local container_name="$1"

  docker ps -a --format '{{.Names}}' | grep -Fxq "$container_name"
}

container_compose_project() {
  local container_name="$1"

  docker inspect -f '{{ index .Config.Labels "com.docker.compose.project" }}' "$container_name" 2>/dev/null || true
}

remove_existing_db_container() {
  local container_name="$1"
  local compose_project

  if ! docker_container_exists "$container_name"; then
    return 0
  fi

  if [[ "${FORCE:-0}" -ne 1 ]]; then
    echo "⚠️  Container '$container_name' already exists. Use --force to recreate."
    return 1
  fi

  compose_project="$(container_compose_project "$container_name")"
  if [[ -n "$compose_project" && "$compose_project" != "<no value>" ]]; then
    echo "♻️  Removing Compose-managed DB service: orac-db"
    compose_cmd stop orac-db >/dev/null || true
    compose_cmd rm -f orac-db >/dev/null
    return 0
  fi

  echo "⚠️  Container '$container_name' is not Compose-managed."
  echo "♻️  Removing legacy DB container because --force was supplied: $container_name"
  docker rm -f "$container_name" >/dev/null
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

  if [[ ! -f "$ORAC_ENV_FILE" ]]; then
    echo "❌ Missing env file: $ORAC_ENV_FILE"
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

  if [[ ! -f "$ORAC_COMPOSE_FILE" ]]; then
    echo "❌ Compose file not found: $ORAC_COMPOSE_FILE"
    failed=1
  fi

  if [[ -f "$ORAC_ENV_FILE" && -f "$ORAC_COMPOSE_FILE" ]] && command -v docker >/dev/null 2>&1; then
    compose_cmd config >/dev/null || {
      echo "❌ Docker Compose configuration is invalid."
      failed=1
    }
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
    "Database configuration failed. Check logs under '/opt/oracle/cfgtoollogs/dbca'."
    "DATABASE SETUP WAS NOT SUCCESSFUL!"
    "ORAC_APEX_SETUP_FAILED"
    "ORAC_ORDS_SETUP_FAILED"
    "ORAC_ORDS_START_FAILED"
    "ORAC_DEPLOYMENT_INCOMPLETE"
  )

  local start_time
  local logs_snapshot
  start_time=$(date +%s)

  echo "⏳ Waiting for Orac deployment to complete..."

  while true; do
    logs_snapshot="$(docker logs "$container" 2>&1 || true)"

    if grep -Fq "$marker" <<<"$logs_snapshot"; then
      if ! verify_container_ords_config "$container"; then
        echo "❌ Deployment marker was found, but ORDS validation failed."
        echo "   Check container logs: docker logs $container"
        return 1
      fi
      if ! wait_for_ords_apex_app "$container"; then
        echo "❌ ORDS did not begin serving the Orac APEX app in time."
        echo "   Check ORDS logs in the container: /tmp/ords-start.log"
        return 1
      fi
      echo "Orac is deployed!"
      return 0
    fi

    local pattern
    for pattern in "${failure_patterns[@]}"; do
      if grep -Fq "$pattern" <<<"$logs_snapshot"; then
        echo "❌ Detected deployment failure in container logs."
        echo "   Matched marker: $pattern"
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

verify_container_ords_config() {
  local container="$1"
  local output
  local metadata_status

  metadata_status="$(docker exec "$container" bash -lc '
    sqlplus -L -s / as sysdba <<SQL
set heading off feedback off pagesize 0 verify off echo off
whenever sqlerror exit failure rollback
alter session set container=FREEPDB1;
select case
         when exists (
                select 1
                  from dba_objects
                 where owner = '\''ORDS_METADATA'\''
                   and object_name = '\''ORDS'\''
                   and object_type = '\''PACKAGE'\''
                   and status = '\''VALID'\''
              )
          and not exists (
                select 1
                  from dba_objects
                 where owner = '\''ORDS_METADATA'\''
                   and status <> '\''VALID'\''
              )
         then '\''VALID'\''
         else '\''INVALID'\''
       end
  from dual;
exit
SQL
  ' 2>&1)" || {
    echo "❌ ORDS metadata validation command failed:"
    echo "$metadata_status"
    return 1
  }

  if ! grep -Eq '(^|[[:space:]])VALID([[:space:]]|$)' <<<"$metadata_status"; then
    echo "❌ ORDS metadata objects are not VALID:"
    echo "$metadata_status"
    return 1
  fi

  output="$(docker exec "$container" bash -lc '
    if [[ ! -d /home/oracle/orac/ords/conf ]]; then
      echo "missing ORDS config directory: /home/oracle/orac/ords/conf"
      exit 1
    fi
    if [[ ! -L /home/oracle/orac/ords/conf ]] ||
       [[ "$(readlink /home/oracle/orac/ords/conf)" != "/opt/oracle/oradata/orac/ords/conf" ]]; then
      echo "ORDS runtime config is not linked to persistent config: /home/oracle/orac/ords/conf"
      exit 1
    fi
    /home/oracle/orac/ords/bin/ords --config /home/oracle/orac/ords/conf config list 2>&1
  ' 2>&1)" || {
    echo "❌ ORDS config validation command failed:"
    echo "$output"
    return 1
  }

  if grep -Fq "does not contain database pool default" <<<"$output"; then
    echo "❌ ORDS default database pool is missing:"
    echo "$output"
    return 1
  fi

  return 0
}

wait_for_ords_apex_app() {
  local container="$1"
  local interval=5
  local timeout=180
  local start_time now elapsed output

  start_time=$(date +%s)
  echo "⏳ Waiting for ORDS to serve APEX application 1042..."

  while true; do
    output="$(docker exec "$container" bash -lc '
      curl -sS -i --max-time 10 "http://127.0.0.1:8080/ords/r/orac/orac-administration1042/login" 2>&1 || true
    ' 2>&1)"

    if grep -Eq 'APEX_APP_ID: 1042|Orac Administration - Log In|HTTP/[0-9.]+ 200' <<<"$output" &&
       ! grep -Eq 'ERR-7620|Application not found|Could not determine workspace' <<<"$output"; then
      echo "✅ ORDS is serving APEX application 1042."
      return 0
    fi

    now=$(date +%s)
    elapsed=$((now - start_time))
    if (( elapsed >= timeout )); then
      echo "❌ Timed out waiting for ORDS/APEX application 1042."
      echo "$output"
      return 1
    fi

    echo "ORDS/APEX not ready yet. Checking again in ${interval}s..."
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

  if docker_container_exists "$container"; then
    local compose_project
    compose_project="$(container_compose_project "$container")"
    if [[ -n "$compose_project" && "$compose_project" != "<no value>" ]]; then
      compose_cmd stop orac-db >/dev/null || true
      compose_cmd rm -f orac-db >/dev/null || true
    else
      docker rm -f "$container" >/dev/null 2>&1 || true
    fi
  fi
  cleanup_oradata_markers
  ensure_oradata_directory

  return 0
}

run_container_with_retries() {
  local max_retries=2
  local attempt=0

  while true; do
    echo "🚀 Launching Compose service 'orac-db' as container '${CONTAINER_NAME}' ..."
    export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-orac}"
    export ORAC_DB_CONTAINER_NAME="${ORAC_DB_CONTAINER_NAME:-$CONTAINER_NAME}"
    export CONTAINER_NAME="$ORAC_DB_CONTAINER_NAME"
    export ORAC_IMAGE_NAME ORAC_IMAGE_TAG ORACLE_PWD ORADATA_DIR
    export PORT_SQLNET PORT_HTTP PORT_EM
    compose_cmd up -d orac-db

    echo "🎉 '${CONTAINER_NAME}' is up"
    echo "📡 SQL*Net  : ${PORT_SQLNET}"
    echo "🌐 ORDS/HTTP: http://localhost:${PORT_HTTP}"
    echo "🌐 APEX admin: http://localhost:${PORT_HTTP}/ords/r/orac/orac-administration1042/login"
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

main() {
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
[[ -f "$ORAC_ENV_FILE" ]] || { echo "❌ Missing env: $ORAC_ENV_FILE"; exit 1; }
# shellcheck source=/dev/null
source "$ORAC_ENV_FILE"

# Defaults / sanity
: "${TOPOLOGY:=db-local}"
: "${CONTAINER_NAME:=orac-db}"
: "${ORAC_DB_CONTAINER_NAME:=$CONTAINER_NAME}"
: "${ORADATA_DIR:=/u01/orac-db/oradata}"
: "${PORT_SQLNET:=1521}"
: "${PORT_HTTP:=8080}"
: "${PORT_EM:=5500}"
: "${ORAC_IMAGE_NAME:=orac}"
: "${ORAC_IMAGE_TAG:=latest}"

DOCKER_IMAGE="${ORAC_IMAGE_NAME}:${ORAC_IMAGE_TAG}"
CONTAINER_NAME="$ORAC_DB_CONTAINER_NAME"

if [[ "$TOPOLOGY" != "db-local" ]]; then
  echo "❌ This init script is for db-local only. Current TOPOLOGY=$TOPOLOGY"
  echo "   (Skip DB container when using remote topologies.)"
  exit 1
fi

# Version
ORAC_VERSION=$(grep -m1 "__version__" "${CTL_DIR}/__init__.py" | cut -d'"' -f2 || true)

echo "$PROG"
echo "Orac version     : ${ORAC_VERSION:-n/a}"
echo "📁 Stack dir     : ${ORAC_STACK_DIR}"
echo "📄 Compose file  : ${ORAC_COMPOSE_FILE}"
echo "🔧 Env file      : ${ORAC_ENV_FILE}"
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

remove_existing_db_container "$CONTAINER_NAME"

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
}

if [[ "${ORAC_DB_DEPLOY_LIB_ONLY:-0}" == "1" ]]; then
  return 0 2>/dev/null || exit 0
fi

main "$@"
