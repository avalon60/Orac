#!/usr/bin/env bash
# Author: Clive Bostock
#   Date: 31 May 2026
#
# Emit the Orac deployment completion marker only after core DB/APEX/ORDS
# readiness checks pass.
#
PROG="Orac: 999-complete.sh"
timestamp() { date +"%Y-%m-%d %H:%M:%S"; }

orac_deployment_complete() {
  set -uo pipefail

  local oracle_pdb="${ORACLE_PDB:-FREEPDB1}"
  local orac_home="${ORAC_HOME:-/home/oracle/orac}"
  local ords_home="${orac_home}/ords"
  local ords_conf="${ords_home}/conf"
  local pdb_status
  local apex_status
  local ords_metadata_status
  local ords_config_output

  echo "[$(timestamp)] ${PROG} Validating DB/APEX/ORDS deployment."

  pdb_status=$(sqlplus -L -s / as sysdba <<SQL
set heading off feedback off pagesize 0 verify off echo off
whenever sqlerror exit failure rollback
select open_mode from v\$pdbs where name = upper('${oracle_pdb}');
exit
SQL
)
  if ! grep -Eq 'READ WRITE' <<<"${pdb_status}"; then
    echo "ORAC_DEPLOYMENT_INCOMPLETE: ${oracle_pdb} is not open read/write."
    echo "${pdb_status}"
    return 1
  fi

  apex_status=$(sqlplus -L -s / as sysdba <<SQL
set heading off feedback off pagesize 0 verify off echo off
whenever sqlerror exit failure rollback
alter session set container=${oracle_pdb};
select status from dba_registry where comp_id = 'APEX';
exit
SQL
)
  if ! grep -Eq '(^|[[:space:]])VALID([[:space:]]|$)' <<<"${apex_status}"; then
    echo "ORAC_DEPLOYMENT_INCOMPLETE: APEX registry component is not VALID."
    echo "${apex_status}"
    return 1
  fi

  if [[ ! -d "${ords_conf}" ]]; then
    echo "ORAC_DEPLOYMENT_INCOMPLETE: missing ORDS config directory: ${ords_conf}"
    return 1
  fi

  ords_metadata_status=$(sqlplus -L -s / as sysdba <<SQL
set heading off feedback off pagesize 0 verify off echo off
whenever sqlerror exit failure rollback
alter session set container=${oracle_pdb};
select case
         when exists (
                select 1
                  from dba_objects
                 where owner = 'ORDS_METADATA'
                   and object_name = 'ORDS'
                   and object_type = 'PACKAGE'
                   and status = 'VALID'
              )
          and not exists (
                select 1
                  from dba_objects
                 where owner = 'ORDS_METADATA'
                   and status <> 'VALID'
              )
         then 'VALID'
         else 'INVALID'
       end
  from dual;
exit
SQL
)
  if ! grep -Eq '(^|[[:space:]])VALID([[:space:]]|$)' <<<"${ords_metadata_status}"; then
    echo "ORAC_DEPLOYMENT_INCOMPLETE: ORDS metadata objects are not VALID."
    echo "${ords_metadata_status}"
    return 1
  fi

  ords_config_output=$("${ords_home}/bin/ords" --config "${ords_conf}" config list 2>&1)
  if grep -Fq "does not contain database pool default" <<<"${ords_config_output}"; then
    echo "ORAC_DEPLOYMENT_INCOMPLETE: ORDS default database pool is missing."
    echo "${ords_config_output}"
    return 1
  fi

}

(
  orac_deployment_complete
)
complete_status=$?

if [[ ${complete_status} -ne 0 ]]; then
  return "${complete_status}" 2>/dev/null || false
fi

return 0 2>/dev/null || true
