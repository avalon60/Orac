#!/usr/bin/env bash
# Author: Clive Bostock
# Date: 24-Jun-2026
# Description: Enforces early Orac Oracle database foundation settings.
# Purpose: Ensure the CDB is NOARCHIVELOG and the target PDB uses extended strings.
# Usage: sourced by the Oracle container setup runner during database creation.

PROG="Orac: 005-orac-db-foundation.sh"

timestamp() {
  date +"%Y-%m-%d %H:%M:%S"
}

run_sqlplus() {
  sqlplus -L -s / as sysdba
}

validate_oracle_identifier() {
  local identifier="$1"

  if [[ ! "${identifier}" =~ ^[A-Za-z][A-Za-z0-9_$#]*$ ]]; then
    echo "ERROR: Invalid Oracle identifier: ${identifier}"
    return 1
  fi
}

get_cdb_log_mode() {
  run_sqlplus <<SQL
set heading off feedback off pagesize 0 verify off echo off
whenever sqlerror exit failure rollback

select upper(log_mode)
from v\$database;

exit
SQL
}

get_pdb_max_string_size() {
  local oracle_pdb="$1"

  run_sqlplus <<SQL
set heading off feedback off pagesize 0 verify off echo off
whenever sqlerror exit failure rollback

alter session set container=${oracle_pdb};

select lower(value)
from v\$parameter
where name = 'max_string_size';

exit
SQL
}

enable_noarchivelog() {
  echo "[$(timestamp)] ${PROG} Switching CDB to NOARCHIVELOG mode."

  run_sqlplus <<SQL
set echo on
set feedback on
set timing on
whenever sqlerror exit failure rollback

shutdown immediate;
startup mount;
alter database noarchivelog;
alter database open;
alter pluggable database all open;
alter pluggable database all save state;

exit
SQL
}

enable_extended_strings() {
  local oracle_pdb="$1"
  local needs_noarchivelog="$2"
  local noarchivelog_sql=""

  if [[ "${needs_noarchivelog}" == "1" ]]; then
    noarchivelog_sql="alter database noarchivelog;"
  fi

  echo "[$(timestamp)] ${PROG} Enabling max_string_size=EXTENDED for ${oracle_pdb}."

  run_sqlplus <<SQL
set echo on
set feedback on
set serveroutput on
set timing on
whenever sqlerror exit failure rollback

alter system set max_string_size = extended scope = spfile;

shutdown immediate;
startup mount;
${noarchivelog_sql}
alter database open upgrade;

alter pluggable database ${oracle_pdb} open upgrade;

alter session set container=${oracle_pdb};

alter system set max_string_size = extended scope = both;

@?/rdbms/admin/utl32k.sql

@?/rdbms/admin/utlrp.sql

alter session set container = cdb\$root;

shutdown immediate;
startup;

declare
  l_open_mode v\$pdbs.open_mode%type;
begin
  select open_mode
  into l_open_mode
  from v\$pdbs
  where name = upper('${oracle_pdb}');

  if l_open_mode <> 'READ WRITE' then
    execute immediate 'alter pluggable database ${oracle_pdb} open';
  end if;
end;
/

alter session set container=${oracle_pdb};

show parameter max_string_size

exit
SQL
}

orac_db_foundation() {
  set -uo pipefail

  local oracle_pdb="${ORACLE_PDB:-FREEPDB1}"
  local current_log_mode
  local current_max_string_size
  local needs_noarchivelog=0
  local needs_extended_strings=0

  validate_oracle_identifier "${oracle_pdb}" || return 1

  echo "[$(timestamp)] ${PROG} Checking CDB log mode."

  current_log_mode="$(
    get_cdb_log_mode | tr -d '[:space:]' | tr '[:lower:]' '[:upper:]'
  )"

  if [[ "${current_log_mode}" == "NOARCHIVELOG" ]]; then
    echo "[$(timestamp)] ${PROG} CDB log mode is already NOARCHIVELOG."
  else
    needs_noarchivelog=1
    echo "[$(timestamp)] ${PROG} Current CDB log mode is: ${current_log_mode:-UNKNOWN}"
  fi

  echo "[$(timestamp)] ${PROG} Checking max_string_size for ${oracle_pdb}."

  current_max_string_size="$(get_pdb_max_string_size "${oracle_pdb}" | tr -d '[:space:]')"

  if [[ "${current_max_string_size}" == "extended" ]]; then
    echo "[$(timestamp)] ${PROG} max_string_size is already EXTENDED for ${oracle_pdb}."
  else
    needs_extended_strings=1
    echo "[$(timestamp)] ${PROG} Current max_string_size is: ${current_max_string_size:-UNKNOWN}"
  fi

  if [[ ${needs_noarchivelog} -eq 0 && ${needs_extended_strings} -eq 0 ]]; then
    echo "[$(timestamp)] ${PROG} Database foundation settings are already correct."
    return 0
  fi

  if [[ ${needs_extended_strings} -eq 1 ]]; then
    enable_extended_strings "${oracle_pdb}" "${needs_noarchivelog}" || return 1
  elif [[ ${needs_noarchivelog} -eq 1 ]]; then
    enable_noarchivelog || return 1
  fi

  current_log_mode="$(
    get_cdb_log_mode | tr -d '[:space:]' | tr '[:lower:]' '[:upper:]'
  )"

  if [[ "${current_log_mode}" != "NOARCHIVELOG" ]]; then
    echo "ERROR: CDB log mode was not set to NOARCHIVELOG."
    echo "Current value: ${current_log_mode:-UNKNOWN}"
    return 1
  fi

  current_max_string_size="$(get_pdb_max_string_size "${oracle_pdb}" | tr -d '[:space:]')"

  if [[ "${current_max_string_size}" != "extended" ]]; then
    echo "ERROR: max_string_size was not set to EXTENDED for ${oracle_pdb}."
    echo "Current value: ${current_max_string_size:-UNKNOWN}"
    return 1
  fi

  echo "[$(timestamp)] ${PROG} Database foundation settings are correct."
}

(
  orac_db_foundation
)
foundation_status=$?

if [[ ${foundation_status} -ne 0 ]]; then
  return "${foundation_status}" 2>/dev/null || false
fi

return 0 2>/dev/null || true
