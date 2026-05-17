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
CONFIG_FILE="${CONFIG_DIR}/orac.ini"
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
ORAC_DISPLAY_SH="${SCRIPT_DIR}/orac-display.sh"
KOKORO_CPU_IMAGE="ghcr.io/remsky/kokoro-fastapi-cpu:latest"
KOKORO_GPU_IMAGE="ghcr.io/remsky/kokoro-fastapi-gpu:latest"

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

ensure_kokoro_sidecar() {
  local tts_engine
  local autostart
  local runtime
  local container_name
  local image
  local image_override
  local host
  local port
  local base_url
  local readiness_url
  local wait_timeout_seconds=45
  local container_state=""

  tts_engine="$(read_ini_value "voice" "tts_engine" "piper" | tr '[:upper:]' '[:lower:]')"
  autostart="$(read_ini_value "voice" "tts_kokoro_autostart" "false")"
  runtime="$(read_ini_value "voice" "tts_kokoro_runtime" "docker-cpu" | tr '[:upper:]' '[:lower:]')"

  if [[ "$tts_engine" != "kokoro" ]] || ! is_truthy "$autostart"; then
    echo "ℹ️  Kokoro autostart disabled (tts_engine=${tts_engine}, tts_kokoro_autostart=${autostart})."
    return 0
  fi

  container_name="$(read_ini_value "voice" "tts_kokoro_container_name" "orac-kokoro")"
  image_override="$(read_ini_value "voice" "tts_kokoro_image" "")"
  host="$(read_ini_value "voice" "tts_kokoro_host" "127.0.0.1")"
  port="$(read_ini_value "voice" "tts_kokoro_port" "8880")"
  base_url="$(read_ini_value "voice" "tts_kokoro_base_url" "http://127.0.0.1:8880/v1")"
  readiness_url="$(kokoro_readiness_url "$host" "$port")"

  if ! command -v curl >/dev/null 2>&1; then
    echo "⚠️  curl is unavailable; cannot check Kokoro readiness. Piper fallback expected."
    return 0
  fi

  if [[ "$runtime" == "external" ]]; then
    readiness_url="$(kokoro_readiness_url_from_base_url "$base_url")"
    if kokoro_endpoint_ready "$readiness_url"; then
      echo "✅ Kokoro external runtime already healthy at ${readiness_url}."
    else
      echo "⚠️  Kokoro runtime is external but ${readiness_url} is not ready."
      echo "⚠️  Orac will not manage an external Kokoro service. Piper fallback expected."
    fi
    return 0
  fi

  if [[ "$runtime" != "docker-cpu" && "$runtime" != "docker-gpu" ]]; then
    echo "⚠️  Unsupported tts_kokoro_runtime='${runtime}'. Supported values: docker-cpu, docker-gpu, external."
    echo "⚠️  Kokoro will not be autostarted. Piper fallback expected."
    return 0
  fi

  if ! image="$(kokoro_image_for_runtime "$runtime" "$image_override")"; then
    echo "⚠️  Unable to resolve Kokoro image for runtime '${runtime}'. Piper fallback expected."
    return 0
  fi

  if kokoro_endpoint_ready "$readiness_url"; then
    echo "✅ Kokoro already healthy at ${readiness_url} (${runtime})."
    return 0
  fi

  if ! command -v docker >/dev/null 2>&1; then
    echo "⚠️  Docker is unavailable; cannot autostart Kokoro. Piper fallback expected."
    return 0
  fi

  if docker ps -a --format '{{.Names}}' | grep -Fxq "$container_name"; then
    container_state="$(docker inspect -f '{{.State.Status}}' "$container_name" 2>/dev/null || true)"
    if [[ "$container_state" == "running" ]]; then
      echo "⚠️  Kokoro container '${container_name}' is running but ${readiness_url} is not ready."
      echo "⚠️  Kokoro failed to become ready. Piper fallback expected."
      return 0
    fi

    echo "▶️  Starting Kokoro container '${container_name}'..."
    if docker start "$container_name" >/dev/null; then
      echo "✅ Kokoro container started."
    else
      echo "⚠️  Failed to start Kokoro container '${container_name}'. Piper fallback expected."
      return 0
    fi
  else
    echo "▶️  Creating Kokoro container '${container_name}' from ${image} (${runtime})..."
    if [[ "$runtime" == "docker-gpu" ]]; then
      if docker run -d \
        --gpus all \
        --name "$container_name" \
        -p "${host}:${port}:8880" \
        "$image" >/dev/null; then
        echo "✅ Kokoro container created."
      else
        echo "⚠️  Failed to create Kokoro GPU container '${container_name}'. Piper fallback expected."
        return 0
      fi
    elif docker run -d \
      --name "$container_name" \
      -p "${host}:${port}:8880" \
      "$image" >/dev/null; then
      echo "✅ Kokoro container created."
    else
      echo "⚠️  Failed to create Kokoro container '${container_name}'. Piper fallback expected."
      return 0
    fi
  fi

  if wait_for_kokoro_ready "$readiness_url" "$wait_timeout_seconds"; then
    echo "✅ Kokoro ready at ${readiness_url}."
  else
    echo "⚠️  Kokoro failed to become ready at ${readiness_url} within ${wait_timeout_seconds}s."
    echo "⚠️  Piper fallback expected."
  fi
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
  ensure_kokoro_sidecar
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
  echo "Usage: $0 {start|stop|restart|status|logs [ai|db]|display [start|stop|status|restart|run]|dump-context|clean [--dry-run|-n]|purge [--dry-run|-n] [--force|-f]}"
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
case "${1:-}" in
  start)   start_orac_stack ;;
  stop)    stop_orac_stack ;;
  restart) echo "🔄 Restarting Orac stack..."; stop_orac_stack; start_orac_stack ;;
  status)  status_orac_stack ;;
  logs)    shift || true; logs_orac_stack "${1:-}" ;;
  display) shift || true; display_orac_stack "$@" ;;
  dump-context) dump_context_orac_stack ;;
  clean)   clean_orac_runtime "$@" ;;
  purge)   purge_orac_runtime "$@" ;;
  *)       print_usage ;;
esac
