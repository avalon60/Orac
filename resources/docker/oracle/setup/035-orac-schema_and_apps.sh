#!/usr/bin/env bash
# Author: Clive Bostock
# Date: 21 Mar 2026
# Description: Execute DDL/DML scripts in ordered directories via SQL*Plus.
#              Expects schema bundle directories beneath ${BASE_DIR}, with each
#              bundle containing the ordered subdirectories in DIR_ORDER.
#              Stops on first error by default; logs each file's output.

# --- Config (override via environment) ---------------------------------------
PROG="Orac: 035-orac-schema_and_apps.sh"
export ORACLE_SID="${ORACLE_SID:-FREE}"
export ORACLE_PDB="${ORACLE_PDB:-FREEPDB1}"
export ORAC_HOME="${ORAC_HOME:-/home/oracle/orac}"

timestamp() {
  date +"%Y-%m-%d %H:%M:%S"
}

echo "[$(timestamp)] ${PROG} Started"

BASE_DIR="${BASE_DIR:-${ORAC_HOME}/schema}"
SQLPLUS_CONN="${SQLPLUS_CONN:-/ as sysdba}"  # e.g. "user/pass@service" or "/ as sysdba"
LOG_ROOT="${LOG_ROOT:-$BASE_DIR/_logs}"
STOP_ON_ERROR="${STOP_ON_ERROR:-1}"          # 1 = stop on first error, 0 = continue
BUNDLE_ORDER=(
  orac_ha
  orac_core
  orac_api
  orac_code
  orac_apx_pub
  orac
)

# Ordered execution list (directories under each schema bundle)
DIR_ORDER=(
  pre_install
  privilege
  role
  sequence
  table
  view
  index
  constraint_pk
  constraint_uc
  constraint_other
  constraint_fk
  type_spec
  package_spec
  materialized_view
  type_body
  package_body
  trigger
  context
  procedure
  function
  seed_data
  schedule
  job
  synonym
  grant
  rest_module
  comment
  post_install
  orac_ws
  orac_apps
)

# --- Setup -------------------------------------------------------------------
RUN_STAMP="$(date +%Y%m%d_%H%M%S)"
LOG_DIR="$LOG_ROOT/$RUN_STAMP"
mkdir -p "$LOG_DIR"

shopt -s nullglob

echo "== $(timestamp) :: DDL runner starting"
echo "   BASE_DIR     : $BASE_DIR"
echo "   SQLPLUS_CONN : $SQLPLUS_CONN"
echo "   LOG_DIR      : $LOG_DIR"
echo "   STOP_ON_ERROR: $STOP_ON_ERROR"
echo

overall_rc=0
ran_any=0

# --- Validation --------------------------------------------------------------
if [[ ! -d "$BASE_DIR" ]]; then
  echo "!! $(timestamp) :: BASE_DIR does not exist or is not a directory: $BASE_DIR"
  exit 1
fi

# --- Runner ------------------------------------------------------------------
run_sql_file() {
  local file="$1"
  local bundle="$2"
  local dir="$3"
  local base
  local logf

  base="$(basename "$file" .sql)"
  logf="$LOG_DIR/${bundle}__${dir}__${base}.log"

  echo "-> $(timestamp) :: Running [$bundle/$dir]: $file"
  (
    set -Eeuo pipefail
    sqlplus -l "$SQLPLUS_CONN" <<SQLPLUS 2>&1 | tee "$logf"
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
    prompt @@@ STARTING: $file @@@
    @$file
    prompt @@@ FINISHED: $file @@@
    exit
SQLPLUS
  )
}

process_bundle_dir() {
  local bundle_dir="$1"
  local bundle_name="$2"
  local dirpath
  local files
  local dir
  local file

  echo "== $(timestamp) :: Processing schema bundle: $bundle_name"

  for dir in "${DIR_ORDER[@]}"; do
    dirpath="$bundle_dir/$dir"

    if [[ ! -d "$dirpath" ]]; then
      echo "-- $(timestamp) :: Skipping missing directory: $bundle_name/$dir"
      continue
    fi

    files=( "$dirpath"/*.sql )
    if (( ${#files[@]} == 0 )); then
      echo "-- $(timestamp) :: No .sql files in: $bundle_name/$dir"
      continue
    fi

    echo "== $(timestamp) :: Processing directory: $bundle_name/$dir"
    for file in "${files[@]}"; do
      if run_sql_file "$file" "$bundle_name" "$dir"; then
        ran_any=1
      else
        rc=$?
        overall_rc=$rc
        echo "!! $(timestamp) :: ERROR ($rc) while running: $file"
        if [[ "$STOP_ON_ERROR" == "1" ]]; then
          echo "!! Halting due to STOP_ON_ERROR=1. See logs in: $LOG_DIR"
          echo
          exit "$overall_rc"
        fi
      fi
    done
    echo
  done
}

# --- Main loop ---------------------------------------------------------------
declare -A seen_bundles=()

for bundle_name in "${BUNDLE_ORDER[@]}"; do
  bundle_dir="$BASE_DIR/$bundle_name"
  if [[ -d "$bundle_dir" ]]; then
    process_bundle_dir "$bundle_dir" "$bundle_name"
    seen_bundles["$bundle_name"]=1
  else
    echo "-- $(timestamp) :: Skipping missing schema bundle: $bundle_name"
  fi
done

for bundle_dir in "$BASE_DIR"/*; do
  [[ -d "$bundle_dir" ]] || continue

  bundle_name="$(basename "$bundle_dir")"
  if [[ "$bundle_name" == "_logs" || -n "${seen_bundles[$bundle_name]:-}" ]]; then
    continue
  fi

  process_bundle_dir "$bundle_dir" "$bundle_name"
done

if [[ "$ran_any" == "0" ]]; then
  echo "!! No SQL files executed. Check BASE_DIR: $BASE_DIR"
fi

echo "== $(timestamp) :: DDL runner finished. Logs: $LOG_DIR"
echo "[$(timestamp)] ${PROG} Done"
