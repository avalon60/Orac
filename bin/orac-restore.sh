#!/usr/bin/env bash
################################################################################
#
# Author: Clive Bostock
# Date: 20-May-2026
# Purpose: Restore Orac database schemas from an Orac backup archive or backup directory.
# Usage: bin/orac-restore.sh [--container NAME] [--pdb NAME] BACKUP_SOURCE
# Example: bin/orac-restore.sh /backups/orac/orac-backup-20260520-120000.tar.gz
# Example: bin/orac-restore.sh /backups/orac
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
BACKUP_SOURCE=""
BACKUP_TARBALL=""

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck source=/dev/null
  source "$ENV_FILE"
fi

CONTAINER_NAME=${CONTAINER_NAME:-orac-db}
ORACLE_PDB=${ORACLE_PDB:-FREEPDB1}
ORAC_DATAPUMP_DIR=${ORAC_DATAPUMP_DIR:-ORAC_DATAPUMP_DIR}
ORAC_DATAPUMP_PATH=${ORAC_DATAPUMP_PATH:-/home/oracle/orac/datapump}
ORAC_RESTORE_CONTENT=${ORAC_RESTORE_CONTENT:-data_only}
ORAC_RESTORE_TABLE_EXISTS_ACTION=${ORAC_RESTORE_TABLE_EXISTS_ACTION:-${ORAC_RECO_TABLE_EXISTS_ACTION:-}}

usage() {
  cat <<EOF
Usage: $PROG [options] BACKUP_SOURCE

Restore Orac database schemas from a backup archive or directory.

When BACKUP_SOURCE is a directory, the newest direct orac-backup-*.tar.gz
archive is selected by filename timestamp.

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

normalize_restore_options() {
  ORAC_RESTORE_CONTENT=${ORAC_RESTORE_CONTENT,,}
  ORAC_RESTORE_TABLE_EXISTS_ACTION=${ORAC_RESTORE_TABLE_EXISTS_ACTION,,}

  case "$ORAC_RESTORE_CONTENT" in
    all|data_only)
      ;;
    *)
      fail "Invalid ORAC_RESTORE_CONTENT: ${ORAC_RESTORE_CONTENT}"
      ;;
  esac

  if [[ -z "$ORAC_RESTORE_TABLE_EXISTS_ACTION" ]]; then
    if [[ "$ORAC_RESTORE_CONTENT" == "data_only" ]]; then
      ORAC_RESTORE_TABLE_EXISTS_ACTION=truncate
    else
      ORAC_RESTORE_TABLE_EXISTS_ACTION=replace
    fi
  fi
}

validate_table_exists_action() {
  case "$ORAC_RESTORE_TABLE_EXISTS_ACTION" in
    skip|append|truncate|replace)
      ;;
    *)
      fail "Invalid ORAC_RESTORE_TABLE_EXISTS_ACTION: ${ORAC_RESTORE_TABLE_EXISTS_ACTION}"
      ;;
  esac

  if [[ "$ORAC_RESTORE_CONTENT" == "data_only" && "$ORAC_RESTORE_TABLE_EXISTS_ACTION" == "replace" ]]; then
    fail "ORAC_RESTORE_TABLE_EXISTS_ACTION=replace requires ORAC_RESTORE_CONTENT=all"
  fi
}

clean_sql_output_file() {
  local output_path="$1"

  sed -i '/^[[:space:]]*$/d; s/^[[:space:]]*//; s/[[:space:]]*$//' "$output_path"
}

