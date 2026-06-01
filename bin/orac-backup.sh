#!/usr/bin/env bash
################################################################################
#
# Author: Clive Bostock
# Date: 20-May-2026
# Purpose: Create an Orac backup archive containing database Data Pump export,
#          host configuration, plugin/schema metadata, and enabled FK metadata.
# Usage: bin/orac-backup.sh [--skip-db] [--include-vaults|--export-vaults] TARGET_DIR
# Example: bin/orac-backup.sh /backups/orac
#
################################################################################

set -Eeuo pipefail

PROG=$(basename "$0")
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ORAC_PROJECT_HOME=$(dirname "$SCRIPT_DIR")
CONFIG_DIR="${ORAC_PROJECT_HOME}/resources/config"
ENV_FILE="${CONFIG_DIR}/orac.env"
PLUGINS_DIR="${ORAC_PROJECT_HOME}/plugins"
VAULT_EXPORT_HELPER="${ORAC_PROJECT_HOME}/src/controller/orac_vault_export.py"

DOCKER_BIN=${ORAC_DOCKER_BIN:-docker}
TAR_BIN=${ORAC_TAR_BIN:-tar}
PYTHON_BIN=${ORAC_PYTHON_BIN:-}
SKIP_DB=0
DRY_RUN=0
TARGET_DIR=""
VAULT_MODE="none"
VAULT_EXPORT_PASSPHRASE=""
VAULT_ALLOW_LIST=("dsn_credentials.ini" "api_keys.ini")

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck source=/dev/null
  source "$ENV_FILE"
fi

