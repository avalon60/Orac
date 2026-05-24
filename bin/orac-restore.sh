#!/usr/bin/env bash
################################################################################
#
# Author: Clive Bostock
# Date: 20-May-2026
# Purpose: Restore Orac database schemas from an Orac backup archive.
# Usage: bin/orac-restore.sh [--container NAME] [--pdb NAME] BACKUP_TARBALL
# Example: bin/orac-restore.sh /backups/orac/orac-backup-20260520-120000.tar.gz
#
################################################################################

set -Eeuo pipefail

PROG=$(basename "$0")
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ORAC_PROJECT_HOME=$(dirname "$SCRIPT_DIR")
CONFIG_DIR="${ORAC_PROJECT_HOME}/resources/config"
ENV_FILE="${CONFIG_DIR}/orac.env"
PLUGINS_DIR="${ORAC_PROJECT_HOME}/plugins"

DOCKER_BIN=${ORAC_DOCKER_BIN:-docker}
TAR_BIN=${ORAC_TAR_BIN:-tar}
PYTHON_BIN=${ORAC_PYTHON_BIN:-}
DRY_RUN=0
BACKUP_TARBALL=""

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck source=/dev/null
  source "$ENV_FILE"
fi

CONTAINER_NAME=${CONTAINER_NAME:-orac-db}
ORACLE_PDB=${ORACLE_PDB:-FREEPDB1}
ORAC_DATAPUMP_DIR=${ORAC_DATAPUMP_DIR:-ORAC_DATAPUMP_DIR}
ORAC_DATAPUMP_PATH=${ORAC_DATAPUMP_PATH:-/home/oracle/orac/datapump}
ORAC_RESTORE_TABLE_EXISTS_ACTION=${ORAC_RESTORE_TABLE_EXISTS_ACTION:-${ORAC_RECO_TABLE_EXISTS_ACTION:-replace}}

usage() {
  cat <<EOF
Usage: $PROG [options] BACKUP_TARBALL

Restore Orac database schemas from a backup archive.

Options:
  --container NAME   Oracle database container name. Default: ${CONTAINER_NAME}
  --pdb NAME         Oracle PDB service/container name. Default: ${ORACLE_PDB}
  --dry-run          Validate the archive and show recovery warnings only.
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

validate_dump_file_name() {
  local value="$1"

  [[ -z "$value" || "$value" =~ ^[A-Za-z0-9_.-]+\.dmp$ ]] || fail "Invalid dump file name in backup manifest: ${value}"
}

validate_table_exists_action() {
  case "$ORAC_RESTORE_TABLE_EXISTS_ACTION" in
    skip|append|truncate|replace|SKIP|APPEND|TRUNCATE|REPLACE)
      ;;
    *)
      fail "Invalid ORAC_RESTORE_TABLE_EXISTS_ACTION: ${ORAC_RESTORE_TABLE_EXISTS_ACTION}"
      ;;
  esac
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
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
        [[ -z "$BACKUP_TARBALL" ]] || fail "Only one BACKUP_TARBALL may be supplied"
        BACKUP_TARBALL="$1"
        shift
        ;;
    esac
  done

  [[ -n "$BACKUP_TARBALL" ]] || fail "BACKUP_TARBALL is required"
  [[ -f "$BACKUP_TARBALL" ]] || fail "Backup tarball not found: $BACKUP_TARBALL"
}

