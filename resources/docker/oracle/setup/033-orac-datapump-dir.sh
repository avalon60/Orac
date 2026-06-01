#!/usr/bin/env bash
################################################################################
#
# Author: Clive Bostock
# Date: 20-May-2026
# Purpose: Create the Orac Data Pump filesystem and database directory object.
# Usage: Executed by the Oracle container setup lifecycle.
#
################################################################################

PROG="Orac: 033-orac-datapump-dir.sh"

timestamp() {
  date +"%Y-%m-%d %H:%M:%S"
}

validate_identifier() {
  local value="$1"
  local label="$2"

  if [[ ! "$value" =~ ^[A-Za-z][A-Za-z0-9_]*$ ]]; then
    echo "[$(timestamp)] ${PROG} Invalid ${label}: ${value}"
    return 1
  fi
}

validate_datapump_path() {
  if [[ "${ORAC_DATAPUMP_PATH}" != /* || "${ORAC_DATAPUMP_PATH}" == *"'"* ]]; then
    echo "[$(timestamp)] ${PROG} Invalid ORAC_DATAPUMP_PATH: ${ORAC_DATAPUMP_PATH}"
    return 1
  fi
}

orac_datapump_dir_setup() {
  set -Eeuo pipefail

  echo "[$(timestamp)] ${PROG} Started"

  export ORACLE_PDB=${ORACLE_PDB:-FREEPDB1}
  export ORAC_HOME=${ORAC_HOME:-/home/oracle/orac}
  export ORAC_DATAPUMP_DIR=${ORAC_DATAPUMP_DIR:-ORAC_DATAPUMP_DIR}
  export ORAC_DATAPUMP_PATH=${ORAC_DATAPUMP_PATH:-${ORAC_HOME}/datapump}

  validate_identifier "${ORACLE_PDB}" "ORACLE_PDB"
  validate_identifier "${ORAC_DATAPUMP_DIR}" "ORAC_DATAPUMP_DIR"
  validate_datapump_path

  mkdir -p "${ORAC_DATAPUMP_PATH}"
  chmod 750 "${ORAC_DATAPUMP_PATH}"

  sqlplus -L -s / as sysdba <<SQL
whenever sqlerror exit sql.sqlcode
alter session set container=${ORACLE_PDB};
create or replace directory ${ORAC_DATAPUMP_DIR} as '${ORAC_DATAPUMP_PATH}';
exit
SQL

  echo "[$(timestamp)] ${PROG} Data Pump directory ready: ${ORAC_DATAPUMP_DIR} -> ${ORAC_DATAPUMP_PATH}"
}

(
  orac_datapump_dir_setup
)
datapump_status=$?

if [[ ${datapump_status} -ne 0 ]]; then
  echo "ORAC_SCHEMA_SETUP_FAILED: ${PROG} failed with status ${datapump_status}."
  return "${datapump_status}" 2>/dev/null || false
fi

return 0 2>/dev/null || true
