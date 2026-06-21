#!/usr/bin/env bash
# Author: Clive Bostock
# Date: 21-Jun-2026
# Description: Run on-demand core Orac SQLcl Liquibase database deltas.
#
# Purpose: Validate, preview, or apply core Orac database Liquibase changes.
# Usage: deploy-orac-db.sh [--validate|--update-sql|--update] [--contexts core,prod] [--labels core]
set -euo pipefail

PROG="Orac: deploy-orac-db.sh"
ORAC_HOME="${ORAC_HOME:-/home/oracle/orac}"
ORACLE_PDB="${ORACLE_PDB:-FREEPDB1}"
SQLCL_HOME="${SQLCL_HOME:-${ORAC_HOME}/setup/sqlcl/sqlcl}"
LIQUIBASE_HOME="${LIQUIBASE_HOME:-${ORAC_HOME}/liquibase}"
PROPERTIES_FILE="${PROPERTIES_FILE:-${LIQUIBASE_HOME}/liquibase-core.properties}"
CHANGELOG_FILE="${CHANGELOG_FILE:-changelogs/core/oracController.xml}"
LOG_ROOT="${LOG_ROOT:-${ORAC_HOME}/logs/liquibase/core}"
LIQUIBASE_DB_USER="${LIQUIBASE_DB_USER:-SYSTEM}"
MODE="update"
CONTEXTS="${CONTEXTS:-core,prod}"
LABELS="${LABELS:-core}"

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
Usage: deploy-orac-db.sh [--validate|--update-sql|--update] [--contexts LIST] [--labels LIST]

Run on-demand core Orac Liquibase deployment from inside the orac-db container.

Options:
  --validate       Validate the configured changelog only.
  --update-sql     Print SQL that would be executed.
  --update         Apply pending changes. This is the default.
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
      --update-sql)
        MODE="update-sql"
        shift
        ;;
      --update)
        MODE="update"
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
    printf '%s/%s\n' "${LIQUIBASE_HOME}" "${CHANGELOG_FILE}"
  fi
}

write_runtime_properties() {
  local runtime_properties="$1"

  grep -Ev '^(liquibase\.command\.(contextFilter|labelFilter)|searchPath)=' \
    "${PROPERTIES_FILE}" >"${runtime_properties}" || true
  {
    printf 'liquibase.command.contextFilter=%s\n' "${CONTEXTS}"
    printf 'liquibase.command.labelFilter=%s\n' "${LABELS}"
    printf 'searchPath=%s\n' "${LIQUIBASE_HOME}"
  } >>"${runtime_properties}"
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
      "${command}" "${runtime_properties}" "${CHANGELOG_FILE}" "${LIQUIBASE_HOME}"
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

  log "Liquibase ${command} completed. See ${log_file}"
}

parse_args "$@"
validate_environment

case "${MODE}" in
  validate) run_liquibase "validate" ;;
  update-sql) run_liquibase "update-sql" ;;
  update) run_liquibase "update" ;;
  *) fail "Unsupported mode: ${MODE}" ;;
esac
