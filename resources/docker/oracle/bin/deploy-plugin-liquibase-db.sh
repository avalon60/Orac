#!/usr/bin/env bash
# Author: Clive Bostock
# Date: 21-Jun-2026
# Description: Deploy plugin-owned database deltas with SQLcl Liquibase.
#
# Purpose: Run a validated plugin Liquibase controller inside an isolated plugin schema.
# Usage: deploy-plugin-liquibase-db.sh --plugin-id home_assistant --archive /path/plugin-db.tar.gz --schema-name orac_ha --default-schema-name orac_ha --liquibase-schema-name orac_ha [--dry-run]
set -euo pipefail

PROG="Orac: deploy-plugin-liquibase-db.sh"
ORAC_HOME="${ORAC_HOME:-/home/oracle/orac}"
ORACLE_PDB="${ORACLE_PDB:-FREEPDB1}"
SQLCL_HOME="${SQLCL_HOME:-${ORAC_HOME}/setup/sqlcl/sqlcl}"
LIQUIBASE_PROPERTIES_SOURCE="${LIQUIBASE_PROPERTIES_SOURCE:-${ORAC_HOME}/liquibase/liquibase-plugin.properties}"
PLUGIN_STAGING_ROOT="${PLUGIN_STAGING_ROOT:-${ORAC_HOME}/plugin_staging}"
LOG_ROOT="${LOG_ROOT:-${ORAC_HOME}/logs/liquibase/plugins}"

PLUGIN_ID=""
ARCHIVE=""
SCHEMA_NAME=""
DEFAULT_SCHEMA_NAME=""
LIQUIBASE_SCHEMA_NAME=""
CONTROLLER="db/liquibase/pluginController.xml"
DRY_RUN=0

timestamp() {
  date +"%Y-%m-%d %H:%M:%S"
}

log() {
  printf '[%s] %s %s\n' "$(timestamp)" "${PROG}" "$*"
}

fail() {
  log "ERROR: $*" >&2
  exit 1
}

