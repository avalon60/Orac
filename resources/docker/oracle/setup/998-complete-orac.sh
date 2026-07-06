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
  local ords_conf_persistent="${ORDS_CONF_PERSISTENT:-/opt/oracle/oradata/orac/ords/conf}"
  local pdb_status
  local apex_status
  local apex_admin_status
  local core_runtime_status
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

  apex_admin_status=$(sqlplus -L -s / as sysdba <<SQL
set heading off feedback off pagesize 0 verify off echo off
whenever sqlerror exit failure rollback
alter session set container=${oracle_pdb};
select case
         when exists (
                select 1
                  from apex_workspace_apex_users
                 where workspace_name = 'ORAC'
                   and user_name = 'ORAC_ADMIN'
              )
          and 3 = (
                select count(distinct role_static_id)
                  from apex_appl_acl_user_roles
                 where workspace = 'ORAC'
                   and application_id = 1042
                   and user_name = 'ORAC_ADMIN'
                   and role_static_id in (
                         'ADMINISTRATOR',
                         'CONTRIBUTOR',
                         'READER'
                       )
              )
         then 'VALID'
         else 'INVALID'
       end
  from dual;
exit
SQL
)
  if ! grep -Eq '(^|[[:space:]])VALID([[:space:]]|$)' <<<"${apex_admin_status}"; then
    echo "ORAC_DEPLOYMENT_INCOMPLETE: ORAC_ADMIN is not configured for APEX application 1042."
    echo "${apex_admin_status}"
    return 1
  fi

  core_runtime_status=$(sqlplus -L -s / as sysdba <<SQL
set heading off feedback off pagesize 0 verify off echo off
whenever sqlerror exit failure rollback
alter session set container=${oracle_pdb};
with required_objects as (
  select 'ORAC_CODE' owner, 'PLUGIN_REGISTRY_V' object_name, 'VIEW' object_type
    from dual
  union all
  select 'ORAC_CODE', 'PLUGIN_SERVICE_STATUS_V', 'VIEW'
    from dual
  union all
  select 'ORAC_CODE', 'PLUGIN_LOV_V', 'VIEW'
    from dual
),
missing_or_invalid as (
  select required_objects.owner,
         required_objects.object_name,
         required_objects.object_type,
         coalesce(objects.status, 'MISSING') status
    from required_objects
    left join dba_objects objects
      on objects.owner = required_objects.owner
     and objects.object_name = required_objects.object_name
     and objects.object_type = required_objects.object_type
   where coalesce(objects.status, 'MISSING') <> 'VALID'
),
invalid_runtime_objects as (
  select owner, object_name, object_type, status
    from dba_objects
   where owner in (
           'ORAC_API',
           'ORAC_CODE',
           'ORAC_APX_PUB',
           'ORAC',
           'ORAC_PLUGIN'
         )
     and status <> 'VALID'
)
select case
         when exists (select 1 from missing_or_invalid)
           or exists (select 1 from invalid_runtime_objects)
         then 'INVALID'
         else 'VALID'
       end
  from dual;
exit
SQL
)
  if ! grep -Eq '(^|[[:space:]])VALID([[:space:]]|$)' <<<"${core_runtime_status}"; then
    echo "ORAC_DEPLOYMENT_INCOMPLETE: core runtime plugin objects are missing or invalid."
    echo "${core_runtime_status}"
    return 1
  fi

  if [[ ! -d "${ords_conf}" ]]; then
    echo "ORAC_DEPLOYMENT_INCOMPLETE: missing ORDS config directory: ${ords_conf}"
    return 1
  fi

  if [[ ! -L "${ords_conf}" ]] || [[ "$(readlink "${ords_conf}")" != "${ords_conf_persistent}" ]]; then
    echo "ORAC_DEPLOYMENT_INCOMPLETE: ORDS runtime config is not linked to persistent config: ${ords_conf}"
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

if [[ "${ORAC_DEPLOYMENT_COMPLETE_LIB_ONLY:-0}" == "1" ]]; then
  return 0 2>/dev/null || exit 0
fi

(
  orac_deployment_complete
)
complete_status=$?

if [[ ${complete_status} -ne 0 ]]; then
  return "${complete_status}" 2>/dev/null || false
fi

echo "==================  ORAC deployment complete =================="

return 0 2>/dev/null || true
