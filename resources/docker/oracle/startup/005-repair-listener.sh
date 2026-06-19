#!/usr/bin/env bash
# Author: Clive Bostock
# Date: 20 Jun 2026
# Description: Repair Oracle listener host binding after container recreation.

PROG="Orac: 005-repair-listener.sh"
timestamp() { date +"%Y-%m-%d %H:%M:%S"; }
echo "[$(timestamp)] ${PROG} Started"

orac_repair_listener() {
  set -Eeuo pipefail

  local listener_file="${ORAC_LISTENER_FILE:-/opt/oracle/oradata/dbconfig/FREE/listener.ora}"
  local listener_log="/tmp/orac-listener-start.log"

  if [[ ! -f "${listener_file}" ]]; then
    echo "ORAC_LISTENER_REPAIR_FAILED: missing listener file: ${listener_file}"
    return 1
  fi

  if grep -Eq '\(ADDRESS[[:space:]]*=[[:space:]]*\(PROTOCOL[[:space:]]*=[[:space:]]*TCP\)\(HOST[[:space:]]*=[[:space:]]*0\.0\.0\.0\)\(PORT[[:space:]]*=[[:space:]]*1521\)\)' "${listener_file}"; then
    echo "ORAC_LISTENER_REPAIR_SKIPPED: TCP listener host is already 0.0.0.0."
  else
    sed -i -E '/PROTOCOL[[:space:]]*=[[:space:]]*TCP/s/\(HOST[[:space:]]*=[[:space:]]*[^)]+\)/(HOST = 0.0.0.0)/' "${listener_file}"
    echo "ORAC_LISTENER_REPAIR_COMPLETE: normalised TCP listener host to 0.0.0.0."
  fi

  if ! grep -Fq "EXTPROC1521" "${listener_file}"; then
    echo "ORAC_LISTENER_REPAIR_FAILED: IPC EXTPROC1521 entry is missing."
    return 1
  fi

  if pgrep -f "[t]nslsnr .*LISTENER" >/dev/null &&
     ss -ltn 2>/dev/null | grep -Eq '(^|[[:space:]])0\.0\.0\.0:1521[[:space:]]'; then
    echo "ORAC_LISTENER_REPAIR_SKIPPED: LISTENER is already running on port 1521."
    return 0
  fi

  lsnrctl start LISTENER >"${listener_log}" 2>&1 || {
    cat "${listener_log}"
    echo "ORAC_LISTENER_REPAIR_FAILED: lsnrctl start LISTENER failed."
    return 1
  }

  echo "ORAC_LISTENER_START_COMPLETE: LISTENER started."
}

(
  orac_repair_listener
)
listener_status=$?
if [[ ${listener_status} -ne 0 ]]; then
  echo "ORAC_LISTENER_REPAIR_FAILED: ${PROG} failed with status ${listener_status}."
  return "${listener_status}" 2>/dev/null || false
fi

echo "[$(timestamp)] ${PROG}: Done."
return 0 2>/dev/null || true
