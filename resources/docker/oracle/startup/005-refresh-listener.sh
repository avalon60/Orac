#!/usr/bin/env bash
# Author: Clive Bostock
#   Date: 1 Jun 2026
#
# Refresh Oracle listener hostnames after container recreation.
#
# Oracle persists dbconfig under ORADATA_DIR. If the DB container is recreated
# against an existing ORADATA_DIR, listener.ora can still reference the old
# container hostname, which prevents SQL*Net readiness checks from succeeding.
PROG="Orac: 005-refresh-listener.sh"
timestamp() { date +"%Y-%m-%d %H:%M:%S"; }
echo "[$(timestamp)] ${PROG} Started"

orac_refresh_listener() {
  set -Eeuo pipefail

  local current_host
  local listener_files=()
  local listener_file

  current_host="$(hostname)"
  if [[ -z "${current_host}" ]]; then
    echo "ORAC_LISTENER_REFRESH_FAILED: unable to determine container hostname."
    return 1
  fi

  while IFS= read -r listener_file; do
    listener_files+=("${listener_file}")
  done < <(
    find /opt/oracle/oradata/dbconfig "${ORACLE_HOME:-/opt/oracle/product/26ai/dbhomeFree}/network/admin" \
      -name listener.ora \
      -type f \
      2>/dev/null | sort -u
  )

  if [[ "${#listener_files[@]}" -eq 0 ]]; then
    echo "ORAC_LISTENER_REFRESH_FAILED: no listener.ora files found."
    return 1
  fi

  for listener_file in "${listener_files[@]}"; do
    echo "${PROG}: refreshing listener host in ${listener_file} -> ${current_host}"
    sed -i -E "s/\\(HOST[[:space:]]*=[[:space:]]*[^)]+\\)/(HOST = ${current_host})/g" "${listener_file}"
  done

  lsnrctl start LISTENER >/tmp/orac-listener-start.log 2>&1 || {
    cat /tmp/orac-listener-start.log
    echo "ORAC_LISTENER_REFRESH_FAILED: lsnrctl start LISTENER failed."
    return 1
  }

  sqlplus -L -s / as sysdba <<SQL >/tmp/orac-listener-register.log 2>&1 || {
alter system register;
exit
SQL
    cat /tmp/orac-listener-register.log
    echo "ORAC_LISTENER_REFRESH_FAILED: alter system register failed."
    return 1
  }

  echo "ORAC_LISTENER_REFRESH_COMPLETE: listener is configured for ${current_host}."
}

(
  orac_refresh_listener
)
listener_status=$?
if [[ ${listener_status} -ne 0 ]]; then
  echo "ORAC_LISTENER_REFRESH_FAILED: ${PROG} failed with status ${listener_status}."
  return "${listener_status}" 2>/dev/null || false
fi

echo "[$(timestamp)] ${PROG}: Done."
return 0 2>/dev/null || true
