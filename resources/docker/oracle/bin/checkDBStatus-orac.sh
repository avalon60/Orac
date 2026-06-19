#!/usr/bin/env bash
# Author: Clive Bostock
# Date: 20 Jun 2026
# Description: Orac-aware Oracle container health check wrapper.

set -uo pipefail

ORACLE_BASE=${ORACLE_BASE:-/opt/oracle}
ORACLE_PDB=${ORACLE_PDB:-FREEPDB1}
ORAC_ORIGINAL_CHECK_DB_FILE=${ORAC_ORIGINAL_CHECK_DB_FILE:-${ORACLE_BASE}/checkDBStatus.sh}
SQLPLUS_BIN=${SQLPLUS_BIN:-sqlplus}

"${ORAC_ORIGINAL_CHECK_DB_FILE}"
original_status=$?

if [[ ${original_status} -eq 0 ]]; then
  exit 0
fi

if [[ ${original_status} -ne 5 ]]; then
  exit "${original_status}"
fi

readiness_output=$(
  "${SQLPLUS_BIN}" -L -s / as sysdba <<SQL
set heading off feedback off pagesize 0 verify off echo off
whenever sqlerror exit failure rollback
select i.status || '|' ||
       d.database_role || '|' ||
       coalesce((
         select p.open_mode
           from v\$pdbs p
          where p.name = upper('${ORACLE_PDB}')
       ), 'MISSING')
  from v\$instance i
 cross join v\$database d;
exit
SQL
)
readiness_status=$?

if [[ ${readiness_status} -ne 0 ]]; then
  exit "${original_status}"
fi

readiness_output="$(
  tr -d '\r' <<<"${readiness_output}" |
    awk 'NF {print; exit}' |
    sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
)"

if [[ "${readiness_output}" == "OPEN|PRIMARY|READ WRITE" ]]; then
  echo "ORAC_DB_HEALTH_OK: ${ORACLE_PDB} is READ WRITE; ignoring mounted PDB\$SEED."
  exit 0
fi

echo "ORAC_DB_HEALTH_FAILED: expected OPEN|PRIMARY|READ WRITE for ${ORACLE_PDB}, got '${readiness_output}'."
exit "${original_status}"
