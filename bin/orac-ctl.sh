#!/usr/bin/env bash
################################################################################
# Author  : Clive Bostock
# Date    : 2025-08-25
# Script  : orac-ctl.sh
# Purpose : Unified script to control Orac (Oracle DB + ORDS + AI engine)
################################################################################

set -euo pipefail
PROG=$(basename "$0")

# -----------------------------------------------------------------------------#
# Paths
# -----------------------------------------------------------------------------#
realpath() { [[ $1 = /* ]] && echo "$1" || echo "$PWD/${1#./}"; }
SCRIPT_DIR=$(dirname "$(realpath "${BASH_SOURCE[0]}")")
PROJECT_DIR=$(dirname "$SCRIPT_DIR")
CONFIG_DIR=${PROJECT_DIR}/resources/config
CONFIG_FILE="${ORAC_CONFIG_FILE:-${CONFIG_DIR}/orac.ini}"
CTL_DIR=${PROJECT_DIR}/src/controller
DEFAULTS_FILE="${CONFIG_DIR}/init-defaults.ini"
ORA_DOCKER_DIR=${PROJECT_DIR}/resources/docker/oracle
DEFAULT_STACK_DIR="${ORA_DOCKER_DIR}"
ORAC_STACK_DIR="${ORAC_STACK_DIR:-$DEFAULT_STACK_DIR}"
ORAC_COMPOSE_FILE="${ORAC_COMPOSE_FILE:-${ORAC_STACK_DIR}/docker-compose.yaml}"
ORAC_ENV_FILE="${ORAC_ENV_FILE:-${CONFIG_DIR}/orac.env}"
REPO_COMPOSE_FILE="${ORA_DOCKER_DIR}/docker-compose.yaml"
REPO_ENV_FILE="${CONFIG_DIR}/orac.env"
RUN_DIR="/run/orac"
DUMP_CONTEXT_FLAG="${RUN_DIR}/dump-context.once"
ORAC_LOG_FILE="${PROJECT_DIR}/logs/orac.log"
ORAC_DEBUG_DIR="${PROJECT_DIR}/logs/_debug"
ORAC_CACHE_DIR="${PROJECT_DIR}/var/cache"
BUILD_LOG_FILE="${PROJECT_DIR}/build.log"
DOCKER_LOG_FILE="${PROJECT_DIR}/docker.log"
ORAC_DISPLAY_SH="${SCRIPT_DIR}/orac-display.sh"
KOKORO_CPU_IMAGE="ghcr.io/remsky/kokoro-fastapi-cpu:latest"
KOKORO_GPU_IMAGE="ghcr.io/remsky/kokoro-fastapi-gpu:latest"

# AI server control script (owns PID, /run/orac, logs)
ORAC_SH="${SCRIPT_DIR}/orac.sh"
if [[ "${ORAC_CTL_LIB_ONLY:-0}" != "1" && ! -x "$ORAC_SH" ]]; then
  echo "❌ Missing or non-executable: $ORAC_SH"
  echo "   Ensure it exists and run:  chmod +x \"$ORAC_SH\""
  exit 1
fi

# Extract Orac version (controller package)
ORAC_VERSION=$(grep -m1 "__version__" "${CTL_DIR}/__init__.py" 2>/dev/null | cut -d'"' -f2 || echo "dev")

# -----------------------------------------------------------------------------#
# Helpers
# -----------------------------------------------------------------------------#
load_stack_env() {
  if [[ ! -f "$ORAC_ENV_FILE" ]]; then
    return 1
  fi

  set -a
  # shellcheck disable=SC1090
  source "$ORAC_ENV_FILE"
  set +a

  : "${COMPOSE_PROJECT_NAME:=orac}"
  : "${ORAC_IMAGE_NAME:=orac}"
  : "${ORAC_IMAGE_TAG:=latest}"
  : "${ORAC_DB_CONTAINER_NAME:=${CONTAINER_NAME:-orac-db}}"
  : "${CONTAINER_NAME:=$ORAC_DB_CONTAINER_NAME}"
  : "${ORADATA_DIR:=/u01/orac-db/oradata}"
  : "${PORT_SQLNET:=1521}"
  : "${PORT_HTTP:=8042}"
  : "${PORT_EM:=5500}"
  : "${KOKORO_CONTAINER_NAME:=orac-kokoro}"
  : "${KOKORO_HOST:=127.0.0.1}"
  : "${KOKORO_PORT:=8880}"
  : "${SEARXNG_CONTAINER_NAME:=orac-searxng}"
  : "${SEARXNG_HOST:=127.0.0.1}"
  : "${SEARXNG_PORT:=8888}"
  : "${SEARXNG_SECRET:=orac-local-searxng-change-me}"

  export COMPOSE_PROJECT_NAME ORAC_IMAGE_NAME ORAC_IMAGE_TAG
  export ORAC_DB_CONTAINER_NAME CONTAINER_NAME ORADATA_DIR
  export PORT_SQLNET PORT_HTTP PORT_EM
  export KOKORO_CONTAINER_NAME KOKORO_HOST KOKORO_PORT
  export SEARXNG_CONTAINER_NAME SEARXNG_HOST SEARXNG_PORT SEARXNG_SECRET
}

load_stack_env_if_present() {
  if [[ -f "$ORAC_ENV_FILE" ]]; then
    load_stack_env
  fi
}

require_compose_inputs() {
  local failed=0

  if [[ ! -f "$ORAC_COMPOSE_FILE" ]]; then
    echo "❌ Missing Compose file: $ORAC_COMPOSE_FILE"
    echo "   Set ORAC_STACK_DIR, ORAC_COMPOSE_FILE, or copy the stack from:"
    echo "   $REPO_COMPOSE_FILE"
    failed=1
  fi

  if [[ ! -f "$ORAC_ENV_FILE" ]]; then
    echo "❌ Missing Compose env file: $ORAC_ENV_FILE"
    echo "   Set ORAC_ENV_FILE or copy a starting env file from:"
    echo "   $REPO_ENV_FILE"
    failed=1
  fi

  return "$failed"
}

get_oracle_password() {
  local password

  password=$("$SCRIPT_DIR/dbconn-property.sh" -n orac -p password)
  if [[ -z "$password" ]]; then
    echo "❌ Could not retrieve Oracle password from credential store." >&2
    return 1
  fi

  printf '%s\n' "$password"
}

ensure_compose_runtime_env() {
  local oracle_password

  require_compose_inputs || return 1
  load_stack_env

  oracle_password="$(get_oracle_password)"
  export ORACLE_PWD="$oracle_password"
}

compose_cmd() {
  docker compose \
    --env-file "$ORAC_ENV_FILE" \
    -f "$ORAC_COMPOSE_FILE" \
    "$@"
}

compose_command_preview() {
  printf 'docker compose --env-file %s -f %s' "$ORAC_ENV_FILE" "$ORAC_COMPOSE_FILE"
  if [[ "$#" -gt 0 ]]; then
    printf ' %s' "$@"
  fi
  printf '\n'
}

read_ini_value() {
  local section="$1"
  local key="$2"
  local default_value="$3"
  local value=""

  if [[ ! -f "$CONFIG_FILE" ]]; then
    printf '%s\n' "$default_value"
    return 0
  fi

  value="$(
    awk -v target_section="$section" -v target_key="$key" '
      function trim(value) {
        sub(/^[[:space:]]+/, "", value)
        sub(/[[:space:]]+$/, "", value)
        return value
      }
      /^[[:space:]]*[#;]/ { next }
      /^[[:space:]]*$/ { next }
      /^\[[^]]+\]/ {
        current = $0
        gsub(/^[[:space:]]*\[/, "", current)
        gsub(/\][[:space:]]*$/, "", current)
        current = trim(current)
        next
      }
      current == target_section {
        split($0, parts, "=")
        candidate = trim(parts[1])
        if (candidate == target_key) {
          sub(/^[^=]*=/, "", $0)
          print trim($0)
          exit
        }
      }
    ' "$CONFIG_FILE"
  )"

  if [[ -z "$value" ]]; then
    printf '%s\n' "$default_value"
  else
    printf '%s\n' "$value"
  fi
}

is_truthy() {
  case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|y|on) return 0 ;;
    *) return 1 ;;
  esac
}

kokoro_readiness_url() {
  local host="$1"
  local port="$2"

  printf 'http://%s:%s/v1/audio/voices\n' "$host" "$port"
}

kokoro_readiness_url_from_base_url() {
  local base_url="$1"

  base_url="${base_url%/}"
  if [[ -z "$base_url" ]]; then
    printf '%s\n' "http://127.0.0.1:8880/v1/audio/voices"
    return 0
  fi
  if [[ "$base_url" == */v1 ]]; then
    printf '%s/audio/voices\n' "$base_url"
  else
    printf '%s/v1/audio/voices\n' "$base_url"
  fi
}

