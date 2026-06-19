# Author: Clive Bostock
#   Date: 22 Nov 2025
#
# Script to start ORDS on container startup.
#
PROG='10-start-ords.sh'
export ORAC_HOME=${ORAC_HOME:-/home/oracle/orac}
export ORDS_HOME=${ORAC_HOME}/ords
export ORDS_CONF=${ORDS_HOME}/conf
export ORDS_CONF_PERSISTENT=${ORDS_CONF_PERSISTENT:-/opt/oracle/oradata/orac/ords/conf}
JAVA_HOME=/usr/lib/jvm/java-17-openjdk
PATH=$JAVA_HOME/bin:$PATH
ORDS_START_LOG=/tmp/ords-start.log

orac_start_ords() {
  set -uo pipefail

  if [[ ! -d "${ORDS_CONF_PERSISTENT}" ]]; then
    {
      echo "ORAC_ORDS_START_FAILED: missing persistent ORDS config directory: ${ORDS_CONF_PERSISTENT}"
      echo "The DB/APEX/ORDS setup did not complete; refusing to serve unmapped ORDS."
    } | tee "${ORDS_START_LOG}"
    return 1
  fi

  if [[ -e "${ORDS_CONF}" && ! -L "${ORDS_CONF}" ]]; then
    {
      echo "ORAC_ORDS_START_FAILED: runtime ORDS config path is not a symlink: ${ORDS_CONF}"
      echo "Refusing to overwrite disposable config automatically during startup."
    } | tee "${ORDS_START_LOG}"
    return 1
  fi

  if [[ -L "${ORDS_CONF}" && "$(readlink "${ORDS_CONF}")" != "${ORDS_CONF_PERSISTENT}" ]]; then
    rm -f "${ORDS_CONF}"
  fi

  if [[ ! -L "${ORDS_CONF}" ]]; then
    ln -s "${ORDS_CONF_PERSISTENT}" "${ORDS_CONF}"
  fi

  if [[ ! -d "${ORDS_CONF}" ]]; then
    {
      echo "ORAC_ORDS_START_FAILED: missing ORDS config directory: ${ORDS_CONF}"
      echo "The DB/APEX/ORDS setup did not complete; refusing to serve unmapped ORDS."
    } | tee "${ORDS_START_LOG}"
    return 1
  fi

  pushd "${ORDS_HOME}" >/dev/null || return 1

  if ! ./bin/ords --config "${ORDS_CONF}" config list > "${ORDS_START_LOG}" 2>&1; then
    {
      echo "ORAC_ORDS_START_FAILED: unable to read ORDS configuration."
      echo "The DB/APEX/ORDS setup did not complete; refusing to serve unmapped ORDS."
    } | tee -a "${ORDS_START_LOG}"
    popd >/dev/null
    return 1
  fi

  if grep -Fq "does not contain database pool default" "${ORDS_START_LOG}"; then
    {
      echo "ORAC_ORDS_START_FAILED: default ORDS database pool is missing."
      echo "The DB/APEX/ORDS setup did not complete; refusing to serve unmapped ORDS."
    } | tee -a "${ORDS_START_LOG}"
    popd >/dev/null
    return 1
  fi

  echo "-e ORDS_HOME = ${ORDS_HOME}"
  echo "./bin/ords --config ${ORDS_CONF} serve"
  echo "APEX admin URL: http://localhost:${PORT_HTTP:-8042}/ords/r/orac/orac-administration1042/login"
  nohup ./bin/ords --config "${ORDS_CONF}" serve >"${ORDS_START_LOG}" 2>&1 &
  popd >/dev/null
}

(
  orac_start_ords
)
ords_start_status=$?
if [[ ${ords_start_status} -ne 0 ]]; then
  return "${ords_start_status}" 2>/dev/null || false
fi

return 0 2>/dev/null || true
