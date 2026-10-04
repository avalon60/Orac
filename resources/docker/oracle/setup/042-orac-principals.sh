#!/usr/bin/env bash
# Author: Clive Bostock
# Date: 03-Oct-2026
# Description: Provision the reserved system principal and initial Orac user.
# Purpose: Idempotently provision installation identities and user defaults.
# Usage: Sourced by Oracle container setup; ORAC_INSTALL_USERNAME is required.

set -Eeuo pipefail

PROG="Orac: 042-orac-principals.sh"
oracle_pdb="${ORACLE_PDB:-FREEPDB1}"
installer_username="${ORAC_INSTALL_USERNAME:-}"

if [[ ${#installer_username} -lt 3 || ${#installer_username} -gt 32 || ! "${installer_username}" =~ ^[a-z][a-z0-9]*([._-][a-z0-9]+)*$ ]]; then
  printf '%s ERROR: ORAC_INSTALL_USERNAME is missing or invalid.\n' "${PROG}" >&2
  return 1 2>/dev/null || exit 1
fi

printf '%s Provisioning Orac principals for installer %s.\n' \
  "${PROG}" "${installer_username}"

sqlplus -L -s / as sysdba <<SQL
whenever sqlerror exit failure rollback
set serveroutput on
alter session set container=${oracle_pdb};
declare
  l_user_created varchar2(1);
begin
  orac_code.installation_bootstrap_api.ensure_principals(
    p_installer_username => '${installer_username}',
    p_user_created       => l_user_created
  );
  commit;
  dbms_output.put_line(
    case l_user_created
      when 'Y' then 'Created ordinary Orac user: ${installer_username}'
      else 'Preserved existing Orac user: ${installer_username}'
    end
  );
end;
/
exit
SQL