resolve_backup_tarball() {
  local source="$1"
  local -a archives=()

  if [[ -f "$source" ]]; then
    BACKUP_TARBALL="$source"
    return 0
  fi

  if [[ -d "$source" ]]; then
    mapfile -d '' -t archives < <(
      find "$source" -maxdepth 1 -type f -name 'orac-backup-*.tar.gz' -print0 | sort -z
    )

    [[ "${#archives[@]}" -gt 0 ]] || fail "No Orac backup archives found in directory: $source"
    BACKUP_TARBALL="${archives[$((${#archives[@]} - 1))]}"
    log "Selected newest backup archive: ${BACKUP_TARBALL}"
    return 0
  fi

  if [[ -e "$source" ]]; then
    fail "Backup source is not a regular file or directory: $source"
  fi

  fail "Backup source not found: $source"
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
        [[ -z "$BACKUP_SOURCE" ]] || fail "Only one BACKUP_SOURCE may be supplied"
        BACKUP_SOURCE="$1"
        shift
        ;;
    esac
  done

  [[ -n "$BACKUP_SOURCE" ]] || fail "BACKUP_SOURCE is required"
  resolve_backup_tarball "$BACKUP_SOURCE"
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
plugin_id_pattern = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

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
schema_plugins = {}
for backup_plugin in manifest.get("plugins", []):
    plugin_id = str(backup_plugin.get("plugin_id") or "").strip()
    if not plugin_id_pattern.fullmatch(plugin_id):
        continue
    for schema_name in backup_plugin.get("database_schemas") or []:
        if not isinstance(schema_name, str) or not schema_name_pattern.fullmatch(schema_name):
            continue
        schema_plugins.setdefault(schema_name.lower(), set()).add(plugin_id)

schema_plugin_lines = [
    f"{schema_name}\t{','.join(sorted(plugin_ids))}"
    for schema_name, plugin_ids in sorted(schema_plugins.items())
]
(work_dir / "schema_plugins.tsv").write_text(
    "\n".join(schema_plugin_lines) + ("\n" if schema_plugin_lines else ""),
    encoding="utf-8",
)
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

query_existing_restore_schemas() {
  local schemas_path="$1"
  local output_path="$2"
  local owner_list

  owner_list=$(sql_quoted_csv_from_schema_file "$schemas_path")
  : >"$output_path"
  [[ -n "$owner_list" ]] || return 0

  if ! "$DOCKER_BIN" exec -i "$CONTAINER_NAME" sqlplus -L -s / as sysdba >"$output_path" <<SQL
set heading off feedback off pagesize 0 verify off echo off trimspool on
whenever sqlerror exit sql.sqlcode
alter session set container=${ORACLE_PDB};
select lower(username)
  from dba_users
 where username in (${owner_list})
 order by username;
exit
SQL
  then
    fail "Restore schema preflight query failed"
  fi
  clean_sql_output_file "$output_path"
}

write_missing_schemas() {
  local requested_path="$1"
  local existing_path="$2"
  local missing_path="$3"

  awk 'NF { print tolower($0) }' "$existing_path" | sort >"${existing_path}.sorted"
  awk 'NF { print tolower($0) }' "$requested_path" | sort >"${requested_path}.sorted"
  comm -23 "${requested_path}.sorted" "${existing_path}.sorted" >"$missing_path"
}

print_missing_schema_guidance() {
  local missing_path="$1"
  local schema_plugins_path="$2"
  local command_path="${WORK_PARENT}/missing_schema_install_commands.txt"
  local schema_name
  local plugin_ids
  local plugin_id
  local -a plugin_id_array

  : >"$command_path"
  log ""
  log "Missing schema(s) required for data-only restore:"
  while IFS= read -r schema_name; do
    [[ -n "$schema_name" ]] || continue
    plugin_ids=$(awk -F '\t' -v schema="$schema_name" '$1 == schema { print $2; exit }' "$schema_plugins_path")
    if [[ -n "$plugin_ids" ]]; then
      log "  - ${schema_name^^} (plugin: ${plugin_ids})"
      IFS=',' read -ra plugin_id_array <<<"$plugin_ids"
      for plugin_id in "${plugin_id_array[@]}"; do
        [[ -n "$plugin_id" ]] || continue
        printf 'bin/orac-plugin.sh install --bundled %s\n' "$plugin_id" >>"$command_path"
      done
    else
      log "  - ${schema_name^^}"
    fi
  done <"$missing_path"

  if [[ -s "$command_path" ]]; then
    sort -u "$command_path" -o "$command_path"
    log ""
    log "Install missing plugin schema objects before rerunning restore, for example:"
    sed 's/^/  - /' "$command_path"
  fi
}

preflight_data_only_restore_schemas() {
  local schemas_path="$1"
  local schema_plugins_path="$2"
  local existing_path="${WORK_PARENT}/existing_restore_schemas.txt"
  local missing_path="${WORK_PARENT}/missing_restore_schemas.txt"

  [[ "$ORAC_RESTORE_CONTENT" == "data_only" ]] || return 0

  log "Checking target schemas for data-only restore."
  query_existing_restore_schemas "$schemas_path" "$existing_path"
  write_missing_schemas "$schemas_path" "$existing_path" "$missing_path"
  if [[ -s "$missing_path" ]]; then
    print_missing_schema_guidance "$missing_path" "$schema_plugins_path"
    fail "Data-only restore requires all exported schemas to exist in the target database. Install the missing plugin schema objects or use an explicitly prepared full metadata restore target."
  fi
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
  log "Data Pump content=${ORAC_RESTORE_CONTENT} table_exists_action=${ORAC_RESTORE_TABLE_EXISTS_ACTION}"
  "$DOCKER_BIN" exec "$CONTAINER_NAME" bash -lc \
    "cd '${ORAC_DATAPUMP_PATH}' && impdp system/\"\${ORACLE_PWD}\"@//127.0.0.1:1521/${ORACLE_PDB} schemas=${schema_csv} directory=${ORAC_DATAPUMP_DIR} dumpfile=${dump_file} logfile=orac-restore-${dump_file%.dmp}.log content=${ORAC_RESTORE_CONTENT} table_exists_action=${ORAC_RESTORE_TABLE_EXISTS_ACTION}"
}

stage_datapump_dump() {
  local dump_file="$1"

  log "Setting Data Pump dump ownership in ${CONTAINER_NAME}"
  "$DOCKER_BIN" exec -u 0 "$CONTAINER_NAME" bash -lc \
    "chown 54321:54321 '${ORAC_DATAPUMP_PATH}/${dump_file}' && chmod 640 '${ORAC_DATAPUMP_PATH}/${dump_file}'"
}

remove_datapump_dump() {
  local dump_file="$1"

  "$DOCKER_BIN" exec -u 0 "$CONTAINER_NAME" bash -lc \
    "rm -f '${ORAC_DATAPUMP_PATH}/${dump_file}'" >/dev/null || true
}

recompile_schema_list() {
  local schemas_path="$1"
  local schema_name

  [[ -s "$schemas_path" ]] || return 0

  while IFS= read -r schema_name; do
    [[ -n "$schema_name" ]] || continue
    schema_name=${schema_name^^}
    validate_identifier "$schema_name" "schema name"

    log "Recompiling ${schema_name} objects."
    "$DOCKER_BIN" exec -i "$CONTAINER_NAME" sqlplus -L -s / as sysdba <<SQL
whenever sqlerror exit sql.sqlcode
alter session set container=${ORACLE_PDB};
begin
  dbms_utility.compile_schema(
    schema => '${schema_name}',
    compile_all => false
  );
end;
/
exit
SQL
  done <"$schemas_path"
}

generate_fk_enable_sql() {
  local schemas_path="$1"
  local output_path="$2"
  local owner_list

  owner_list=$(sql_quoted_csv_from_schema_file "$schemas_path")
  : >"$output_path"
  [[ -n "$owner_list" ]] || return 0

  "$DOCKER_BIN" exec -i "$CONTAINER_NAME" sqlplus -L -s / as sysdba >"$output_path" <<SQL
set heading off feedback off pagesize 0 verify off echo off trimspool on linesize 32767
whenever sqlerror exit sql.sqlcode
alter session set container=${ORACLE_PDB};
select 'alter table ' || owner || '.' || table_name ||
       ' enable validate constraint ' || constraint_name || ';'
  from all_constraints
 where owner in (${owner_list})
   and constraint_type = 'R'
 order by owner,
          table_name,
          constraint_name;
exit
SQL
  clean_sql_output_file "$output_path"
}

normalize_restored_imported_state() {
  local schemas_path="$1"
  local fk_enable_sql="${WORK_PARENT}/restore_enable_imported_fks.sql"

  [[ -s "$schemas_path" ]] || return 0

  log "Normalizing restored foreign keys."
  generate_fk_enable_sql "$schemas_path" "$fk_enable_sql" || fail "Restore normalization foreign key query failed"
  execute_sql_file "$fk_enable_sql"

  log "Recompiling restored schemas."
  recompile_schema_list "$schemas_path"
}

verify_restore_recovery_api() {
  local output_path="${WORK_PARENT}/restore_recovery_api_objects.tsv"
  local object_count
  local valid_count

  log "Verifying post-restore recovery API is installed."
  if ! "$DOCKER_BIN" exec -i "$CONTAINER_NAME" sqlplus -L -s / as sysdba >"$output_path" <<SQL
set heading off feedback off pagesize 0 verify off echo off trimspool on linesize 32767
whenever sqlerror exit sql.sqlcode
alter session set container=${ORACLE_PDB};
select object_type || chr(9) || status
  from all_objects
 where owner = 'ORAC_CODE'
   and object_name = 'RESTORE_RECOVERY_API'
   and object_type in ('PACKAGE', 'PACKAGE BODY')
 order by object_type;
exit
SQL
  then
    fail "Restore recovery API preflight query failed"
  fi
  clean_sql_output_file "$output_path"

  object_count=$(wc -l <"$output_path" | tr -d '[:space:]')
  valid_count=$(awk -F '\t' 'NF == 2 && $2 == "VALID" { count++ } END { print count + 0 }' "$output_path")
  if [[ "$object_count" -ne 2 || "$valid_count" -ne 2 ]]; then
    fail "Restore requires valid ORAC_CODE.RESTORE_RECOVERY_API package and package body. Stage the restore_recovery_api SQL files into orac-db and run /home/oracle/orac/bin/deploy-orac-db.sh --validate then --update before restoring."
  fi
}

quarantine_restored_plugin_state() {
  log "Quarantining restored plugin runtime state pending plugin reinstall."
  "$DOCKER_BIN" exec -i "$CONTAINER_NAME" sqlplus -L -s / as sysdba <<SQL
whenever sqlerror exit sql.sqlcode
alter session set container=${ORACLE_PDB};
begin
  orac_code.restore_recovery_api.quarantine_plugin_state;
end;
/
exit
SQL
}

query_invalid_objects() {
  local schemas_path="$1"
  local output_path="$2"
  local owner_list

  owner_list=$(sql_quoted_csv_from_schema_file "$schemas_path")
  : >"$output_path"
  [[ -n "$owner_list" ]] || return 0

  if ! "$DOCKER_BIN" exec -i "$CONTAINER_NAME" sqlplus -L -s / as sysdba >"$output_path" <<SQL
set heading off feedback off pagesize 0 verify off echo off trimspool on linesize 32767
whenever sqlerror exit sql.sqlcode
alter session set container=${ORACLE_PDB};
select owner || chr(9) || object_type || chr(9) || object_name || chr(9) || status
  from all_objects
 where owner in (${owner_list})
   and status <> 'VALID'
 order by owner,
          object_type,
          object_name;
exit
SQL
  then
    return 1
  fi
  clean_sql_output_file "$output_path"
}

query_fk_constraint_issues() {
  local schemas_path="$1"
  local output_path="$2"
  local owner_list

  owner_list=$(sql_quoted_csv_from_schema_file "$schemas_path")
  : >"$output_path"
  [[ -n "$owner_list" ]] || return 0

  if ! "$DOCKER_BIN" exec -i "$CONTAINER_NAME" sqlplus -L -s / as sysdba >"$output_path" <<SQL
set heading off feedback off pagesize 0 verify off echo off trimspool on linesize 32767
whenever sqlerror exit sql.sqlcode
alter session set container=${ORACLE_PDB};
select owner || chr(9) || table_name || chr(9) || constraint_name || chr(9) ||
       status || chr(9) || validated
  from all_constraints
 where owner in (${owner_list})
   and constraint_type = 'R'
   and (
         status <> 'ENABLED'
      or validated <> 'VALIDATED'
       )
 order by owner,
          table_name,
          constraint_name;
exit
SQL
  then
    return 1
  fi
  clean_sql_output_file "$output_path"
}

query_core_table_count() {
  local table_name="$1"
  local output_path="$2"
  local count_value

  validate_identifier "$table_name" "validation table name"
  if ! "$DOCKER_BIN" exec -i "$CONTAINER_NAME" sqlplus -L -s / as sysdba >"$output_path" <<SQL
set heading off feedback off pagesize 0 verify off echo off trimspool on
whenever sqlerror exit sql.sqlcode
alter session set container=${ORACLE_PDB};
select count(*)
  from ORAC_CORE.${table_name};
exit
SQL
  then
    return 1
  fi
  clean_sql_output_file "$output_path"
  count_value=$(tr -d '[:space:]' <"$output_path")
  [[ "$count_value" =~ ^[0-9]+$ ]] || return 1
  printf '%s\n' "$count_value"
}

print_tsv_table() {
  local output_path="$1"
  local format="$2"

  awk -F '\t' -v fmt="$format" 'NF { printf fmt, $1, $2, $3, $4, $5 }' "$output_path"
}

run_restore_validation() {
  local schemas_path="$1"
  local invalid_objects_path="${WORK_PARENT}/validation_invalid_objects.tsv"
  local fk_issues_path="${WORK_PARENT}/validation_fk_issues.tsv"
  local count_path="${WORK_PARENT}/validation_row_count.txt"
  local invalid_count
  local disabled_fk_count
  local unvalidated_fk_count
  local users_count
  local conversations_count
  local messages_count
  local user_preferences_count
  local llm_registry_count
  local tts_voices_count
  local personalities_count
  local preference_definitions_count
  local generation_presets_count
  local validation_failed=0

  log "Running post-restore validation."

  query_invalid_objects "$schemas_path" "$invalid_objects_path" || fail "Restore validation invalid object query failed"
  query_fk_constraint_issues "$schemas_path" "$fk_issues_path" || fail "Restore validation foreign key query failed"

  invalid_count=$(wc -l <"$invalid_objects_path" | tr -d '[:space:]')
  disabled_fk_count=$(awk -F '\t' 'NF && $4 != "ENABLED" { count++ } END { print count + 0 }' "$fk_issues_path")
  unvalidated_fk_count=$(awk -F '\t' 'NF && $5 != "VALIDATED" { count++ } END { print count + 0 }' "$fk_issues_path")

  users_count=$(query_core_table_count "USERS" "$count_path") || fail "Restore validation row count failed for ORAC_CORE.USERS"
  conversations_count=$(query_core_table_count "CONVERSATIONS" "$count_path") || fail "Restore validation row count failed for ORAC_CORE.CONVERSATIONS"
  messages_count=$(query_core_table_count "MESSAGES" "$count_path") || fail "Restore validation row count failed for ORAC_CORE.MESSAGES"
  user_preferences_count=$(query_core_table_count "USER_PREFERENCES" "$count_path") || fail "Restore validation row count failed for ORAC_CORE.USER_PREFERENCES"
  llm_registry_count=$(query_core_table_count "LLM_REGISTRY" "$count_path") || fail "Restore validation row count failed for ORAC_CORE.LLM_REGISTRY"
  tts_voices_count=$(query_core_table_count "TTS_VOICES" "$count_path") || fail "Restore validation row count failed for ORAC_CORE.TTS_VOICES"
  personalities_count=$(query_core_table_count "ORAC_PERSONALITIES" "$count_path") || fail "Restore validation row count failed for ORAC_CORE.ORAC_PERSONALITIES"
  preference_definitions_count=$(query_core_table_count "PREFERENCE_DEFINITIONS" "$count_path") || fail "Restore validation row count failed for ORAC_CORE.PREFERENCE_DEFINITIONS"
  generation_presets_count=$(query_core_table_count "MODEL_GENERATION_PRESETS" "$count_path") || fail "Restore validation row count failed for ORAC_CORE.MODEL_GENERATION_PRESETS"

  log ""
  log "## Restore validation summary"
  printf '%-25s : %s\n' "Invalid objects" "$invalid_count"
  printf '%-25s : %s\n' "Disabled FK constraints" "$disabled_fk_count"
  printf '%-25s : %s\n' "Unvalidated FKs" "$unvalidated_fk_count"
  printf '%-25s : %s\n' "Users" "$users_count"
  printf '%-25s : %s\n' "Conversations" "$conversations_count"
  printf '%-25s : %s\n' "Messages" "$messages_count"
  printf '%-25s : %s\n' "User preferences" "$user_preferences_count"
  printf '%-25s : %s\n' "LLM registry rows" "$llm_registry_count"
  printf '%-25s : %s\n' "TTS voices" "$tts_voices_count"
  printf '%-25s : %s\n' "Personalities" "$personalities_count"
  printf '%-25s : %s\n' "Preference definitions" "$preference_definitions_count"
  printf '%-25s : %s\n' "Generation presets" "$generation_presets_count"

  if [[ "$invalid_count" -ne 0 ]]; then
    log ""
    log "Invalid objects:"
    printf '%-16s %-18s %-40s %-10s\n' "OWNER" "OBJECT_TYPE" "OBJECT_NAME" "STATUS"
    print_tsv_table "$invalid_objects_path" '%-16s %-18s %-40s %-10s\n'
    validation_failed=1
  fi

  if [[ "$disabled_fk_count" -ne 0 || "$unvalidated_fk_count" -ne 0 ]]; then
    log ""
    log "Foreign key constraint issues:"
    printf '%-16s %-32s %-32s %-10s %-12s\n' "OWNER" "TABLE_NAME" "CONSTRAINT_NAME" "STATUS" "VALIDATED"
    print_tsv_table "$fk_issues_path" '%-16s %-32s %-32s %-10s %-12s\n'
    validation_failed=1
  fi

  [[ "$validation_failed" -eq 0 ]] || fail "Restore validation failed"
  log "Restore validation complete."
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
normalize_restore_options
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
# TODO: Add a database-level schema/build version compatibility check once
# Orac records deployed schema build versions in the database.

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

verify_restore_recovery_api

preflight_data_only_restore_schemas "${WORK_PARENT}/schemas.txt" "${WORK_PARENT}/schema_plugins.tsv"

DUMP_PATH=$(find "$EXTRACT_DIR" -path "*/db/${DUMP_FILE}" -print -quit)
[[ -n "$DUMP_PATH" ]] || fail "Dump file not found in archive: ${DUMP_FILE}"

ensure_datapump_directory
write_fk_toggle_sql "${WORK_PARENT}/schemas.txt" "${WORK_PARENT}/disable_fks.sql" "${WORK_PARENT}/enable_fks.sql"

log "Copying dump into ${CONTAINER_NAME}:${ORAC_DATAPUMP_PATH}/${DUMP_FILE}"
"$DOCKER_BIN" cp "$DUMP_PATH" "${CONTAINER_NAME}:${ORAC_DATAPUMP_PATH}/${DUMP_FILE}"
stage_datapump_dump "$DUMP_FILE"

IMPORT_STATUS=0
log "Disabling enabled foreign key constraints for imported schemas."
execute_sql_file "${WORK_PARENT}/disable_fks.sql"

set +e
run_datapump_import "${WORK_PARENT}/schemas.txt" "$DUMP_FILE"
IMPORT_STATUS=$?
set -e

log "Re-enabling foreign key constraints disabled before import."
execute_sql_file "${WORK_PARENT}/enable_fks.sql" || {
  remove_datapump_dump "$DUMP_FILE"
  fail "Import completed with status ${IMPORT_STATUS}, but foreign key re-enable failed"
}

if [[ "$IMPORT_STATUS" -ne 0 ]]; then
  remove_datapump_dump "$DUMP_FILE"
  fail "Data Pump import failed with status ${IMPORT_STATUS}"
fi

normalize_restored_imported_state "${WORK_PARENT}/schemas.txt"
quarantine_restored_plugin_state || {
  remove_datapump_dump "$DUMP_FILE"
  fail "Post-restore plugin quarantine failed. Verify ORAC_CODE.RESTORE_RECOVERY_API is installed and valid, then rerun restore."
}
remove_datapump_dump "$DUMP_FILE"

log "Restore import complete."
run_restore_validation "${WORK_PARENT}/schemas.txt"
