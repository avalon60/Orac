#!/usr/bin/env bash
# Author: Clive Bostock
# Date: 25-Jun-2026
# Description: Import Orac APEX workspace and application exports after core database deployment.
#
# Purpose: Import SQL*Plus-owned APEX exports after Liquibase-owned database
#          objects, grants, synonyms, and parsing-schema dependencies exist.
# Usage: Sourced by Oracle container setup; no direct arguments are required.

PROG="Orac: 045-orac-apex-import.sh"
export ORACLE_SID="${ORACLE_SID:-FREE}"
export ORACLE_PDB="${ORACLE_PDB:-FREEPDB1}"
export ORAC_HOME="${ORAC_HOME:-/home/oracle/orac}"

timestamp() {
  date +"%Y-%m-%d %H:%M:%S"
}

echo "[$(timestamp)] ${PROG} Started"

APEX_BASE_DIR="${APEX_BASE_DIR:-${ORAC_HOME}/apex}"
SQLPLUS_CONN="${SQLPLUS_CONN:-/ as sysdba}"
LOG_ROOT="${LOG_ROOT:-${ORAC_HOME}/logs/apex-import}"
STOP_ON_ERROR="${STOP_ON_ERROR:-1}"
APEX_DIR_ORDER=(
  orac_ws
  orac_apps
)

RUN_STAMP="$(date +%Y%m%d_%H%M%S)"
LOG_DIR="${LOG_ROOT}/${RUN_STAMP}"
mkdir -p "${LOG_DIR}"

shopt -s nullglob

echo "== $(timestamp) :: APEX import starting"
echo "   APEX_BASE_DIR: ${APEX_BASE_DIR}"
echo "   SQLPLUS_CONN : ${SQLPLUS_CONN}"
echo "   LOG_DIR      : ${LOG_DIR}"
echo "   STOP_ON_ERROR: ${STOP_ON_ERROR}"
echo

overall_rc=0
ran_any=0

if [[ ! -d "${APEX_BASE_DIR}" ]]; then
  echo "!! $(timestamp) :: APEX_BASE_DIR does not exist or is not a directory: ${APEX_BASE_DIR}"
  return 1 2>/dev/null || exit 1
fi

run_apex_sql_file() {
  local file="$1"
  local dir="$2"
  local base
  local logf

  base="$(basename "${file}" .sql)"
  logf="${LOG_DIR}/${dir}__${base}.log"

  echo "-> $(timestamp) :: Running [apex/${dir}]: ${file}"
  (
    set -Eeuo pipefail
    sqlplus -l "${SQLPLUS_CONN}" <<SQLPLUS 2>&1 | tee "${logf}"
    alter session set container=${ORACLE_PDB};
    whenever sqlerror exit 1 rollback
    whenever oserror exit 2
    set echo on
    set termout on
    set feedback on
    set timing on
    set serveroutput on size unlimited
    set sqlblanklines on
    set define off
    prompt @@@ STARTING: ${file} @@@
    @${file}
    prompt @@@ FINISHED: ${file} @@@
    exit
SQLPLUS
  )
}

for dir in "${APEX_DIR_ORDER[@]}"; do
  dirpath="${APEX_BASE_DIR}/${dir}"

  if [[ ! -d "${dirpath}" ]]; then
    echo "-- $(timestamp) :: Skipping missing APEX directory: ${dir}"
    continue
  fi

  files=( "${dirpath}"/*.sql )
  if (( ${#files[@]} == 0 )); then
    echo "-- $(timestamp) :: No .sql files in: apex/${dir}"
    continue
  fi

  echo "== $(timestamp) :: Processing APEX directory: apex/${dir}"
  for file in "${files[@]}"; do
    if run_apex_sql_file "${file}" "${dir}"; then
      ran_any=1
    else
      rc=$?
      overall_rc=$rc
      echo "!! $(timestamp) :: ERROR (${rc}) while running: ${file}"
      if [[ "${STOP_ON_ERROR}" == "1" ]]; then
        echo "!! Halting due to STOP_ON_ERROR=1. See logs in: ${LOG_DIR}"
        echo "ORAC_APEX_IMPORT_FAILED: ${PROG} failed with status ${overall_rc}."
        return "${overall_rc}" 2>/dev/null || exit "${overall_rc}"
      fi
    fi
  done
  echo
done

if [[ "${ran_any}" == "0" ]]; then
  echo "!! No APEX SQL files executed. Check APEX_BASE_DIR: ${APEX_BASE_DIR}"
fi

echo "== $(timestamp) :: APEX import finished. Logs: ${LOG_DIR}"
echo "ORAC_APEX_IMPORT_COMPLETE: Orac APEX exports imported."
echo "[$(timestamp)] ${PROG} Done"
return "${overall_rc}" 2>/dev/null || exit "${overall_rc}"