kokoro_image_for_runtime() {
  local runtime="$1"
  local override_image="$2"

  if [[ -n "$override_image" ]]; then
    printf '%s\n' "$override_image"
    return 0
  fi

  case "$runtime" in
    docker-cpu) printf '%s\n' "$KOKORO_CPU_IMAGE" ;;
    docker-gpu) printf '%s\n' "$KOKORO_GPU_IMAGE" ;;
    *) return 1 ;;
  esac
}

declare -a COMPOSE_PROFILE_ARGS=()
declare -a ACTIVE_PROFILE_NAMES=()
VOICE_PROFILE_ENABLED=0
KOKORO_EXTERNAL_ENABLED=0
KOKORO_READINESS_URL=""
KOKORO_RUNTIME_VALUE=""
SEARCH_PROFILE_ENABLED=0

add_compose_profile() {
  local profile="$1"

  COMPOSE_PROFILE_ARGS+=(--profile "$profile")
  ACTIVE_PROFILE_NAMES+=("$profile")
}

compose_profiles_text() {
  if [[ "${#ACTIVE_PROFILE_NAMES[@]}" -eq 0 ]]; then
    printf 'none\n'
    return 0
  fi

  printf '%s\n' "${ACTIVE_PROFILE_NAMES[*]}"
}

