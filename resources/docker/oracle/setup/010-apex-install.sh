#!/usr/bin/env bash
# Author: Clive Bostock
#   Date: 9 Aug 2025
#
# Orac script to install APEX on container setup.
#
# Oracle's runUserScripts.sh sources setup shell scripts. Keep this file
# source-safe: risky installer work runs in a child shell and this script returns
# control to the Oracle setup runner.
#
PROG="Orac: 010-apex-install.sh"

timestamp() { date +"%Y-%m-%d %H:%M:%S"; }

orac_apex_install() {
  set -uo pipefail

  export APEX_HOME=${APEX_HOME:-/home/oracle/orac/setup/apex/apex}
  export ORACLE_SID=${ORACLE_SID:-FREE}
  export ORACLE_PDB=${ORACLE_PDB:-FREEPDB1}
  export ORAC_HOME=${ORAC_HOME:-/home/oracle/orac}
  export ORACLE_BASE=${ORACLE_BASE:-/opt/oracle}

  local cdn=" https://static.oracle.com/cdn/apex/${APEX_VERSION}.0/"
  local validation_output

  echo "[$(timestamp)] ${PROG} Started"
  echo "${PROG} Launching sqlplus; installing APEX..."

  cd "${APEX_HOME}" || return 1

  sqlplus / as sysdba <<EOF
alter session set container=${ORACLE_PDB};

-- Switch off password expiry
alter profile DEFAULT limit password_life_time UNLIMITED;

-- Install APEX in the SID.
alter session set container = ${ORACLE_PDB:-FREE};
-- @apxremov.sql

@apexins.sql SYSAUX SYSAUX TEMP /i/

-- Set the APEX admin password.
begin
    apex_util.set_security_group_id( 10 );
    
    apex_util.create_user(
        p_user_name                    => 'ADMIN',
        p_email_address                => 'me@example.com',
        p_web_password                 => '${ORACLE_PWD}',
        p_developer_privs              => 'ADMIN',
        p_change_password_on_first_use => 'N' );
    apex_util.set_security_group_id( null );
    commit;
end;
/

-- Create the APEX_LISTENER and APEX_REST_PUBLIC_USER users
@apex_rest_config.sql ${ORACLE_PWD} ${ORACLE_PWD}

-- Unlock the accounts.
alter user ANONYMOUS account unlock;
alter user APEX_REST_PUBLIC_USER  account unlock;
alter user APEX_PUBLIC_USER account unlock;
alter user APEX_LISTENER account unlock;
@${APEX_HOME}/utilities/reset_image_prefix_core.sql ${cdn} x
@${ORACLE_BASE}/scripts/setup/011-apex-check.sql
EOF

  validation_output=$(sqlplus -L -s / as sysdba <<SQL
set heading off feedback off pagesize 0 verify off echo off
whenever sqlerror exit failure rollback
alter session set container=${ORACLE_PDB};
select status from dba_registry where comp_id = 'APEX';
exit
SQL
)

  if ! grep -Eq '(^|[[:space:]])VALID([[:space:]]|$)' <<<"${validation_output}"; then
    echo "${PROG}: APEX validation failed. Registry status output:"
    echo "${validation_output}"
    return 1
  fi

  echo "ORAC_APEX_SETUP_COMPLETE: APEX registry component is VALID in ${ORACLE_PDB}."
  echo "[$(timestamp)] ${PROG}: Done."
}

(
  orac_apex_install
)
apex_status=$?

if [[ ${apex_status} -ne 0 ]]; then
  echo "ORAC_APEX_SETUP_FAILED: ${PROG} failed with status ${apex_status}."
  return "${apex_status}" 2>/dev/null || false
fi

return 0 2>/dev/null || true