read_current_version() {
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

extract_manifest_details() {
  local python="$1"
  local manifest_path="$2"
  local work_dir="$3"

  "$python" - "$manifest_path" "$PLUGINS_DIR" "$ORAC_PROJECT_HOME" "$work_dir" <<'PY'
import json
import re
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
plugins_dir = Path(sys.argv[2])
project_home = Path(sys.argv[3])
work_dir = Path(sys.argv[4])

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
database = manifest.get("database") or {}
schema_name_pattern = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

(work_dir / "backup_version.txt").write_text(str(manifest.get("orac_version", "unknown")) + "\n", encoding="utf-8")
(work_dir / "dump_file.txt").write_text(str(database.get("dump_file") or "") + "\n", encoding="utf-8")
(work_dir / "log_file.txt").write_text(str(database.get("log_file") or "") + "\n", encoding="utf-8")
(work_dir / "skip_db.txt").write_text(("1" if database.get("skip_db") else "0") + "\n", encoding="utf-8")

schemas = database.get("exported_schemas") or []
for schema_name in schemas:
    if not isinstance(schema_name, str) or not schema_name_pattern.fullmatch(schema_name):
        raise ValueError(f"Invalid exported schema name in backup manifest: {schema_name}")
(work_dir / "schemas.txt").write_text("\n".join(schemas) + ("\n" if schemas else ""), encoding="utf-8")

backup_plugins = {
    item.get("plugin_id"): item
    for item in manifest.get("plugins", [])
    if item.get("plugin_id")
}
current_plugins = {}
for plugin_path in sorted(plugins_dir.glob("*.json")):
    plugin_manifest = json.loads(plugin_path.read_text(encoding="utf-8"))
    plugin_id = plugin_manifest.get("plugin_id")
    if plugin_id:
        current_plugins[plugin_id] = {
            "version": plugin_manifest.get("version"),
            "manifest_path": str(plugin_path.relative_to(project_home)),
        }

warnings = []
for plugin_id, backup_plugin in sorted(backup_plugins.items()):
    current_plugin = current_plugins.get(plugin_id)
    if not current_plugin:
        warnings.append(f"Plugin {plugin_id} exists in backup but not in this checkout.")
        continue
    if backup_plugin.get("version") != current_plugin.get("version"):
        warnings.append(
            f"Plugin {plugin_id} version mismatch: backup={backup_plugin.get('version')} "
            f"current={current_plugin.get('version')}."
        )

for plugin_id in sorted(set(current_plugins) - set(backup_plugins)):
    warnings.append(f"Plugin {plugin_id} exists in this checkout but not in backup.")

(work_dir / "plugin_warnings.txt").write_text("\n".join(warnings) + ("\n" if warnings else ""), encoding="utf-8")
PY
}

sql_quoted_csv_from_schema_file() {
  local file_path="$1"

  awk 'NF { printf "%s'\''%s'\''", sep, toupper($0); sep=", " }' "$file_path"
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

write_fk_toggle_sql() {
  local schemas_path="$1"
  local disable_path="$2"
  local enable_path="$3"
  local owner_list

  owner_list=$(sql_quoted_csv_from_schema_file "$schemas_path")
  : >"$disable_path"
  : >"$enable_path"

  [[ -n "$owner_list" ]] || return 0

  "$DOCKER_BIN" exec -i "$CONTAINER_NAME" sqlplus -L -s / as sysdba >"$disable_path" <<SQL
set heading off feedback off pagesize 0 verify off echo off trimspool on linesize 32767
whenever sqlerror exit sql.sqlcode
alter session set container=${ORACLE_PDB};
select 'alter table ' || owner || '.' || table_name ||
       ' disable constraint ' || constraint_name || ';'
  from dba_constraints
 where owner in (${owner_list})
   and constraint_type = 'R'
   and status = 'ENABLED'
 order by owner, table_name, constraint_name;
exit
SQL

  "$DOCKER_BIN" exec -i "$CONTAINER_NAME" sqlplus -L -s / as sysdba >"$enable_path" <<SQL
set heading off feedback off pagesize 0 verify off echo off trimspool on linesize 32767
whenever sqlerror exit sql.sqlcode
alter session set container=${ORACLE_PDB};
select 'alter table ' || owner || '.' || table_name ||
       ' enable constraint ' || constraint_name || ';'
  from dba_constraints
 where owner in (${owner_list})
   and constraint_type = 'R'
   and status = 'ENABLED'
 order by owner, table_name, constraint_name;
exit
SQL
}

execute_sql_file() {
  local sql_path="$1"

  [[ -s "$sql_path" ]] || return 0
  {
    printf 'whenever sqlerror exit sql.sqlcode\n'
    printf 'alter session set container=%s;\n' "$ORACLE_PDB"
    cat "$sql_path"
    printf '\nexit\n'
  } | "$DOCKER_BIN" exec -i "$CONTAINER_NAME" sqlplus -L -s / as sysdba
}

run_datapump_import() {
  local schemas_path="$1"
  local dump_file="$2"
  local schema_csv

  schema_csv=$(uppercase_csv_from_file "$schemas_path")
  [[ -n "$schema_csv" ]] || fail "Backup manifest does not list exported schemas"

  log "Importing schemas: ${schema_csv}"
  "$DOCKER_BIN" exec "$CONTAINER_NAME" bash -lc \
    "cd '${ORAC_DATAPUMP_PATH}' && impdp system/\"\${ORACLE_PWD}\"@//127.0.0.1:1521/${ORACLE_PDB} schemas=${schema_csv} directory=${ORAC_DATAPUMP_DIR} dumpfile=${dump_file} logfile=orac-restore-${dump_file%.dmp}.log table_exists_action=${ORAC_RESTORE_TABLE_EXISTS_ACTION}"
}

confirm_recovery() {
  cat <<EOF

Restore will import database schemas into ${CONTAINER_NAME}/${ORACLE_PDB}.
This can overwrite existing schema objects/data depending on Data Pump behaviour.

Type RECOVER to continue:
EOF
  local answer
  read -r answer
  [[ "$answer" == "RECOVER" ]] || fail "Restore cancelled"
}

parse_args "$@"
validate_container_name "$CONTAINER_NAME"
validate_identifier "$ORACLE_PDB" "ORACLE_PDB"
validate_identifier "$ORAC_DATAPUMP_DIR" "ORAC_DATAPUMP_DIR"
validate_datapump_path
validate_table_exists_action

PYTHON_BIN=$(find_python)
WORK_PARENT=$(mktemp -d "${TMPDIR:-/tmp}/orac-restore.XXXXXX")
EXTRACT_DIR="${WORK_PARENT}/extract"

cleanup() {
  rm -rf "$WORK_PARENT"
}
trap cleanup EXIT

mkdir -p "$EXTRACT_DIR"
"$TAR_BIN" -xzf "$BACKUP_TARBALL" -C "$EXTRACT_DIR"
MANIFEST_PATH=$(find "$EXTRACT_DIR" -name backup_manifest.json -print -quit)
[[ -n "$MANIFEST_PATH" ]] || fail "backup_manifest.json not found in archive"

extract_manifest_details "$PYTHON_BIN" "$MANIFEST_PATH" "$WORK_PARENT"

CURRENT_VERSION=$(read_current_version "$PYTHON_BIN")
BACKUP_VERSION=$(tr -d '\n' <"${WORK_PARENT}/backup_version.txt")
SKIP_DB=$(tr -d '\n' <"${WORK_PARENT}/skip_db.txt")
DUMP_FILE=$(tr -d '\n' <"${WORK_PARENT}/dump_file.txt")
validate_dump_file_name "$DUMP_FILE"

log "Backup Orac version : ${BACKUP_VERSION}"
log "Current Orac version: ${CURRENT_VERSION}"
if [[ "$BACKUP_VERSION" != "$CURRENT_VERSION" ]]; then
  log "WARNING: Orac version mismatch: backup=${BACKUP_VERSION} current=${CURRENT_VERSION}"
fi

if [[ -s "${WORK_PARENT}/plugin_warnings.txt" ]]; then
  log "Plugin version warnings:"
  sed 's/^/  - /' "${WORK_PARENT}/plugin_warnings.txt"
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  log "Dry run only. No database import performed."
  exit 0
fi

confirm_recovery

if [[ "$SKIP_DB" == "1" || -z "$DUMP_FILE" ]]; then
  log "Backup archive does not contain a database export. Nothing to import."
  exit 0
fi

DUMP_PATH=$(find "$EXTRACT_DIR" -path "*/db/${DUMP_FILE}" -print -quit)
[[ -n "$DUMP_PATH" ]] || fail "Dump file not found in archive: ${DUMP_FILE}"

ensure_datapump_directory
write_fk_toggle_sql "${WORK_PARENT}/schemas.txt" "${WORK_PARENT}/disable_fks.sql" "${WORK_PARENT}/enable_fks.sql"

log "Copying dump into ${CONTAINER_NAME}:${ORAC_DATAPUMP_PATH}/${DUMP_FILE}"
"$DOCKER_BIN" cp "$DUMP_PATH" "${CONTAINER_NAME}:${ORAC_DATAPUMP_PATH}/${DUMP_FILE}"

IMPORT_STATUS=0
log "Disabling enabled foreign key constraints for imported schemas."
execute_sql_file "${WORK_PARENT}/disable_fks.sql"

set +e
run_datapump_import "${WORK_PARENT}/schemas.txt" "$DUMP_FILE"
IMPORT_STATUS=$?
set -e

log "Re-enabling foreign key constraints disabled before import."
execute_sql_file "${WORK_PARENT}/enable_fks.sql" || {
  "$DOCKER_BIN" exec "$CONTAINER_NAME" bash -lc "rm -f '${ORAC_DATAPUMP_PATH}/${DUMP_FILE}'" >/dev/null || true
  fail "Import completed with status ${IMPORT_STATUS}, but foreign key re-enable failed"
}

"$DOCKER_BIN" exec "$CONTAINER_NAME" bash -lc "rm -f '${ORAC_DATAPUMP_PATH}/${DUMP_FILE}'" >/dev/null || true

if [[ "$IMPORT_STATUS" -ne 0 ]]; then
  fail "Data Pump import failed with status ${IMPORT_STATUS}"
fi

log "Restore import complete."