determine_voice_profile() {
  local tts_engine
  local autostart
  local runtime
  local container_name
  local image
  local image_override
  local host
  local port
  local base_url

  VOICE_PROFILE_ENABLED=0
  KOKORO_EXTERNAL_ENABLED=0
  KOKORO_READINESS_URL=""
  KOKORO_RUNTIME_VALUE=""

  tts_engine="$(read_ini_value "voice" "tts_engine" "piper" | tr '[:upper:]' '[:lower:]')"
  autostart="$(read_ini_value "voice" "tts_kokoro_autostart" "false")"
  runtime="$(read_ini_value "voice" "tts_kokoro_runtime" "docker-cpu" | tr '[:upper:]' '[:lower:]')"

  if [[ "$tts_engine" != "kokoro" ]] || ! is_truthy "$autostart"; then
    return 0
  fi

  container_name="$(read_ini_value "voice" "tts_kokoro_container_name" "${KOKORO_CONTAINER_NAME:-orac-kokoro}")"
  image_override="$(read_ini_value "voice" "tts_kokoro_image" "")"
  host="$(read_ini_value "voice" "tts_kokoro_host" "${KOKORO_HOST:-127.0.0.1}")"
  port="$(read_ini_value "voice" "tts_kokoro_port" "${KOKORO_PORT:-8880}")"
  base_url="$(read_ini_value "voice" "tts_kokoro_base_url" "http://127.0.0.1:8880/v1")"

  export KOKORO_CONTAINER_NAME="$container_name"
  export KOKORO_HOST="$host"
  export KOKORO_PORT="$port"
  KOKORO_RUNTIME_VALUE="$runtime"

  if [[ "$runtime" == "external" ]]; then
    KOKORO_EXTERNAL_ENABLED=1
    KOKORO_READINESS_URL="$(kokoro_readiness_url_from_base_url "$base_url")"
    return 0
  fi

  if [[ "$runtime" != "docker-cpu" && "$runtime" != "docker-gpu" ]]; then
    echo "⚠️  Unsupported tts_kokoro_runtime='${runtime}'. Supported values: docker-cpu, docker-gpu, external."
    echo "⚠️  Kokoro will not be managed by Compose. Piper fallback expected."
    return 0
  fi

  if ! image="$(kokoro_image_for_runtime "$runtime" "$image_override")"; then
    echo "⚠️  Unable to resolve Kokoro image for runtime '${runtime}'. Piper fallback expected."
    return 0
  fi

  export KOKORO_IMAGE="$image"
  if [[ "$runtime" == "docker-gpu" ]]; then
    export KOKORO_DOCKER_RUNTIME="${KOKORO_DOCKER_RUNTIME:-nvidia}"
  else
    export KOKORO_DOCKER_RUNTIME="${KOKORO_DOCKER_RUNTIME:-}"
  fi

  VOICE_PROFILE_ENABLED=1
  KOKORO_READINESS_URL="$(kokoro_readiness_url "$host" "$port")"
  add_compose_profile "voice"
}

