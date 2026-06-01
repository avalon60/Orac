#!/usr/bin/env bash
# Author: Clive Bostock
#   Date: 15 Mar 2026
#
# Orac script to restart ORDS as part of post install steps
#
# 026-restart-ords.sh

PROG="Orac: 026-restart-ords.sh"

orac_restart_ords() {
  set -Eeuo pipefail

  ORAC_HOME=${ORAC_HOME:-/home/oracle/orac}
  ORDS_HOME=${ORAC_HOME}/ords
  ORDS_CONF=${ORDS_HOME}/conf
  JAVA_HOME=/usr/lib/jvm/java-17-openjdk
  PATH=$JAVA_HOME/bin:$PATH

  pkill -f ords || true

  cd "${ORDS_HOME}"
  nohup ./bin/ords --config "${ORDS_CONF}" serve >/tmp/ords-restart.log 2>&1 &
}

(
  orac_restart_ords
)
ords_restart_status=$?

if [[ ${ords_restart_status} -ne 0 ]]; then
  echo "ORAC_ORDS_START_FAILED: ${PROG} failed with status ${ords_restart_status}."
  return "${ords_restart_status}" 2>/dev/null || false
fi

return 0 2>/dev/null || true
