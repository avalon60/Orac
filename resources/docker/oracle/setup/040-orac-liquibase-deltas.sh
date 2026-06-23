#!/usr/bin/env bash
# Author: Clive Bostock
# Date: 21-Jun-2026
# Description: Run first-setup Orac Liquibase database changes after bootstrap.
#
# Purpose: Probe, validate, and apply core Orac Liquibase changes during first container setup.
# Usage: Sourced by Oracle container setup; no direct arguments are required.

PROG="Orac: 040-orac-liquibase-deltas.sh"

timestamp() {
  date +"%Y-%m-%d %H:%M:%S"
}

orac_liquibase_delta_setup() {
  set -Eeuo pipefail

  local orac_home="${ORAC_HOME:-/home/oracle/orac}"
  local oracle_pdb="${ORACLE_PDB:-FREEPDB1}"
  local sqlcl_home="${SQLCL_HOME:-${orac_home}/setup/sqlcl/sqlcl}"
  local liquibase_home="${LIQUIBASE_HOME:-${orac_home}/liquibase}"
  local liquibase_search_path="${LIQUIBASE_SEARCH_PATH:-${orac_home}/schema}"
  local setup_log_root="${LIQUIBASE_SETUP_LOG_ROOT:-${orac_home}/logs/liquibase/setup}"
  local run_stamp
  local log_dir
  local log_file
  local deploy_script
  local sqlcl_bin
  local properties_file
  local changelog_file

  run_stamp="$(date +%Y%m%d_%H%M%S)"
  log_dir="${setup_log_root}/${run_stamp}"
  log_file="${log_dir}/040-orac-liquibase-deltas.log"
  deploy_script="${orac_home}/bin/deploy-orac-db.sh"
  sqlcl_bin="${sqlcl_home}/bin/sql"
  properties_file="${liquibase_home}/liquibase-core.properties"
  changelog_file="${liquibase_search_path}/productController.xml"

  mkdir -p "${log_dir}"

  {
    printf '[%s] %s Started\n' "$(timestamp)" "${PROG}"
    printf '%s SQLcl home: %s\n' "${PROG}" "${sqlcl_home}"
    printf '%s Liquibase home: %s\n' "${PROG}" "${liquibase_home}"
    printf '%s Liquibase search path: %s\n' "${PROG}" "${liquibase_search_path}"
    printf '%s Setup log: %s\n' "${PROG}" "${log_file}"

    # This setup stage intentionally runs after account/bootstrap setup. Core
    # Orac schema objects are owned by Liquibase, while user creation remains in
    # the dedicated bootstrap scripts.
    [[ -n "${ORACLE_PWD:-}" ]] || {
      printf '%s ERROR: ORACLE_PWD is not set.\n' "${PROG}" >&2
      return 1
    }
    [[ -x "${sqlcl_bin}" ]] || {
      printf '%s ERROR: SQLcl executable is missing or not executable: %s\n' "${PROG}" "${sqlcl_bin}" >&2
      return 1
    }
    [[ -f "${properties_file}" ]] || {
      printf '%s ERROR: Liquibase properties file is missing: %s\n' "${PROG}" "${properties_file}" >&2
      return 1
    }
    [[ -f "${changelog_file}" ]] || {
      printf '%s ERROR: Liquibase controller is missing: %s\n' "${PROG}" "${changelog_file}" >&2
      return 1
    }
    [[ -x "${deploy_script}" ]] || {
      printf '%s ERROR: Core Liquibase deploy wrapper is missing or not executable: %s\n' "${PROG}" "${deploy_script}" >&2
      return 1
    }

    printf '%s Verifying SQLcl availability.\n' "${PROG}"
    "${sqlcl_bin}" -V

    printf '%s Probing SQLcl Liquibase tracking table behaviour.\n' "${PROG}"
    LOG_ROOT="${log_dir}/core" \
      ORAC_HOME="${orac_home}" \
      ORACLE_PDB="${oracle_pdb}" \
      SQLCL_HOME="${sqlcl_home}" \
      LIQUIBASE_HOME="${liquibase_home}" \
      LIQUIBASE_SEARCH_PATH="${liquibase_search_path}" \
      "${deploy_script}" --probe-tracking --contexts core,prod --labels core

    printf '%s Validating core Liquibase changelog.\n' "${PROG}"
    LOG_ROOT="${log_dir}/core" \
      ORAC_HOME="${orac_home}" \
      ORACLE_PDB="${oracle_pdb}" \
      SQLCL_HOME="${sqlcl_home}" \
      LIQUIBASE_HOME="${liquibase_home}" \
      LIQUIBASE_SEARCH_PATH="${liquibase_search_path}" \
      "${deploy_script}" --validate --contexts core,prod --labels core

    printf '%s Applying core Liquibase deltas.\n' "${PROG}"
    LOG_ROOT="${log_dir}/core" \
      ORAC_HOME="${orac_home}" \
      ORACLE_PDB="${oracle_pdb}" \
      SQLCL_HOME="${sqlcl_home}" \
      LIQUIBASE_HOME="${liquibase_home}" \
      LIQUIBASE_SEARCH_PATH="${liquibase_search_path}" \
      "${deploy_script}" --update --contexts core,prod --labels core

    printf '[%s] %s Complete\n' "$(timestamp)" "${PROG}"
  } 2>&1 | tee "${log_file}"
}

(
  orac_liquibase_delta_setup
)
liquibase_status=$?

if [[ ${liquibase_status} -ne 0 ]]; then
  echo "ORAC_LIQUIBASE_DELTA_SETUP_FAILED: ${PROG} failed with status ${liquibase_status}."
  return "${liquibase_status}" 2>/dev/null || exit "${liquibase_status}"
fi

return 0 2>/dev/null || exit 0