CONTAINER_NAME=${CONTAINER_NAME:-orac-db}
ORACLE_PDB=${ORACLE_PDB:-FREEPDB1}
ORAC_DATAPUMP_DIR=${ORAC_DATAPUMP_DIR:-ORAC_DATAPUMP_DIR}
ORAC_DATAPUMP_PATH=${ORAC_DATAPUMP_PATH:-/home/oracle/orac/datapump}
ORAC_VAULT_DIR=${ORAC_VAULT_DIR:-${HOME}/.Orac}
ORAC_VAULT_DIR=${ORAC_VAULT_DIR/#\~/$HOME}

usage() {
  cat <<EOF
Usage: $PROG [options] TARGET_DIR

Create an Orac backup archive in TARGET_DIR.

Options:
  --skip-db          Skip Data Pump export and archive only metadata/config.
  --include-vaults   Include allow-listed machine-bound encrypted vault files.
  --export-vaults    Export allow-listed vaults using a recovery passphrase.
  --container NAME   Oracle database container name. Default: ${CONTAINER_NAME}
  --pdb NAME         Oracle PDB service/container name. Default: ${ORACLE_PDB}
  --dry-run          Show the planned backup inputs without creating an archive.
  -h, --help         Show this help.
EOF
}

log() {
  printf '%s\n' "$*"
}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

find_python() {
  if [[ -n "$PYTHON_BIN" ]]; then
    printf '%s\n' "$PYTHON_BIN"
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi

  command -v python >/dev/null 2>&1 || fail "python3 or python is required"
  command -v python
}

validate_identifier() {
  local value="$1"
  local label="$2"

  [[ "$value" =~ ^[A-Za-z][A-Za-z0-9_]*$ ]] || fail "Invalid ${label}: ${value}"
}

validate_container_name() {
  local value="$1"

  [[ "$value" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]] || fail "Invalid container name: ${value}"
}

validate_datapump_path() {
  [[ "$ORAC_DATAPUMP_PATH" == /* ]] || fail "ORAC_DATAPUMP_PATH must be absolute"
  [[ "$ORAC_DATAPUMP_PATH" != *"'"* ]] || fail "ORAC_DATAPUMP_PATH must not contain single quotes"
}

vault_source_display() {
  if [[ "$ORAC_VAULT_DIR" == "${HOME}/.Orac" || "$ORAC_VAULT_DIR" == "~/.Orac" ]]; then
    printf '%s\n' "~/.Orac"
  else
    printf '%s\n' "$ORAC_VAULT_DIR"
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --skip-db)
        SKIP_DB=1
        shift
        ;;
      --include-vaults)
        [[ "$VAULT_MODE" == "none" ]] || fail "--include-vaults and --export-vaults are mutually exclusive"
        VAULT_MODE="machine_bound"
        shift
        ;;
      --export-vaults)
        [[ "$VAULT_MODE" == "none" ]] || fail "--include-vaults and --export-vaults are mutually exclusive"
        VAULT_MODE="portable"
        shift
        ;;
      --container)
        [[ $# -ge 2 ]] || fail "--container requires a value"
        CONTAINER_NAME="$2"
        shift 2
        ;;
      --pdb)
        [[ $# -ge 2 ]] || fail "--pdb requires a value"
        ORACLE_PDB="$2"
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
      -*)
        fail "Unknown option: $1"
        ;;
      *)
        [[ -z "$TARGET_DIR" ]] || fail "Only one TARGET_DIR may be supplied"
        TARGET_DIR="$1"
        shift
        ;;
    esac
  done

  [[ -n "$TARGET_DIR" ]] || fail "TARGET_DIR is required"
}

discover_manifest_data() {
  local python="$1"
  local metadata_path="$2"
  local schemas_path="$3"

  "$python" - "$ORAC_PROJECT_HOME" "$PLUGINS_DIR" "$metadata_path" "$schemas_path" <<'PY'
import json
import re
import sys
import tomllib
from pathlib import Path

project_home = Path(sys.argv[1])
plugins_dir = Path(sys.argv[2])
metadata_path = Path(sys.argv[3])
schemas_path = Path(sys.argv[4])

schemas = ["orac_core", "orac_api", "orac_code"]
plugins = []
schema_name_pattern = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

for manifest_path in sorted(plugins_dir.glob("*.json")):
    with manifest_path.open("rb") as handle:
        manifest = json.load(handle)

    database = manifest.get("database") or {}
    database_schemas = []
    for schema in database.get("schemas") or []:
        schema_name = str(schema.get("schema_name", "")).strip()
        if schema_name:
            if not schema_name_pattern.fullmatch(schema_name):
                raise ValueError(f"Invalid database schema name in {manifest_path}: {schema_name}")
            database_schemas.append(schema_name.lower())
            backup = schema.get("backup") or {}
            if backup.get("include", True):
                schemas.append(schema_name.lower())

    plugins.append(
        {
            "plugin_id": manifest.get("plugin_id"),
            "name": manifest.get("name"),
            "version": manifest.get("version"),
            "enabled": bool(manifest.get("enabled", False)),
            "manifest_path": str(manifest_path.relative_to(project_home)),
            "database_schemas": database_schemas,
        }
    )

unique_schemas = list(dict.fromkeys(schemas))

metadata_path.write_text(json.dumps(plugins, indent=2, sort_keys=True) + "\n", encoding="utf-8")
schemas_path.write_text("\n".join(unique_schemas) + "\n", encoding="utf-8")
PY
}

read_version() {
  local python="$1"

  "$python" - "$ORAC_PROJECT_HOME" <<'PY'
import re
import sys
import tomllib
from pathlib import Path

project_home = Path(sys.argv[1])
pyproject = project_home / "pyproject.toml"
if pyproject.exists():
    with pyproject.open("rb") as handle:
        data = tomllib.load(handle)
    version = (data.get("project") or {}).get("version")
    if version:
        print(version)
        raise SystemExit

init_path = project_home / "src" / "model" / "__init__.py"
if init_path.exists():
    match = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", init_path.read_text(encoding="utf-8"))
    if match:
        print(match.group(1))
        raise SystemExit

print("unknown")
PY
}

uppercase_csv_from_file() {
  local file_path="$1"
  awk 'NF { print toupper($0) }' "$file_path" | paste -sd, -
}

ensure_datapump_directory() {
  validate_identifier "$ORACLE_PDB" "ORACLE_PDB"
  validate_identifier "$ORAC_DATAPUMP_DIR" "ORAC_DATAPUMP_DIR"

  log "Preparing Data Pump directory ${ORAC_DATAPUMP_DIR} in ${CONTAINER_NAME}"
  "$DOCKER_BIN" exec -u 0 "$CONTAINER_NAME" bash -lc "mkdir -p '${ORAC_DATAPUMP_PATH}' && chown 54321:54321 '${ORAC_DATAPUMP_PATH}' && chmod 750 '${ORAC_DATAPUMP_PATH}'"
  "$DOCKER_BIN" exec -i "$CONTAINER_NAME" sqlplus -L -s / as sysdba <<SQL
whenever sqlerror exit sql.sqlcode
alter session set container=${ORACLE_PDB};
create or replace directory ${ORAC_DATAPUMP_DIR} as '${ORAC_DATAPUMP_PATH}';
exit
SQL
}

query_existing_schemas() {
  local requested_csv="$1"
  local output_path="$2"

  "$DOCKER_BIN" exec -i "$CONTAINER_NAME" sqlplus -L -s / as sysdba >"$output_path" <<SQL
set heading off feedback off pagesize 0 verify off echo off trimspool on
whenever sqlerror exit sql.sqlcode
alter session set container=${ORACLE_PDB};
select lower(username)
  from dba_users
 where username in (${requested_csv})
 order by username;
exit
SQL
  sed -i '/^$/d; s/^[[:space:]]*//; s/[[:space:]]*$//' "$output_path"
}

sql_quoted_csv_from_schema_file() {
  local file_path="$1"

  awk 'NF { printf "%s'\''%s'\''", sep, toupper($0); sep=", " }' "$file_path"
}

write_missing_schemas() {
  local requested_path="$1"
  local existing_path="$2"
  local missing_path="$3"

  awk 'NF { print tolower($0) }' "$existing_path" | sort >"${existing_path}.sorted"
  awk 'NF { print tolower($0) }' "$requested_path" | sort >"${requested_path}.sorted"
  comm -23 "${requested_path}.sorted" "${existing_path}.sorted" >"$missing_path"
}

write_enabled_fk_metadata() {
  local exported_path="$1"
  local output_path="$2"
  local owner_list

  owner_list=$(sql_quoted_csv_from_schema_file "$exported_path")
  if [[ -z "$owner_list" ]]; then
    : >"$output_path"
    return 0
  fi

  "$DOCKER_BIN" exec -i "$CONTAINER_NAME" sqlplus -L -s / as sysdba >"$output_path" <<SQL
set heading off feedback off pagesize 0 verify off echo off trimspool on linesize 32767
whenever sqlerror exit sql.sqlcode
alter session set container=${ORACLE_PDB};
select '-- enabled foreign key: ' || owner || '.' || constraint_name ||
       ' on ' || table_name || chr(10) ||
       'alter table ' || owner || '.' || table_name ||
       ' enable constraint ' || constraint_name || ';'
  from dba_constraints
 where owner in (${owner_list})
   and constraint_type = 'R'
   and status = 'ENABLED'
 order by owner, table_name, constraint_name;
exit
SQL
}

run_datapump_export() {
  local exported_path="$1"
  local dump_file="$2"
  local log_file="$3"
  local schema_csv

  schema_csv=$(uppercase_csv_from_file "$exported_path")
  [[ -n "$schema_csv" ]] || fail "No existing schemas are available to export"

  log "Exporting schemas: ${schema_csv}"
  "$DOCKER_BIN" exec "$CONTAINER_NAME" bash -lc \
    "cd '${ORAC_DATAPUMP_PATH}' && expdp system/\"\${ORACLE_PWD}\"@//127.0.0.1:1521/${ORACLE_PDB} schemas=${schema_csv} directory=${ORAC_DATAPUMP_DIR} dumpfile=${dump_file} logfile=${log_file} reuse_dumpfiles=yes"
}

copy_datapump_files() {
  local dump_file="$1"
  local log_file="$2"
  local db_dir="$3"

  mkdir -p "$db_dir"
  "$DOCKER_BIN" cp "${CONTAINER_NAME}:${ORAC_DATAPUMP_PATH}/${dump_file}" "${db_dir}/${dump_file}"
  "$DOCKER_BIN" cp "${CONTAINER_NAME}:${ORAC_DATAPUMP_PATH}/${log_file}" "${db_dir}/${log_file}"
  "$DOCKER_BIN" exec "$CONTAINER_NAME" bash -lc "rm -f '${ORAC_DATAPUMP_PATH}/${dump_file}' '${ORAC_DATAPUMP_PATH}/${log_file}'" >/dev/null
}

copy_config_files() {
  local config_target="$1"

  mkdir -p "$config_target"
  shopt -s nullglob
  local config_file
  for config_file in "${CONFIG_DIR}"/*.ini; do
    cp "$config_file" "$config_target/"
  done
  shopt -u nullglob
}

discover_vault_files() {
  local output_path="$1"
  local vault_file

  : >"$output_path"
  for vault_file in "${VAULT_ALLOW_LIST[@]}"; do
    if [[ -f "${ORAC_VAULT_DIR}/${vault_file}" ]]; then
      printf '%s\n' "$vault_file" >>"$output_path"
    fi
  done
}

print_vault_dry_run_summary() {
  local vault_files_path="$1"

  log "Vault mode: ${VAULT_MODE}"
  log "Vault source directory: $(vault_source_display)"
  log "Existing allow-listed vault files:"
  if [[ -s "$vault_files_path" ]]; then
    sed 's/^/  - /' "$vault_files_path"
  else
    log "  - none"
  fi
}

copy_machine_bound_vaults() {
  local vault_files_path="$1"
  local target_dir="$2"
  local vault_file

  mkdir -p "$target_dir"
  while IFS= read -r vault_file; do
    [[ -n "$vault_file" ]] || continue
    cp "${ORAC_VAULT_DIR}/${vault_file}" "${target_dir}/${vault_file}"
    chmod 600 "${target_dir}/${vault_file}" 2>/dev/null || true
  done <"$vault_files_path"
}

read_vault_export_passphrase() {
  local passphrase_file="${ORAC_VAULT_EXPORT_PASSPHRASE_FILE:-}"
  local confirm_passphrase=""

  if [[ -n "${ORAC_VAULT_EXPORT_PASSPHRASE:-}" ]]; then
    fail "ORAC_VAULT_EXPORT_PASSPHRASE is not supported. Use ORAC_VAULT_EXPORT_PASSPHRASE_FILE or interactive input."
  fi

  if [[ -n "$passphrase_file" ]]; then
    [[ -f "$passphrase_file" ]] || fail "ORAC_VAULT_EXPORT_PASSPHRASE_FILE does not exist: ${passphrase_file}"
    [[ -r "$passphrase_file" ]] || fail "ORAC_VAULT_EXPORT_PASSPHRASE_FILE is not readable: ${passphrase_file}"
    VAULT_EXPORT_PASSPHRASE=$(sed -n '1p' "$passphrase_file")
    [[ -n "$VAULT_EXPORT_PASSPHRASE" ]] || fail "ORAC_VAULT_EXPORT_PASSPHRASE_FILE first line must not be empty"
    return 0
  fi

  printf 'Vault export passphrase: '
  read -r -s VAULT_EXPORT_PASSPHRASE
  printf '\n'
  printf 'Confirm vault export passphrase: '
  read -r -s confirm_passphrase
  printf '\n'

  [[ -n "$VAULT_EXPORT_PASSPHRASE" ]] || fail "Vault export passphrase must not be empty"
  [[ "$VAULT_EXPORT_PASSPHRASE" == "$confirm_passphrase" ]] || fail "Vault export passphrase confirmation does not match"
}

export_portable_vaults() {
  local vault_files_path="$1"
  local target_dir="$2"

  mkdir -p "$target_dir"
  [[ -f "$VAULT_EXPORT_HELPER" ]] || fail "Portable vault export is not yet implemented because no vault export API was found."

  if [[ -n "${ORAC_VAULT_EXPORT_PASSPHRASE_FILE:-}" ]]; then
    PYTHONPATH="${ORAC_PROJECT_HOME}/src:${ORAC_PROJECT_HOME}:${PYTHONPATH:-}" \
      "$PYTHON_BIN" "$VAULT_EXPORT_HELPER" \
      --vault-dir "$ORAC_VAULT_DIR" \
      --output-dir "$target_dir" \
      --files "${VAULT_ALLOW_LIST[@]}" \
      --passphrase-file "$ORAC_VAULT_EXPORT_PASSPHRASE_FILE"
  else
    printf '%s\n' "$VAULT_EXPORT_PASSPHRASE" | PYTHONPATH="${ORAC_PROJECT_HOME}/src:${ORAC_PROJECT_HOME}:${PYTHONPATH:-}" \
      "$PYTHON_BIN" "$VAULT_EXPORT_HELPER" \
      --vault-dir "$ORAC_VAULT_DIR" \
      --output-dir "$target_dir" \
      --files "${VAULT_ALLOW_LIST[@]}" \
      --passphrase-stdin
  fi

  [[ -f "${target_dir}/vault_export.json.enc" ]] || fail "Portable vault export did not produce vault_export.json.enc"
  [[ -f "${target_dir}/vault_export_manifest.json" ]] || fail "Portable vault export did not produce vault_export_manifest.json"
  : >"$vault_files_path"
  "$PYTHON_BIN" - "${target_dir}/vault_export_manifest.json" "$vault_files_path" <<'PY'
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
Path(sys.argv[2]).write_text(
    "\n".join(manifest.get("files", [])) + ("\n" if manifest.get("files") else ""),
    encoding="utf-8",
)
PY
}

write_backup_manifest() {
  local python="$1"
  local manifest_path="$2"

  ORAC_BACKUP_MANIFEST_PATH="$manifest_path" \
  ORAC_VERSION_VALUE="$ORAC_VERSION_VALUE" \
  ORAC_CONTAINER_NAME="$CONTAINER_NAME" \
  ORAC_PDB_NAME="$ORACLE_PDB" \
  ORAC_DATAPUMP_DIR_VALUE="$ORAC_DATAPUMP_DIR" \
  ORAC_DATAPUMP_PATH_VALUE="$ORAC_DATAPUMP_PATH" \
  ORAC_REQUESTED_SCHEMAS_PATH="$REQUESTED_SCHEMAS_PATH" \
  ORAC_EXPORTED_SCHEMAS_PATH="$EXPORTED_SCHEMAS_PATH" \
  ORAC_MISSING_SCHEMAS_PATH="$MISSING_SCHEMAS_PATH" \
  ORAC_PLUGIN_METADATA_PATH="$PLUGIN_METADATA_PATH" \
  ORAC_DUMP_FILE="$DUMP_FILE" \
  ORAC_LOG_FILE="$EXPORT_LOG_FILE" \
  ORAC_SKIP_DB="$SKIP_DB" \
  ORAC_VAULT_MODE="$VAULT_MODE" \
  ORAC_VAULT_SOURCE_DIR="$(vault_source_display)" \
  ORAC_VAULT_FILES_PATH="$VAULT_FILES_PATH" \
  "$python" <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

def read_lines(env_name):
    path = Path(os.environ[env_name])
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

plugin_metadata = json.loads(Path(os.environ["ORAC_PLUGIN_METADATA_PATH"]).read_text(encoding="utf-8"))
skip_db = os.environ["ORAC_SKIP_DB"] == "1"
vault_mode = os.environ["ORAC_VAULT_MODE"]
vault_files = [] if vault_mode == "none" else read_lines("ORAC_VAULT_FILES_PATH")
vaults = {
    "mode": vault_mode,
    "included": vault_mode != "none",
    "portable": vault_mode == "portable",
    "source_dir": os.environ["ORAC_VAULT_SOURCE_DIR"],
    "files": vault_files,
}
if vault_mode == "machine_bound":
    vaults["warning"] = (
        "Vault files are encrypted using the original machine's local key "
        "material and may not be decryptable on another host."
    )
elif vault_mode == "portable":
    vaults["warning"] = "Portable vault export requires the recovery passphrase during restore."
manifest = {
    "backup_format_version": 1,
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "orac_version": os.environ["ORAC_VERSION_VALUE"],
    "database": {
        "container_name": os.environ["ORAC_CONTAINER_NAME"],
        "pdb": os.environ["ORAC_PDB_NAME"],
        "datapump_directory": os.environ["ORAC_DATAPUMP_DIR_VALUE"],
        "datapump_path": os.environ["ORAC_DATAPUMP_PATH_VALUE"],
        "skip_db": skip_db,
        "dump_file": "" if skip_db else os.environ["ORAC_DUMP_FILE"],
        "log_file": "" if skip_db else os.environ["ORAC_LOG_FILE"],
        "requested_schemas": read_lines("ORAC_REQUESTED_SCHEMAS_PATH"),
        "exported_schemas": read_lines("ORAC_EXPORTED_SCHEMAS_PATH"),
        "missing_schemas": read_lines("ORAC_MISSING_SCHEMAS_PATH"),
    },
    "plugins": plugin_metadata,
    "vaults": vaults,
}
Path(os.environ["ORAC_BACKUP_MANIFEST_PATH"]).write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
}

create_archive() {
  local stage_parent="$1"
  local stage_name="$2"
  local archive_path="$3"

  mkdir -p "$(dirname "$archive_path")"
  "$TAR_BIN" -czf "$archive_path" -C "$stage_parent" "$stage_name"
}

parse_args "$@"
validate_container_name "$CONTAINER_NAME"
validate_identifier "$ORACLE_PDB" "ORACLE_PDB"
validate_identifier "$ORAC_DATAPUMP_DIR" "ORAC_DATAPUMP_DIR"
validate_datapump_path

PYTHON_BIN=$(find_python)
STAMP=$(date -u +"%Y%m%d-%H%M%S")
STAGE_PARENT=$(mktemp -d "${TMPDIR:-/tmp}/orac-backup.XXXXXX")
STAGE_DIR="${STAGE_PARENT}/orac-backup-${STAMP}"
ARCHIVE_PATH="${TARGET_DIR%/}/orac-backup-${STAMP}.tar.gz"
REQUESTED_SCHEMAS_PATH="${STAGE_DIR}/schema_list_requested.txt"
EXPORTED_SCHEMAS_PATH="${STAGE_DIR}/schema_list.txt"
MISSING_SCHEMAS_PATH="${STAGE_DIR}/schema_list_missing.txt"
PLUGIN_METADATA_PATH="${STAGE_DIR}/plugins.json"
VAULT_FILES_PATH="${STAGE_PARENT}/vault_files.txt"
DUMP_FILE="orac-${STAMP}.dmp"
EXPORT_LOG_FILE="orac-${STAMP}.log"
ORAC_VERSION_VALUE=$(read_version "$PYTHON_BIN")

cleanup() {
  rm -rf "$STAGE_PARENT"
}
trap cleanup EXIT

mkdir -p "$STAGE_DIR"
discover_manifest_data "$PYTHON_BIN" "$PLUGIN_METADATA_PATH" "$REQUESTED_SCHEMAS_PATH"
discover_vault_files "$VAULT_FILES_PATH"
: >"$EXPORTED_SCHEMAS_PATH"
: >"$MISSING_SCHEMAS_PATH"

log "Orac version: ${ORAC_VERSION_VALUE}"
log "Requested schemas:"
sed 's/^/  - /' "$REQUESTED_SCHEMAS_PATH"
print_vault_dry_run_summary "$VAULT_FILES_PATH"

if [[ "$DRY_RUN" -eq 1 ]]; then
  log "Dry run only. No backup archive created."
  exit 0
fi

copy_config_files "${STAGE_DIR}/config"

case "$VAULT_MODE" in
  none)
    ;;
  machine_bound)
    copy_machine_bound_vaults "$VAULT_FILES_PATH" "${STAGE_DIR}/vaults/machine_bound"
    ;;
  portable)
    read_vault_export_passphrase
    export_portable_vaults "$VAULT_FILES_PATH" "${STAGE_DIR}/vaults/portable"
    ;;
esac

if [[ "$SKIP_DB" -eq 1 ]]; then
  log "Skipping database export because --skip-db was supplied."
else
  REQUESTED_SQL_LIST=$(sql_quoted_csv_from_schema_file "$REQUESTED_SCHEMAS_PATH")
  ensure_datapump_directory
  query_existing_schemas "$REQUESTED_SQL_LIST" "$EXPORTED_SCHEMAS_PATH"
  write_missing_schemas "$REQUESTED_SCHEMAS_PATH" "$EXPORTED_SCHEMAS_PATH" "$MISSING_SCHEMAS_PATH"

  if [[ -s "$MISSING_SCHEMAS_PATH" ]]; then
    log "WARNING: requested schemas missing from database:"
    sed 's/^/  - /' "$MISSING_SCHEMAS_PATH"
  fi

  write_enabled_fk_metadata "$EXPORTED_SCHEMAS_PATH" "${STAGE_DIR}/foreign_keys_enabled.sql"
  run_datapump_export "$EXPORTED_SCHEMAS_PATH" "$DUMP_FILE" "$EXPORT_LOG_FILE"
  copy_datapump_files "$DUMP_FILE" "$EXPORT_LOG_FILE" "${STAGE_DIR}/db"
fi

write_backup_manifest "$PYTHON_BIN" "${STAGE_DIR}/backup_manifest.json"
create_archive "$STAGE_PARENT" "$(basename "$STAGE_DIR")" "$ARCHIVE_PATH"
log "Backup archive created: ${ARCHIVE_PATH}"
