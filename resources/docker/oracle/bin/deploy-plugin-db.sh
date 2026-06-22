#!/usr/bin/env bash
# Author: Clive Bostock
# Date: 2026-06-03
# Description: Deploy a plugin-owned database payload archive inside Oracle.

set -euo pipefail

PROG="Orac: deploy-plugin-db.sh"
ORAC_HOME="${ORAC_HOME:-/home/oracle/orac}"
ORACLE_PDB="${ORACLE_PDB:-FREEPDB1}"
PLUGIN_STAGING_ROOT="${PLUGIN_STAGING_ROOT:-${ORAC_HOME}/plugin_staging}"
CORE_DEPLOY_SCRIPT="${CORE_DEPLOY_SCRIPT:-/opt/oracle/scripts/setup/035-orac-schema_and_apps.sh}"

PLUGIN_ID=""
ARCHIVE=""
DRY_RUN=0

timestamp() {
  date +"%Y-%m-%d %H:%M:%S"
}

log() {
  printf '[%s] %s %s\n' "$(timestamp)" "${PROG}" "$*"
}

fail() {
  log "ERROR: $*"
  exit 1
}

usage() {
  cat <<EOF
Usage: deploy-plugin-db.sh --plugin-id PLUGIN_ID --archive ARCHIVE [--dry-run]

Deploy a plugin-owned database payload archive. The archive must contain:
  manifest.json
  plugin.json
  db/schema/**
EOF
}

validate_identifier() {
  local value="$1"
  local label="$2"

  [[ "${value}" =~ ^[A-Za-z][A-Za-z0-9_]*$ ]] || fail "Invalid ${label}: ${value}"
}

validate_version() {
  local value="$1"

  [[ "${value}" =~ ^[A-Za-z0-9_.-]+$ ]] || fail "Invalid plugin version: ${value}"
}

validate_checksum() {
  local value="$1"

  [[ "${value}" =~ ^[a-fA-F0-9]{64}$ ]] || fail "Invalid payload checksum: ${value}"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --plugin-id)
        [[ $# -ge 2 ]] || fail "--plugin-id requires a value"
        PLUGIN_ID="$2"
        shift 2
        ;;
      --archive)
        [[ $# -ge 2 ]] || fail "--archive requires a value"
        ARCHIVE="$2"
        shift 2
        ;;
      --dry-run)
        DRY_RUN=1
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        fail "Unknown option: $1"
        ;;
    esac
  done

  [[ -n "${PLUGIN_ID}" ]] || fail "--plugin-id is required"
  [[ -n "${ARCHIVE}" ]] || fail "--archive is required"
  validate_identifier "${PLUGIN_ID}" "plugin id"
  [[ -f "${ARCHIVE}" ]] || fail "Archive does not exist: ${ARCHIVE}"
}

manifest_value() {
  local manifest_path="$1"
  local key="$2"

  python3 - "$manifest_path" "$key" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
value = data
for part in sys.argv[2].split("."):
    value = value[part]
print(value)
PY
}

record_deployment_status() {
  local status="$1"
  local schema_name="$2"
  local plugin_version="$3"
  local checksum="$4"
  local error_message="${5:-}"
  local log_path="${6:-}"

  sqlplus -L -s / as sysdba <<SQL >/dev/null || log "WARNING: deployment state record failed for ${PLUGIN_ID}/${schema_name}/${status}"
whenever sqlerror exit failure rollback
alter session set container=${ORACLE_PDB};
declare
  l_row_version number;
begin
  orac_code.plugin_db_deployment_api.record_status(
    p_plugin_id           => '${PLUGIN_ID}',
    p_plugin_version      => '${plugin_version}',
    p_schema_name         => '${schema_name}',
    p_deployment_checksum => '${checksum}',
    p_deployment_status   => '${status}',
    p_error_message       => q'[${error_message}]',
    p_log_path            => q'[${log_path}]',
    p_row_version         => l_row_version
  );
end;
/
exit
SQL
}

invalid_schema_objects() {
  local schema_name="$1"

  sqlplus -L -s / as sysdba <<SQL
whenever sqlerror exit failure rollback
set heading off feedback off pagesize 0 verify off echo off trimspool on
alter session set container=${ORACLE_PDB};
select 'INVALID_OBJECT ' || object_type || ' ' || owner || '.' || object_name
  from dba_objects
 where owner = upper('${schema_name}')
   and status <> 'VALID'
 order by object_type, object_name;
exit
SQL
}

main() {
  parse_args "$@"

  local plugin_root
  local work_dir
  local manifest_path
  local plugin_version
  local payload_checksum
  local schema_count
  local schema_index
  local schema_name
  local log_root

  plugin_root="$(dirname "${ARCHIVE}")"
  work_dir="${plugin_root}/work"
  rm -rf "${work_dir}"
  mkdir -p "${work_dir}"

  log "Unpacking ${ARCHIVE} into ${work_dir}"
  tar -xzf "${ARCHIVE}" -C "${work_dir}"

  manifest_path="${work_dir}/manifest.json"
  [[ -f "${manifest_path}" ]] || fail "manifest.json is missing from archive"
  [[ -f "${work_dir}/plugin.json" ]] || fail "plugin.json is missing from archive"
  [[ -d "${work_dir}/db/schema" ]] || fail "db/schema is missing from archive"

  plugin_version="$(manifest_value "${manifest_path}" "plugin_version")"
  payload_checksum="$(manifest_value "${manifest_path}" "payload_checksum")"
  validate_version "${plugin_version}"
  validate_checksum "${payload_checksum}"
  schema_count="$(python3 - "${manifest_path}" <<'PY'
import json
import sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(len((data.get("database") or {}).get("schemas") or []))
PY
)"
  [[ "${schema_count}" =~ ^[0-9]+$ ]] || fail "Unable to read database schema count"
  (( schema_count > 0 )) || fail "Archive manifest database.schemas is empty"

  if [[ "${DRY_RUN}" == "1" ]]; then
    log "Dry run complete for ${PLUGIN_ID}; archive shape is valid."
    exit 0
  fi

  for ((schema_index = 0; schema_index < schema_count; schema_index++)); do
    schema_name="$(python3 - "${manifest_path}" "${schema_index}" <<'PY'
import json
import sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(data["database"]["schemas"][int(sys.argv[2])]["schema_name"])
PY
)"
    validate_identifier "${schema_name}" "schema name"
    record_deployment_status "started" "${schema_name}" "${plugin_version}" "${payload_checksum}" "" ""
  done

  [[ -x "${CORE_DEPLOY_SCRIPT}" ]] || fail "Core schema deploy script is missing or not executable: ${CORE_DEPLOY_SCRIPT}"
  log_root="${work_dir}/db/_logs"

  if BASE_DIR="${work_dir}/db" LOG_ROOT="${log_root}" STOP_ON_ERROR=1 "${CORE_DEPLOY_SCRIPT}"; then
    local invalid_objects

    for ((schema_index = 0; schema_index < schema_count; schema_index++)); do
      schema_name="$(python3 - "${manifest_path}" "${schema_index}" <<'PY'
import json
import sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(data["database"]["schemas"][int(sys.argv[2])]["schema_name"])
PY
)"
      invalid_objects="$(
        invalid_schema_objects "${schema_name}" \
          | sed -n 's/^[[:space:]]*INVALID_OBJECT[[:space:]]\{1,\}//p'
      )"
      if [[ -n "${invalid_objects}" ]]; then
        record_deployment_status "failed" "${schema_name}" "${plugin_version}" "${payload_checksum}" "Deployment left invalid objects: ${invalid_objects}" "${log_root}"
        fail "Plugin database deployment left invalid objects in ${schema_name}: ${invalid_objects}"
      fi
      record_deployment_status "succeeded" "${schema_name}" "${plugin_version}" "${payload_checksum}" "" "${log_root}"
    done
    log "Plugin database deployment completed for ${PLUGIN_ID}."
    exit 0
  else
    local rc=$?
    for ((schema_index = 0; schema_index < schema_count; schema_index++)); do
      schema_name="$(python3 - "${manifest_path}" "${schema_index}" <<'PY'
import json
import sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(data["database"]["schemas"][int(sys.argv[2])]["schema_name"])
PY
)"
      record_deployment_status "failed" "${schema_name}" "${plugin_version}" "${payload_checksum}" "Deployment script failed with exit ${rc}" "${log_root}"
    done
    fail "Plugin database deployment failed for ${PLUGIN_ID} with exit ${rc}"
  fi
}

main "$@"