determine_search_profile() {
  local internet_enabled
  local provider
  local autostart
  local host
  local port

  SEARCH_PROFILE_ENABLED=0

  internet_enabled="$(read_ini_value "retrieval" "internet_search_enabled" "false")"
  provider="$(read_ini_value "retrieval" "default_search_provider" "searxng" | tr '[:upper:]' '[:lower:]')"
  autostart="$(read_ini_value "retrieval.searxng" "autostart" "false")"

  if ! is_truthy "$internet_enabled" || [[ "$provider" != "searxng" ]] || ! is_truthy "$autostart"; then
    return 0
  fi

  host="$(read_ini_value "retrieval.searxng" "host" "${SEARXNG_HOST:-127.0.0.1}")"
  port="$(read_ini_value "retrieval.searxng" "port" "${SEARXNG_PORT:-8888}")"

  export SEARXNG_HOST="$host"
  export SEARXNG_PORT="$port"
  SEARCH_PROFILE_ENABLED=1
  add_compose_profile "search"
}

determine_compose_profiles() {
  COMPOSE_PROFILE_ARGS=()
  ACTIVE_PROFILE_NAMES=()

  load_stack_env_if_present || true
  determine_voice_profile
  determine_search_profile
}

kokoro_endpoint_ready() {
  local url="$1"

  command -v curl >/dev/null 2>&1 || return 1
  curl -fsS --max-time 2 "$url" >/dev/null 2>&1
}

wait_for_kokoro_ready() {
  local url="$1"
  local timeout_seconds="$2"
  local deadline

  deadline=$((SECONDS + timeout_seconds))
  while (( SECONDS < deadline )); do
    if kokoro_endpoint_ready "$url"; then
      return 0
    fi
    sleep 1
  done

  kokoro_endpoint_ready "$url"
}

