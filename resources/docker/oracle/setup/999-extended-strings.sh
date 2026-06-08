#!/usr/bin/env bash
# Author: Clive Bostock
# Date: 08 June 2026
# Description: Enables extended string support for the Orac Oracle database PDB.

PROG="Orac: 020-enable-extended-strings.sh"

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

enable_extended_strings() {
  local oracle_pdb="$1"

  echo "[$(timestamp)] ${PROG} Enabling max_string_size=EXTENDED for ${oracle_pdb}."

  run_sqlplus <<SQL
set echo on
set feedback on
set serveroutput on
set timing on
whenever sqlerror exit failure rollback

alter system set max_string_size = extended scope = spfile;

shutdown immediate;
startup upgrade;

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

orac_enable_extended_strings() {
  set -uo pipefail

  local oracle_pdb="${ORACLE_PDB:-FREEPDB1}"
  local current_max_string_size

  validate_oracle_identifier "${oracle_pdb}" || return 1

  echo "[$(timestamp)] ${PROG} Checking max_string_size for ${oracle_pdb}."

  current_max_string_size="$(get_pdb_max_string_size "${oracle_pdb}" | tr -d '[:space:]')"

  if [[ "${current_max_string_size}" == "extended" ]]; then
    echo "[$(timestamp)] ${PROG} max_string_size is already EXTENDED for ${oracle_pdb}."
    return 0
  fi

  echo "[$(timestamp)] ${PROG} Current max_string_size is: ${current_max_string_size:-UNKNOWN}"

  enable_extended_strings "${oracle_pdb}" || return 1

  current_max_string_size="$(get_pdb_max_string_size "${oracle_pdb}" | tr -d '[:space:]')"

  if [[ "${current_max_string_size}" != "extended" ]]; then
    echo "ERROR: max_string_size was not set to EXTENDED for ${oracle_pdb}."
    echo "Current value: ${current_max_string_size:-UNKNOWN}"
    return 1
  fi

  echo "[$(timestamp)] ${PROG} Extended strings enabled successfully for ${oracle_pdb}."
}

(
  orac_enable_extended_strings
)
enable_status=$?

if [[ ${enable_status} -ne 0 ]]; then
  return "${enable_status}" 2>/dev/null || exit "${enable_status}"
fi

echo "==================  ORAC deployment complete =================="
return 0 2>/dev/null || exit 0
