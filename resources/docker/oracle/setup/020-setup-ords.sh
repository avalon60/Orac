#!/usr/bin/env bash
# Author: Clive Bostock
#   Date: 9 Aug 2025
#
# Orac script to configure ORDS on container setup.
#
# 020-setup-ords.sh
PROG="Orac: 020-setup-ords.sh"
timestamp() { date +"%Y-%m-%d %H:%M:%S"; }
echo "[$(timestamp)] ${PROG} Started"

orac_ords_setup() {
  set -Eeuo pipefail

  APEX_HOME=${APEX_HOME:-/home/oracle/orac/setup/apex/apex}
  ORACLE_SID=${ORACLE_SID:-FREE}
  ORACLE_PDB=${ORACLE_PDB:-FREEPDB1}
  ORAC_HOME=${ORAC_HOME:-/home/oracle/orac}
  ORACLE_BASE=${ORACLE_BASE:-/opt/oracle}
  JAVA_HOME=/usr/lib/jvm/java-17-openjdk
  PATH=$JAVA_HOME/bin:$PATH

  ORDS_HOME=${ORAC_HOME}/ords
  ORDS_CONF=${ORDS_HOME}/conf
  ORDS_CONF_PERSISTENT=${ORDS_CONF_PERSISTENT:-/opt/oracle/oradata/orac/ords/conf}
  ORDS_LOG=${ORAC_HOME}/logs
  ORDS_INIT_LOG=${ORDS_HOME}/init_ords.log
  ORDS_PWD_FILE=${ORDS_HOME}/install_pwd.txt
  local ords_metadata_status

  pushd "${ORDS_HOME}" >/dev/null

  echo "ORDS_HOME = ${ORDS_HOME}"
  echo "APEX_HOME = ${APEX_HOME}"

  if [[ -z "${ORACLE_PWD:-}" ]]; then
    echo "ORAC_ORDS_SETUP_FAILED: ORACLE_PWD is not set."
    return 1
  fi

  echo "020-setup-ords.sh: Creating password file..."
  printf '%s\n%s\n' "${ORACLE_PWD}" "${ORACLE_PWD}" > "${ORDS_PWD_FILE}"
  ls -l ${ORDS_PWD_FILE}
  chmod 600 "${ORDS_PWD_FILE}"

  rm -f nohup.out 2>/dev/null || true
  mkdir -p "$(dirname "${ORDS_CONF_PERSISTENT}")" "${ORDS_LOG}"
  if [[ -d "${ORDS_CONF_PERSISTENT}" ]] && find "${ORDS_CONF_PERSISTENT}" -type f -print -quit 2>/dev/null | grep -q .; then
    echo "ORAC_ORDS_SETUP: Keeping existing persistent ORDS config: ${ORDS_CONF_PERSISTENT}"
  elif [[ -d "${ORDS_CONF}" && ! -L "${ORDS_CONF}" ]]; then
    echo "ORAC_ORDS_SETUP: Preserving existing runtime ORDS config from ${ORDS_CONF} to ${ORDS_CONF_PERSISTENT}"
    mkdir -p "${ORDS_CONF_PERSISTENT}"
    if ! cp -a "${ORDS_CONF}/." "${ORDS_CONF_PERSISTENT}/"; then
      echo "ORAC_ORDS_SETUP_FAILED: Could not preserve runtime ORDS config at ${ORDS_CONF_PERSISTENT}."
      return 1
    fi
    echo "ORAC_ORDS_SETUP: Runtime ORDS config preserved in persistent storage."
  else
    echo "ORAC_ORDS_SETUP: No existing ORDS config to preserve before setup."
  fi

  if [[ -e "${ORDS_CONF}" && ! -L "${ORDS_CONF}" ]]; then
    rm -rf "${ORDS_CONF}"
  elif [[ -L "${ORDS_CONF}" && "$(readlink "${ORDS_CONF}")" != "${ORDS_CONF_PERSISTENT}" ]]; then
    rm -f "${ORDS_CONF}"
  fi
  mkdir -p "${ORDS_CONF_PERSISTENT}"
  if [[ ! -L "${ORDS_CONF}" ]]; then
    ln -s "${ORDS_CONF_PERSISTENT}" "${ORDS_CONF}"
  fi

  ORDS_DB_HOSTNAME="localhost"
  ORDS_DB_PORT="1521"
  ORDS_DB_SERVICENAME="${ORACLE_PDB}"
  ORDS_DB_ADMIN_USER="${ORDS_DB_ADMIN_USER:-SYS}"

  INSTALL_CMD=(
    ./bin/ords
    --config "${ORDS_CONF}"
    install
    --admin-user "${ORDS_DB_ADMIN_USER}"
    --proxy-user
    --db-hostname "${ORDS_DB_HOSTNAME}"
    --db-port "${ORDS_DB_PORT}"
    --db-servicename "${ORDS_DB_SERVICENAME}"
    --log-folder "${ORDS_LOG}"
    --feature-rest-enabled-sql true
    --password-stdin
  )

  echo "ORDS initialisation starting, with:"
  echo "================================================================"
  printf '%q ' "${INSTALL_CMD[@]}"
  echo
  echo "================================================================"
  echo "Running ORDS Install:" > "${ORDS_INIT_LOG}"
  printf '%q ' "${INSTALL_CMD[@]}" >> "${ORDS_INIT_LOG}"
  echo "< ${ORDS_PWD_FILE}" >> "${ORDS_INIT_LOG}"

  echo "${PROG}: ORDS installation launched."
  "${INSTALL_CMD[@]}" < "${ORDS_PWD_FILE}" >> "${ORDS_INIT_LOG}" 2>&1
  if grep -Eiq 'ORA-[0-9]+|SP2-[0-9]+|ERROR at line|Error executing script|does not have the privileges to install ORDS' "${ORDS_INIT_LOG}"; then
    echo "ORAC_ORDS_SETUP_FAILED: ORDS install log contains Oracle errors. See ${ORDS_INIT_LOG}."
    return 1
  fi

  echo "Integrating APEX:" >> "${ORDS_INIT_LOG}"
  ./bin/ords --config "${ORDS_CONF}" config set apex.templating.enabled true >> "${ORDS_INIT_LOG}" 2>&1

  echo "Validating ORDS metadata objects:" >> "${ORDS_INIT_LOG}"
  ords_metadata_status=$(sqlplus -L -s / as sysdba <<SQL
set heading off feedback off pagesize 0 verify off echo off
whenever sqlerror exit failure rollback
alter session set container=${ORACLE_PDB};
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
  echo "${ords_metadata_status}" >> "${ORDS_INIT_LOG}"
  if ! grep -Eq '(^|[[:space:]])VALID([[:space:]]|$)' <<<"${ords_metadata_status}"; then
    echo "ORAC_ORDS_SETUP_FAILED: ORDS metadata objects are not VALID in ${ORACLE_PDB}."
    return 1
  fi

  echo "Validating ORDS default pool:" >> "${ORDS_INIT_LOG}"
  ./bin/ords --config "${ORDS_CONF}" config list >> "${ORDS_INIT_LOG}" 2>&1
  if grep -Fq "does not contain database pool default" "${ORDS_INIT_LOG}"; then
    echo "ORAC_ORDS_SETUP_FAILED: ORDS default database pool was not created."
    return 1
  fi

  if [[ ! -L "${ORDS_CONF}" ]] || [[ "$(readlink "${ORDS_CONF}")" != "${ORDS_CONF_PERSISTENT}" ]]; then
    echo "ORAC_ORDS_SETUP_FAILED: ORDS runtime config is not linked to persistent config: ${ORDS_CONF}"
    return 1
  fi

  if [[ ! -d "${ORDS_CONF}" ]] || ! find "${ORDS_CONF}" -type f -print -quit | grep -q .; then
    echo "ORAC_ORDS_SETUP_FAILED: ORDS config directory is missing or empty: ${ORDS_CONF}"
    return 1
  fi

  # rm -f "${ORDS_PWD_FILE}"
  popd >/dev/null
}

(
  orac_ords_setup
)
ords_status=$?

if [[ ${ords_status} -ne 0 ]]; then
  echo "ORAC_ORDS_SETUP_FAILED: ${PROG} failed with status ${ords_status}."
  return "${ords_status}" 2>/dev/null || false
fi

echo "ORAC_ORDS_SETUP_COMPLETE: ORDS default pool is configured."
# IMPORTANT: no `exit` here; let the runner continue
echo "[$(timestamp)] ${PROG}: Done."
return 0 2>/dev/null || true