check_kokoro_readiness_if_configured() {
  local wait_timeout_seconds=45

  if ! command -v curl >/dev/null 2>&1; then
    echo "⚠️  curl is unavailable; cannot check Kokoro readiness. Piper fallback expected."
    return 0
  fi

  if [[ "$KOKORO_EXTERNAL_ENABLED" -eq 1 ]]; then
    if kokoro_endpoint_ready "$KOKORO_READINESS_URL"; then
      echo "✅ Kokoro external runtime healthy at ${KOKORO_READINESS_URL}."
    else
      echo "⚠️  Kokoro runtime is external but ${KOKORO_READINESS_URL} is not ready."
      echo "⚠️  Orac will not manage an external Kokoro service. Piper fallback expected."
    fi
    return 0
  fi

  if [[ "$VOICE_PROFILE_ENABLED" -ne 1 ]]; then
    return 0
  fi

  if wait_for_kokoro_ready "$KOKORO_READINESS_URL" "$wait_timeout_seconds"; then
    echo "✅ Kokoro ready at ${KOKORO_READINESS_URL} (${KOKORO_RUNTIME_VALUE})."
    return 0
  fi

  echo "⚠️  Kokoro failed to become ready at ${KOKORO_READINESS_URL} within ${wait_timeout_seconds}s."
  echo "⚠️  Piper fallback expected."
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
docker_container_exists() {
  local container_name="$1"

  command -v docker >/dev/null 2>&1 || return 1
  docker ps -a --format '{{.Names}}' 2>/dev/null | grep -Fxq "$container_name"
}

docker_inspect_field() {
  local container_name="$1"
  local template="$2"

  docker inspect -f "$template" "$container_name" 2>/dev/null || true
}

print_container_compose_labels() {
  local container_name="$1"
  local project
  local service

  project="$(docker_inspect_field "$container_name" '{{ index .Config.Labels "com.docker.compose.project" }}')"
  service="$(docker_inspect_field "$container_name" '{{ index .Config.Labels "com.docker.compose.service" }}')"

  if [[ -z "$project" || "$project" == "<no value>" ]]; then
    echo "  Compose-managed: no"
    echo "  Warning: existing container is not labelled as Docker Compose-managed."
    return 0
  fi

  echo "  Compose-managed: yes"
  echo "  Compose project: $project"
  echo "  Compose service: ${service:-unknown}"
  if [[ "$project" != "${COMPOSE_PROJECT_NAME:-orac}" ]]; then
    echo "  Warning: project label differs from active COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-orac}."
  fi
}

print_container_metadata_comparison() {
  local container_name="${ORAC_DB_CONTAINER_NAME:-${CONTAINER_NAME:-orac-db}}"
  local expected_image="${ORAC_IMAGE_NAME:-orac}:${ORAC_IMAGE_TAG:-latest}"
  local expected_ports
  local expected_mount
  local actual_image
  local actual_ports
  local actual_mounts
  local actual_restart
  local actual_health
  local has_oracle_pwd

  echo
  echo "🔎 DB container compatibility check:"
  echo "  Container: $container_name"

  if ! command -v docker >/dev/null 2>&1; then
    echo "  Docker is not available; cannot inspect existing containers."
    return 0
  fi

  if ! docker ps -a --format '{{.Names}}' >/dev/null 2>&1; then
    echo "  Docker is not accessible; cannot inspect existing containers."
    return 0
  fi

  if ! docker_container_exists "$container_name"; then
    echo "  Existing container: not found"
    echo "  Compose will create it on first start if the image and data directory are available."
    return 0
  fi

  actual_image="$(docker_inspect_field "$container_name" '{{.Config.Image}}')"
  actual_ports="$(docker_inspect_field "$container_name" '{{json .HostConfig.PortBindings}}')"
  actual_mounts="$(docker_inspect_field "$container_name" '{{json .Mounts}}')"
  actual_restart="$(docker_inspect_field "$container_name" '{{.HostConfig.RestartPolicy.Name}}')"
  actual_health="$(docker_inspect_field "$container_name" '{{json .Config.Healthcheck}}')"
  has_oracle_pwd="$(docker_inspect_field "$container_name" '{{range .Config.Env}}{{println .}}{{end}}' | grep -c '^ORACLE_PWD=' || true)"

  expected_ports="1521->${PORT_SQLNET:-1521}, 8080->${PORT_HTTP:-8042}, 5500->${PORT_EM:-5500}"
  expected_mount="${ORADATA_DIR:-/u01/orac-db/oradata}:/opt/oracle/oradata"

  echo "  Expected image : $expected_image"
  echo "  Actual image   : ${actual_image:-unknown}"
  [[ "$actual_image" == "$expected_image" ]] || echo "  Difference     : image differs"
  echo "  Expected ports : $expected_ports"
  echo "  Actual ports   : ${actual_ports:-unknown}"
  echo "  Expected mount : $expected_mount"
  echo "  Actual mounts  : ${actual_mounts:-unknown}"
  echo "  Expected env   : ORACLE_PWD=<from credential store>"
  if [[ "$has_oracle_pwd" -gt 0 ]]; then
    echo "  Actual env     : ORACLE_PWD=<present, masked>"
  else
    echo "  Actual env     : ORACLE_PWD=<not present>"
  fi
  echo "  Expected restart policy: unless-stopped"
  echo "  Actual restart policy  : ${actual_restart:-unknown}"
  [[ "$actual_restart" == "unless-stopped" ]] || echo "  Difference             : restart policy differs"
  echo "  Expected health check  : none in Compose; readiness remains bin/dbwait.sh"
  echo "  Actual health check    : ${actual_health:-unknown}"

  print_container_compose_labels "$container_name"
}

compose_check_orac_stack() {
  local all_profiles=(--profile voice --profile search)
  local config_status=0

  echo "📁 Active stack directory : $ORAC_STACK_DIR"
  echo "📄 Compose file           : $ORAC_COMPOSE_FILE"
  echo "📄 Env file               : $ORAC_ENV_FILE"
  echo

  if ! require_compose_inputs; then
    return 1
  fi

  load_stack_env
  determine_compose_profiles

  echo "🧩 Profiles from Orac config: $(compose_profiles_text)"
  echo "🔧 Compose command preview : $(compose_command_preview "${COMPOSE_PROFILE_ARGS[@]}" up -d)"
  echo
  echo "🧪 Validating docker compose config..."
  if compose_cmd "${all_profiles[@]}" config >/dev/null; then
    echo "✅ docker compose config is valid."
  else
    config_status=$?
    echo "❌ docker compose config failed."
  fi

  print_container_metadata_comparison

  if [[ "$KOKORO_EXTERNAL_ENABLED" -eq 1 ]]; then
    echo
    echo "🔎 Kokoro external runtime:"
    echo "  Runtime: external"
    echo "  Readiness URL: $KOKORO_READINESS_URL"
    echo "  Compose profile: not activated"
  elif [[ "$KOKORO_RUNTIME_VALUE" == "docker-gpu" ]]; then
    echo
    echo "⚠️  Kokoro docker-gpu uses Compose runtime '${KOKORO_DOCKER_RUNTIME:-nvidia}'."
    echo "   Confirm the Docker host has NVIDIA Container Toolkit/runtime support."
  fi

  echo
  echo "Migration note:"
  echo "  This check is non-destructive. It does not remove, recreate, or modify containers or volumes."
  echo "  If an existing '${ORAC_DB_CONTAINER_NAME:-orac-db}' container is not Compose-managed,"
  echo "  stop it only after reviewing the differences above, then start through '$PROG start'."

  return "$config_status"
}

start_orac_stack() {
  echo "🚀 Starting Orac stack (Oracle DB + ORDS + AI)..."
  ensure_compose_runtime_env
  determine_compose_profiles

  echo "📁 Stack directory : $ORAC_STACK_DIR"
  echo "📄 Compose file    : $ORAC_COMPOSE_FILE"
  echo "📄 Env file        : $ORAC_ENV_FILE"
  echo "🧩 Profiles        : $(compose_profiles_text)"
  compose_cmd "${COMPOSE_PROFILE_ARGS[@]}" up -d --no-recreate

  "$SCRIPT_DIR/dbwait.sh"
  check_kokoro_readiness_if_configured
  echo "🤖 Starting Orac AI engine..."
  "$ORAC_SH" start
}

stop_orac_stack() {
  local all_profiles=(--profile voice --profile search)

  echo "🛑 Stopping Orac AI engine..."
  "$ORAC_SH" stop || true

  echo "🛑 Stopping Orac Compose services..."
  require_compose_inputs || return 1
  load_stack_env
  compose_cmd "${all_profiles[@]}" stop
}

status_orac_stack() {
  local all_profiles=(--profile voice --profile search)

  echo "📋 Orac Compose service status:"
  require_compose_inputs || return 1
  load_stack_env
  compose_cmd "${all_profiles[@]}" ps
  echo
  echo "🤖 Orac AI engine status:"
  "$ORAC_SH" status
}

logs_orac_stack() {
  local all_profiles=(--profile voice --profile search)

  require_compose_inputs || return 1
  load_stack_env

  case "${1:-}" in
    ai|orac)
      "$ORAC_SH" logs
      ;;
    db|ords|"")
      echo "📜 Tailing DB/ORDS container logs..."
      compose_cmd "${all_profiles[@]}" logs -f orac-db
      ;;
    voice|kokoro)
      echo "📜 Tailing Kokoro container logs..."
      compose_cmd "${all_profiles[@]}" logs -f orac-kokoro
      ;;
    search|searxng)
      echo "📜 Tailing SearXNG container logs..."
      compose_cmd "${all_profiles[@]}" logs -f orac-searxng
      ;;
    *)
      echo "Usage: $PROG logs {ai|db|voice|search}"
      exit 1
      ;;
  esac
}

