#!/usr/bin/env bash
# Author: Clive Bostock
# Date: 21-Jun-2026
# Description: Run on-demand core Orac SQLcl Liquibase database changes.
#
# Purpose: Validate, preview, apply, or probe core Orac database Liquibase changes.
# Usage: deploy-orac-db.sh [--probe-tracking|--validate|--update-sql|--update|--changelog-sync] [--contexts core,prod] [--labels core]
set -euo pipefail

PROG="Orac: deploy-orac-db.sh"
ORAC_HOME="${ORAC_HOME:-/home/oracle/orac}"
ORACLE_PDB="${ORACLE_PDB:-FREEPDB1}"
SQLCL_HOME="${SQLCL_HOME:-${ORAC_HOME}/setup/sqlcl/sqlcl}"
LIQUIBASE_HOME="${LIQUIBASE_HOME:-${ORAC_HOME}/liquibase}"
LIQUIBASE_SEARCH_PATH="${LIQUIBASE_SEARCH_PATH:-${ORAC_HOME}/schema}"
PROPERTIES_FILE="${PROPERTIES_FILE:-${LIQUIBASE_HOME}/liquibase-core.properties}"
CHANGELOG_FILE="${CHANGELOG_FILE:-productController.xml}"
LOG_ROOT="${LOG_ROOT:-${ORAC_HOME}/logs/liquibase/core}"
LIQUIBASE_DB_USER="${LIQUIBASE_DB_USER:-SYSTEM}"
MODE="update"
CONTEXTS="${CONTEXTS:-core,prod}"
LABELS="${LABELS:-core}"
DEFAULT_CHANGELOG_TABLE="DATABASECHANGELOG"
DEFAULT_CHANGELOG_LOCK_TABLE="DATABASECHANGELOGLOCK"

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
Usage: deploy-orac-db.sh [--probe-tracking|--validate|--update-sql|--update|--changelog-sync] [--contexts LIST] [--labels LIST]

Run on-demand core Orac Liquibase deployment from inside the orac-db container.

Options:
  --probe-tracking
                   Run a controlled validate/update-sql/update probe and verify
                   the Liquibase tracking table names SQLcl actually uses.
  --validate       Validate the configured changelog only.
  --update-sql     Print SQL that would be executed.
  --update         Apply pending changes. This is the default.
  --changelog-sync Adopt an existing SQL*Plus-created developer database by
                   validating representative objects and marking baseline
                   changesets as ran without executing them.
  --contexts LIST  Liquibase context filter. Default: ${CONTEXTS}
  --labels LIST    Liquibase label filter. Default: ${LABELS}
  -h, --help       Show this help.