usage() {
  cat <<EOF
Usage: deploy-plugin-liquibase-db.sh --plugin-id PLUGIN_ID --archive ARCHIVE --schema-name SCHEMA [--controller PATH] [--dry-run]

Deploy a plugin-owned Liquibase payload archive. The archive must contain:
  manifest.json
  plugin.json
  db/schema/**
  db/liquibase/pluginController.xml
EOF
}

validate_identifier() {
  local value="$1"
  local label="$2"
  [[ "${value}" =~ ^[A-Za-z][A-Za-z0-9_]*$ ]] || fail "Invalid ${label}: ${value}"
}

liquibase_log_has_error() {
  local log_file="$1"

  grep -Eiq \
    "^(ERROR:|Connection failed|An error has occurred:|Processing has failed)|ORA-[0-9]{5}|SP2-[0-9]{4}|Option not recognized|Unexpected token|can not be used for Liquibase" \
    "${log_file}"
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
      --schema-name)
        [[ $# -ge 2 ]] || fail "--schema-name requires a value"
        SCHEMA_NAME="$2"
        shift 2
        ;;
      --default-schema-name)
        [[ $# -ge 2 ]] || fail "--default-schema-name requires a value"
        DEFAULT_SCHEMA_NAME="$2"
        shift 2
        ;;
      --liquibase-schema-name)
        [[ $# -ge 2 ]] || fail "--liquibase-schema-name requires a value"
        LIQUIBASE_SCHEMA_NAME="$2"
        shift 2
        ;;
      --controller)
        [[ $# -ge 2 ]] || fail "--controller requires a value"
        CONTROLLER="$2"
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
  [[ -n "${SCHEMA_NAME}" ]] || fail "--schema-name is required"
  [[ -n "${DEFAULT_SCHEMA_NAME}" ]] || fail "--default-schema-name is required"
  [[ -n "${LIQUIBASE_SCHEMA_NAME}" ]] || fail "--liquibase-schema-name is required"
  validate_identifier "${PLUGIN_ID}" "plugin id"
  validate_identifier "${SCHEMA_NAME}" "schema name"
  validate_identifier "${DEFAULT_SCHEMA_NAME}" "default schema name"
  validate_identifier "${LIQUIBASE_SCHEMA_NAME}" "Liquibase schema name"
  [[ "${DEFAULT_SCHEMA_NAME^^}" == "${SCHEMA_NAME^^}" ]] || fail "--default-schema-name must match --schema-name"
  [[ "${LIQUIBASE_SCHEMA_NAME^^}" == "${SCHEMA_NAME^^}" ]] || fail "--liquibase-schema-name must match --schema-name"
  [[ -f "${ARCHIVE}" ]] || fail "Archive does not exist: ${ARCHIVE}"
  [[ -x "${SQLCL_HOME}/bin/sql" ]] || fail "SQLcl executable not found: ${SQLCL_HOME}/bin/sql"
  [[ -f "${LIQUIBASE_PROPERTIES_SOURCE}" ]] || fail "Plugin Liquibase properties file missing: ${LIQUIBASE_PROPERTIES_SOURCE}"
}

plugin_row_predicate() {
  local plugin_path
  local plugin_label
  local plugin_author
  local schema_token

  plugin_path="plugins/${PLUGIN_ID}/"
  plugin_label="${PLUGIN_ID}"
  plugin_author="${PLUGIN_ID}"
  schema_token="${SCHEMA_NAME^^}"

  cat <<SQL
(
       lower(filename) like '%${plugin_path}%'
    or upper(filename) like '%${schema_token}%'
    or lower(id) like '${plugin_label}_%'
    or lower(author) = '${plugin_author}'
    or lower(labels) like '%${plugin_label}%'
    or lower(contexts) like '%${plugin_label}%'
)
SQL
}

run_tracking_sql() {
  local sql_body="$1"

  sqlplus -L -s / as sysdba <<SQL
whenever sqlerror exit failure rollback
set heading off feedback off pagesize 0 verify off echo off trimspool on
set define off
set serveroutput on size unlimited
alter session set container=${ORACLE_PDB};
${sql_body}
exit
SQL
}

ensure_plugin_schema_login() {
  local password

  password="${ORACLE_PWD:?ORACLE_PWD is required}"
  password="${password//\"/\"\"}"
  run_tracking_sql "alter user ${SCHEMA_NAME^^} identified by \"${password}\" account unlock;" >/dev/null
}

preflight_tracking_checks() {
  local predicate
  local output

  predicate="$(plugin_row_predicate)"
  output="$(
    run_tracking_sql "
select 'MISSING_SCHEMA'
  from dual
 where not exists (
       select 1
         from dba_users
        where username = upper('${SCHEMA_NAME}')
      );
select 'TRACKING_TABLE ' || owner || '.' || table_name
  from dba_tables
 where owner = upper('${SCHEMA_NAME}')
   and table_name in ('DATABASECHANGELOG', 'DATABASECHANGELOGLOCK')
 order by table_name;
declare
  l_count number;
begin
  for changelog_table in (
    select owner
      from dba_tables
     where table_name = 'DATABASECHANGELOG'
       and owner <> upper('${SCHEMA_NAME}')
     order by case when owner = 'SYSTEM' then 0 else 1 end, owner
  )
  loop
    execute immediate
      'select count(1) from ' || changelog_table.owner ||
      '.databasechangelog where ' || q'~${predicate}~'
      into l_count;

    if l_count > 0
    then
      dbms_output.put_line(
        'CONTAMINATED_CHANGELOG ' || changelog_table.owner ||
        '.DATABASECHANGELOG rows=' || l_count
      );
    end if;
  end loop;
end;
/
"
  )"

  if grep -q '^MISSING_SCHEMA$' <<<"${output}"; then
    fail "Plugin schema does not exist: ${SCHEMA_NAME}"
  fi
  if grep -q '^CONTAMINATED_CHANGELOG ' <<<"${output}"; then
    fail "Plugin-owned Liquibase rows were found outside ${SCHEMA_NAME}; guarded repair is required: $(grep '^CONTAMINATED_CHANGELOG ' <<<"${output}" | tr '\n' ';')"
  fi
}

post_update_tracking_checks() {
  local predicate
  local output

  predicate="$(plugin_row_predicate)"
  output="$(
    run_tracking_sql "
select 'MISSING_TRACKING_TABLE ' || required.table_name
  from (
       select 'DATABASECHANGELOG' table_name from dual union all
       select 'DATABASECHANGELOGLOCK' table_name from dual
       ) required
 where not exists (
       select 1
         from dba_tables t
       where t.owner = upper('${SCHEMA_NAME}')
          and t.table_name = required.table_name
      );
declare
  l_tracking_table_count number := 0;
  l_count number := 0;
begin
  select count(1)
    into l_tracking_table_count
    from dba_tables
   where owner = upper('${SCHEMA_NAME}')
     and table_name = 'DATABASECHANGELOG';

  if l_tracking_table_count > 0
  then
    execute immediate
      'select count(1) from ${SCHEMA_NAME}.databasechangelog where ' || q'~${predicate}~'
      into l_count;
  end if;

  if l_count = 0
  then
    dbms_output.put_line('MISSING_PLUGIN_CHANGELOG_ROWS');
  end if;

  for changelog_table in (
    select owner
      from dba_tables
     where table_name = 'DATABASECHANGELOG'
       and owner <> upper('${SCHEMA_NAME}')
     order by case when owner = 'SYSTEM' then 0 else 1 end, owner
  )
  loop
    execute immediate
      'select count(1) from ' || changelog_table.owner ||
      '.databasechangelog where ' || q'~${predicate}~'
      into l_count;

    if l_count > 0
    then
      dbms_output.put_line(
        'CONTAMINATED_CHANGELOG ' || changelog_table.owner ||
        '.DATABASECHANGELOG rows=' || l_count
      );
    end if;
  end loop;
end;
/
"
  )"

  if grep -q '^MISSING_TRACKING_TABLE ' <<<"${output}"; then
    fail "Plugin Liquibase tracking tables were not created in ${SCHEMA_NAME}: $(grep '^MISSING_TRACKING_TABLE ' <<<"${output}" | tr '\n' ';')"
  fi
  if grep -q '^MISSING_PLUGIN_CHANGELOG_ROWS$' <<<"${output}"; then
    fail "No plugin-owned Liquibase changelog rows were recorded in ${SCHEMA_NAME}.DATABASECHANGELOG"
  fi
  if grep -q '^CONTAMINATED_CHANGELOG ' <<<"${output}"; then
    fail "Plugin-owned Liquibase rows were written to SYSTEM; guarded repair is required: $(grep '^CONTAMINATED_CHANGELOG ' <<<"${output}" | tr '\n' ';')"
  fi
}

main() {
  parse_args "$@"

  local plugin_root
  local work_dir
  local controller_path
  local controller_relative
  local properties_path
  local log_dir
  local log_file
  local command
  local sqlcl_rc

  plugin_root="$(dirname "${ARCHIVE}")"
  work_dir="${plugin_root}/work-liquibase-${SCHEMA_NAME}"
  rm -rf "${work_dir}"
  mkdir -p "${work_dir}"

  log "Unpacking ${ARCHIVE} into ${work_dir}"
  tar -xzf "${ARCHIVE}" -C "${work_dir}"

  [[ -f "${work_dir}/manifest.json" ]] || fail "manifest.json is missing from archive"
  [[ -f "${work_dir}/plugin.json" ]] || fail "plugin.json is missing from archive"
  [[ -d "${work_dir}/db/schema" ]] || fail "db/schema is missing from archive"
  controller_path="${work_dir}/${CONTROLLER}"
  [[ -f "${controller_path}" ]] || fail "Plugin Liquibase controller is missing: ${CONTROLLER}"
  controller_relative="${CONTROLLER}"

  if [[ "${DRY_RUN}" == "1" ]]; then
    command="update-sql"
  else
    command="update"
  fi

  properties_path="${work_dir}/liquibase-plugin.properties"
  grep -Ev '^(liquibase\.command\.(contextFilter|labelFilter)|searchPath)=' \
    "${LIQUIBASE_PROPERTIES_SOURCE}" >"${properties_path}" || true
  {
    printf 'defaultSchemaName=%s\n' "${DEFAULT_SCHEMA_NAME^^}"
    printf 'liquibaseSchemaName=%s\n' "${LIQUIBASE_SCHEMA_NAME^^}"
    printf 'liquibase.command.defaultSchemaName=%s\n' "${DEFAULT_SCHEMA_NAME^^}"
    printf 'liquibase.command.liquibaseSchemaName=%s\n' "${LIQUIBASE_SCHEMA_NAME^^}"
    printf 'liquibase.command.contextFilter=plugin,prod\n'
    printf 'liquibase.command.labelFilter=plugin\n'
    printf 'searchPath=%s\n' "${work_dir}"
  } >>"${properties_path}"
  log_dir="${LOG_ROOT}/${PLUGIN_ID}/${SCHEMA_NAME}/$(date +%Y%m%d_%H%M%S)"
  mkdir -p "${log_dir}"
  log_file="${log_dir}/${command}.log"

  if [[ "${command}" == "update" ]]; then
    preflight_tracking_checks
  fi
  ensure_plugin_schema_login

  # Each plugin schema owns its own Liquibase history and lock tables. The
  # wrapper connects as the plugin schema and explicitly directs SQLcl Liquibase
  # to use that same schema for both object defaults and tracking. Post-update
  # checks fail the deployment if SQLcl records plugin rows anywhere else.
  log "Running plugin Liquibase ${command}; log=${log_file}"
  sqlcl_rc=0
  {
    printf 'set echo off\n'
    printf 'set sqlblanklines on\n'
    printf 'whenever sqlerror exit sql.sqlcode\n'
    printf 'connect %s/"%s"@//127.0.0.1:1521/%s\n' "${SCHEMA_NAME^^}" "${ORACLE_PWD:?ORACLE_PWD is required}" "${ORACLE_PDB}"
    printf 'set echo on\n'
    printf 'liquibase %s -defaults-file %s -changelog-file %s -search-path %s\n' \
      "${command}" "${properties_path}" "${controller_relative}" "${work_dir}"
    printf 'exit\n'
  } | "${SQLCL_HOME}/bin/sql" -S /nolog >"${log_file}" 2>&1 || sqlcl_rc=$?

  if [[ ${sqlcl_rc} -ne 0 ]]; then
    log "Plugin Liquibase ${command} failed with exit ${sqlcl_rc}. See ${log_file}" >&2
    return "${sqlcl_rc}"
  fi
  if liquibase_log_has_error "${log_file}"; then
    log "Plugin Liquibase ${command} reported an error. See ${log_file}" >&2
    return 1
  fi

  if [[ "${command}" == "update" ]]; then
    post_update_tracking_checks
  fi

  log "Plugin Liquibase ${command} completed. See ${log_file}"
}

main "$@"