display_orac_stack() {
  if [[ ! -x "$ORAC_DISPLAY_SH" ]]; then
    echo "❌ Missing or non-executable: $ORAC_DISPLAY_SH"
    echo "   Ensure it exists and run:  chmod +x \"$ORAC_DISPLAY_SH\""
    exit 1
  fi

  "$ORAC_DISPLAY_SH" "$@"
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
  echo "Usage: $0 {start|stop|restart|status|compose-check|logs [ai|db|voice|search]|display [start|stop|status|restart|run]|dump-context|clean [--dry-run|-n]|purge [--dry-run|-n] [--force|-f]}"
  echo
  echo "Stack files:"
  echo "  ORAC_STACK_DIR defaults to ${DEFAULT_STACK_DIR}."
  echo "  ORAC_COMPOSE_FILE defaults to \$ORAC_STACK_DIR/docker-compose.yaml."
  echo "  ORAC_ENV_FILE defaults to ${CONFIG_DIR}/orac.env."
  echo
  echo "Commands:"
  echo "  start"
  echo "    Start the required Compose services, wait for the DB to be ready,"
  echo "    then start the Orac AI engine process."
  echo
  echo "  stop"
  echo "    Stop the Orac AI engine process, then stop the Compose services."
  echo
  echo "  restart"
  echo "    Stop and then start the full Orac stack."
  echo
  echo "  status"
  echo "    Show Compose service status and process status for the"
  echo "    Orac AI engine."
  echo
  echo "  compose-check"
  echo "    Validate the active Compose stack and compare any existing DB container"
  echo "    with the Compose definition without changing Docker state."
  echo
  echo "  logs [ai|db|voice|search]"
  echo "    Tail logs for one part of the stack."
  echo "    ai   - follow the Orac AI engine log."
  echo "    db   - follow the Oracle DB/ORDS container log."
  echo "    voice  - follow the Kokoro sidecar log."
  echo "    search - follow the SearXNG sidecar log."
  echo "    If omitted, defaults to db."
  echo
  echo "  display [start|stop|status|restart|run]"
  echo "    Manage the optional Orac atom display companion process."
  echo "    It is not started automatically with the backend stack."
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
if [[ "${ORAC_CTL_LIB_ONLY:-0}" == "1" ]]; then
  return 0 2>/dev/null || exit 0
fi

case "${1:-}" in
  start)   start_orac_stack ;;
  stop)    stop_orac_stack ;;
  restart) echo "🔄 Restarting Orac stack..."; stop_orac_stack; start_orac_stack ;;
  status)  status_orac_stack ;;
  compose-check) compose_check_orac_stack ;;
  logs)    shift || true; logs_orac_stack "${1:-}" ;;
  display) shift || true; display_orac_stack "$@" ;;
  dump-context) dump_context_orac_stack ;;
  clean)   clean_orac_runtime "$@" ;;
  purge)   purge_orac_runtime "$@" ;;
  *)       print_usage ;;
esac