Example:
  deploy-orac-db.sh --update-sql --contexts core,dev --labels core
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --validate)
        MODE="validate"
        shift
        ;;
      --probe-tracking)
        MODE="probe-tracking"
        shift
        ;;
      --update-sql)
        MODE="update-sql"
        shift
        ;;
      --update)
        MODE="update"
        shift
        ;;
      --changelog-sync)
        MODE="changelog-sync"
        shift
        ;;
      --contexts)
        [[ $# -ge 2 ]] || fail "--contexts requires a value"
        CONTEXTS="$2"
        shift 2
        ;;
      --labels)
        [[ $# -ge 2 ]] || fail "--labels requires a value"
        LABELS="$2"
        shift 2
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
}

validate_environment() {
  [[ -x "${SQLCL_HOME}/bin/sql" ]] || fail "SQLcl executable not found: ${SQLCL_HOME}/bin/sql"
  [[ -f "${PROPERTIES_FILE}" ]] || fail "Liquibase properties file missing: ${PROPERTIES_FILE}"
  [[ -f "$(resolved_changelog_file)" ]] || fail "Liquibase changelog missing: $(resolved_changelog_file)"
  [[ -n "${ORACLE_PWD:-}" ]] || fail "ORACLE_PWD is required"

  case "${LIQUIBASE_DB_USER^^}" in
    SYS|SYSDBA)
      fail "SQLcl Liquibase cannot run as ${LIQUIBASE_DB_USER}; use a non-SYS deployment user"
      ;;
  esac
}

resolved_changelog_file() {
  if [[ "${CHANGELOG_FILE}" = /* ]]; then
    printf '%s\n' "${CHANGELOG_FILE}"
  else
    printf '%s/%s\n' "${LIQUIBASE_SEARCH_PATH}" "${CHANGELOG_FILE}"
  fi
}

write_runtime_properties() {
  local runtime_properties="$1"

  grep -Ev '^(liquibase\.command\.(contextFilter|labelFilter)|searchPath)=' \
    "${PROPERTIES_FILE}" >"${runtime_properties}" || true
  {
    printf 'liquibase.command.contextFilter=%s\n' "${CONTEXTS}"
    printf 'liquibase.command.labelFilter=%s\n' "${LABELS}"
    printf 'searchPath=%s\n' "${LIQUIBASE_SEARCH_PATH}"
  } >>"${runtime_properties}"
}

configured_property() {
  local properties_file="$1"
  local key="$2"

  awk -F= -v key="${key}" '
    $1 == key {
      value = $2
      for (i = 3; i <= NF; i++) {
        value = value "=" $i
      }
    }
    END {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      print value
    }
  ' "${properties_file}"
}

uppercase_identifier() {
  tr '[:lower:]' '[:upper:]'
}

expected_changelog_table() {
  local properties_file="$1"
  local configured

  configured="$(configured_property "${properties_file}" "databaseChangeLogTableName")"
  if [[ -z "${configured}" ]]; then
    printf '%s\n' "${DEFAULT_CHANGELOG_TABLE}"
  else
    printf '%s\n' "${configured}" | uppercase_identifier
  fi
}

expected_changelog_lock_table() {
  local properties_file="$1"
  local configured

  configured="$(configured_property "${properties_file}" "databaseChangeLogLockTableName")"
  if [[ -z "${configured}" ]]; then
    printf '%s\n' "${DEFAULT_CHANGELOG_LOCK_TABLE}"
  else
    printf '%s\n' "${configured}" | uppercase_identifier
  fi
}

verify_tracking_tables() {
  local properties_file="$1"
  local log_dir="$2"
  local expected_changelog
  local expected_lock
  local observed_log
  local observed_tables

  expected_changelog="$(expected_changelog_table "${properties_file}")"
  expected_lock="$(expected_changelog_lock_table "${properties_file}")"
  observed_log="${log_dir}/tracking-tables.log"

  {
    printf 'set echo off\n'
    printf 'set heading off feedback off pagesize 0 verify off trimspool on\n'
    printf 'whenever sqlerror exit sql.sqlcode\n'
    printf 'connect %s/"%s"@//127.0.0.1:1521/%s\n' "${LIQUIBASE_DB_USER}" "${ORACLE_PWD}" "${ORACLE_PDB}"
    printf "select table_name from all_tables where owner = upper('%s') and lower(table_name) like '%%databasechangelog%%' order by table_name;\n" "${LIQUIBASE_DB_USER}"
    printf 'exit\n'
  } | "${SQLCL_HOME}/bin/sql" -S /nolog >"${observed_log}" 2>&1

  observed_tables="$(
    grep -E '^[[:space:]]*[[:alnum:]_]+[[:space:]]*$' "${observed_log}" \
      | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//' || true
  )"

  if ! grep -qx "${expected_changelog}" <<<"${observed_tables}"; then
    log "Configured Liquibase changelog table ${expected_changelog} was not observed for ${LIQUIBASE_DB_USER}. Observed: ${observed_tables//$'\n'/,}" >&2
    return 1
  fi
  if ! grep -qx "${expected_lock}" <<<"${observed_tables}"; then
    log "Configured Liquibase changelog lock table ${expected_lock} was not observed for ${LIQUIBASE_DB_USER}. Observed: ${observed_tables//$'\n'/,}" >&2
    return 1
  fi

  log "Verified Liquibase tracking tables for ${LIQUIBASE_DB_USER}: ${expected_changelog}, ${expected_lock}"
}

liquibase_log_has_error() {
  local log_file="$1"

  grep -Eiq \
    "^(ERROR:|An error has occurred:|Processing has failed)|Option not recognized|Unexpected token|can not be used for Liquibase" \
    "${log_file}"
}

run_liquibase() {
  local command="$1"
  local run_stamp
  local log_dir
  local log_file
  local runtime_properties
  local sqlcl_rc

  run_stamp="$(date +%Y%m%d_%H%M%S)"
  log_dir="${LOG_ROOT}/${run_stamp}"
  mkdir -p "${log_dir}"
  log_file="${log_dir}/${MODE}.log"
  runtime_properties="${log_dir}/liquibase-core-runtime.properties"
  write_runtime_properties "${runtime_properties}"

  # The wrapper owns operational policy and logging; SQLcl is used only as the
  # Liquibase command host. Credentials are read from ORACLE_PWD inside the
  # container and are not printed to the log.
  log "Running Liquibase ${command}; log=${log_file}"
  sqlcl_rc=0
  {
    printf 'set echo off\n'
    printf 'set sqlblanklines on\n'
    printf 'whenever sqlerror exit sql.sqlcode\n'
    printf 'connect %s/"%s"@//127.0.0.1:1521/%s\n' "${LIQUIBASE_DB_USER}" "${ORACLE_PWD}" "${ORACLE_PDB}"
    printf 'set echo on\n'
    printf 'liquibase %s -defaults-file %s -changelog-file %s -search-path %s\n' \
      "${command}" "${runtime_properties}" "${CHANGELOG_FILE}" "${LIQUIBASE_SEARCH_PATH}"
    printf 'exit\n'
  } | "${SQLCL_HOME}/bin/sql" -S /nolog >"${log_file}" 2>&1 || sqlcl_rc=$?

  if [[ ${sqlcl_rc} -ne 0 ]]; then
    log "Liquibase ${command} failed with exit ${sqlcl_rc}. See ${log_file}" >&2
    return "${sqlcl_rc}"
  fi
  if liquibase_log_has_error "${log_file}"; then
    log "Liquibase ${command} reported an error. See ${log_file}" >&2
    return 1
  fi

  if [[ "${command}" == "update" || "${command}" == "changelogSync" ]]; then
    verify_tracking_tables "${runtime_properties}" "${log_dir}"
  fi

  log "Liquibase ${command} completed. See ${log_file}"
}

validate_existing_core_baseline() {
  local run_stamp
  local log_dir
  local validation_log
  local missing_count

  run_stamp="$(date +%Y%m%d_%H%M%S)"
  log_dir="${LOG_ROOT}/${run_stamp}"
  validation_log="${log_dir}/existing-core-baseline.log"
  mkdir -p "${log_dir}"

  log "Validating representative existing core objects before changelogSync; log=${validation_log}"
  {
    printf 'set echo off\n'
    printf 'set heading off feedback off pagesize 0 verify off trimspool on\n'
    printf 'whenever sqlerror exit sql.sqlcode\n'
    printf 'connect %s/"%s"@//127.0.0.1:1521/%s\n' "${LIQUIBASE_DB_USER}" "${ORACLE_PWD}" "${ORACLE_PDB}"
    cat <<'SQL'
with expected(owner, object_name, object_type) as (
  select 'ORAC_CORE', 'USERS', 'TABLE' from dual union all
  select 'ORAC_CORE', 'MESSAGES', 'TABLE' from dual union all
  select 'ORAC_API', 'USERS_V', 'VIEW' from dual union all
  select 'ORAC_API', 'USERS_TAPI', 'PACKAGE' from dual union all
  select 'ORAC_API', 'USERS_TAPI', 'PACKAGE BODY' from dual union all
  select 'ORAC_CODE', 'PLUGIN_REGISTRY_API', 'PACKAGE' from dual union all
  select 'ORAC_CODE', 'PLUGIN_REGISTRY_API', 'PACKAGE BODY' from dual union all
  select 'ORAC_APX_PUB', 'USERS', 'SYNONYM' from dual union all
  select 'ORAC', 'USERS', 'SYNONYM' from dual
)
select 'MISSING ' || expected.owner || '.' || expected.object_name || ' ' || expected.object_type
  from expected
 where not exists (
         select 1
           from all_objects obj
          where obj.owner = expected.owner
            and obj.object_name = expected.object_name
            and obj.object_type = expected.object_type
       )
 order by 1;
select 'INVALID ' || owner || '.' || object_name || ' ' || object_type
  from all_objects
 where owner in ('ORAC_CORE', 'ORAC_API', 'ORAC_CODE', 'ORAC_APX_PUB', 'ORAC')
   and status <> 'VALID'
 order by 1;
SQL
    printf 'exit\n'
  } | "${SQLCL_HOME}/bin/sql" -S /nolog >"${validation_log}" 2>&1

  missing_count="$(grep -Ec '^(MISSING|INVALID) ' "${validation_log}" || true)"
  if [[ "${missing_count}" != "0" ]]; then
    log "Existing core baseline validation failed before changelogSync. See ${validation_log}" >&2
    return 1
  fi
}

run_tracking_probe_command() {
  local command="$1"
  local probe_dir="$2"
  local properties_file="$3"
  local changelog_file="$4"
  local log_file="$5"
  local sqlcl_rc

  sqlcl_rc=0
  {
    printf 'set echo off\n'
    printf 'set sqlblanklines on\n'
    printf 'whenever sqlerror exit sql.sqlcode\n'
    printf 'connect %s/"%s"@//127.0.0.1:1521/%s\n' "${LIQUIBASE_DB_USER}" "${ORACLE_PWD}" "${ORACLE_PDB}"
    printf 'set echo on\n'
    printf 'liquibase %s -defaults-file %s -changelog-file %s -search-path %s\n' \
      "${command}" "${properties_file}" "${changelog_file}" "${probe_dir}"
    printf 'exit\n'
  } | "${SQLCL_HOME}/bin/sql" -S /nolog >"${log_file}" 2>&1 || sqlcl_rc=$?

  if [[ ${sqlcl_rc} -ne 0 ]]; then
    log "Liquibase tracking probe ${command} failed with exit ${sqlcl_rc}. See ${log_file}" >&2
    return "${sqlcl_rc}"
  fi
  if liquibase_log_has_error "${log_file}"; then
    log "Liquibase tracking probe ${command} reported an error. See ${log_file}" >&2
    return 1
  fi
}

run_tracking_probe() {
  local run_stamp
  local log_dir
  local probe_dir
  local probe_id
  local probe_table
  local probe_changelog
  local probe_properties

  run_stamp="$(date +%Y%m%d_%H%M%S)"
  log_dir="${LOG_ROOT}/${run_stamp}"
  probe_dir="${log_dir}/tracking-probe"
  probe_id="${run_stamp//_/}"
  probe_table="system.orac_lqb_probe_${probe_id}"
  probe_changelog="${probe_dir}/trackingProbe.sql"
  probe_properties="${probe_dir}/liquibase-core-probe.properties"
  mkdir -p "${probe_dir}"

  grep -Ev '^(liquibase\.command\.(contextFilter|labelFilter)|searchPath|changeLogFile)=' \
    "${PROPERTIES_FILE}" >"${probe_properties}" || true
  {
    printf 'changeLogFile=trackingProbe.sql\n'
    printf 'liquibase.command.contextFilter=probe\n'
    printf 'liquibase.command.labelFilter=probe\n'
    printf 'searchPath=%s\n' "${probe_dir}"
  } >>"${probe_properties}"

  cat >"${probe_changelog}" <<SQL
--liquibase formatted sql
--changeset clive:tracking_probe_${probe_id}_create context:probe labels:probe
create table ${probe_table} (probe_id number)
--rollback drop table ${probe_table}

--changeset clive:tracking_probe_${probe_id}_drop context:probe labels:probe
drop table ${probe_table}
--rollback create table ${probe_table} (probe_id number)
SQL

  log "Running Liquibase tracking probe; log=${log_dir}"
  run_tracking_probe_command "validate" "${probe_dir}" "${probe_properties}" "trackingProbe.sql" "${log_dir}/probe-validate.log"
  run_tracking_probe_command "update-sql" "${probe_dir}" "${probe_properties}" "trackingProbe.sql" "${log_dir}/probe-update-sql.log"
  run_tracking_probe_command "update" "${probe_dir}" "${probe_properties}" "trackingProbe.sql" "${log_dir}/probe-update.log"
  verify_tracking_tables "${probe_properties}" "${log_dir}"
  log "Liquibase tracking probe completed. See ${log_dir}"
}

parse_args "$@"
validate_environment

case "${MODE}" in
  probe-tracking) run_tracking_probe ;;
  validate) run_liquibase "validate" ;;
  update-sql) run_liquibase "update-sql" ;;
  update) run_liquibase "update" ;;
  changelog-sync)
    validate_existing_core_baseline
    run_liquibase "changelogSync"
    ;;
  *) fail "Unsupported mode: ${MODE}" ;;
esac
