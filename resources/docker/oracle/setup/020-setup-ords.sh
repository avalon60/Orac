#!/usr/bin/env bash
# Author: Clive Bostock
#   Date: 9 Aug 2025
#
# Orac script to configure ORDS on container setup.
#
# 020-setup-ords.sh
PROG='020-setup-ords.sh'
echo "${PROG} Started."

(
  set -Eeuo pipefail

  APEX_HOME=${APEX_HOME:-/home/oracle/orac/setup/apex/apex}
  ORACLE_SID=${ORACLE_SID:-FREE}
  ORAC_HOME=${ORAC_HOME:-/home/oracle/orac}
  ORACLE_BASE=${ORACLE_BASE:-/opt/oracle}
  JAVA_HOME=/usr/lib/jvm/java-17-openjdk
  PATH=$JAVA_HOME/bin:$PATH

  ORDS_HOME=${ORAC_HOME}/ords
  ORDS_CONF=${ORDS_HOME}/conf
  ORDS_LOG=${ORAC_HOME}/logs
  ORDS_PWD_FILE=${ORDS_HOME}/install_pwd.txt

  pushd "${ORDS_HOME}" >/dev/null

  echo "ORDS_HOME = ${ORDS_HOME}"
  echo "APEX_HOME = ${APEX_HOME}"

  : "${ORACLE_PWD:?ORACLE_PWD not set}"   # fail early if missing
  printf '%s\n%s\n' "${ORACLE_PWD}" "${ORACLE_PWD}" > "${ORDS_PWD_FILE}"
  chmod 600 "${ORDS_PWD_FILE}"

  rm -f nohup.out 2>/dev/null || true
  rm -rf "${ORDS_CONF}" "${ORDS_LOG}"
  mkdir -p "${ORDS_CONF}" "${ORDS_LOG}"

  ORDS_DB_HOSTNAME="localhost"
  ORDS_DB_PORT="1521"
  ORDS_DB_SERVICENAME="${ORACLE_PDB:-FREEPDB1}"
  ORDS_DB_ADMIN_USER="SYS"

  INSTALL_CMD="./bin/ords --config ${ORDS_CONF} install \
    --db-pool orac \
    --admin-user ${ORDS_DB_ADMIN_USER} \
    --proxy-user \
    --db-hostname ${ORDS_DB_HOSTNAME} \
    --db-port ${ORDS_DB_PORT} \
    --db-servicename ${ORDS_DB_SERVICENAME} \
    --log-folder ${ORDS_LOG} \
    --feature-rest-enabled-sql true \
    --password-stdin"

  echo "Running ORDS Install:" > init_ords.log
  echo "${INSTALL_CMD} < ${ORDS_PWD_FILE}" >> init_ords.log

  echo "${PROG}: ORDS installation launched."
  bash -c "${INSTALL_CMD}" < "${ORDS_PWD_FILE}"

  echo "Integrating APEX:" >> init_ords.log
  ./bin/ords config set apex.templating.enabled true --conf "${ORDS_CONF}" >> init_ords.log
  ./bin/ords enable-schema APEX_PUBLIC_USER --db-pool orac >> init_ords.log

  rm -f "${ORDS_PWD_FILE}"
  popd >/dev/null
) || { echo "${PROG}: FAILED"; return 1 2>/dev/null || exit 1; }

echo "${PROG}: Done."
# IMPORTANT: no `exit` here; let the runner continue

