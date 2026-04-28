# Author: Clive Bostock
#   Date: 25 Apr 2026
#
# Orac script to create application schema users during container setup.
#
set -Eeuo pipefail

PROG="Orac: 030-orac-user.sh"
timestamp() { date +"%Y-%m-%d %H:%M:%S"; }
echo "[$(timestamp)] ${PROG} Started"
export APEX_HOME=${APEX_HOME:-/home/oracle/orac/setup/apex/apex}
export ORACLE_SID=${ORACLE_SID:-FREE}
export ORACLE_PDB=${ORACLE_PDB:-FREEPDB1}
export ORAC_HOME=${ORAC_HOME:-/home/oracle/orac}
export ORACLE_BASE=${ORACLE_BASE:-/opt/oracle}
USER_LIST_FILE="${ORACLE_BASE}/scripts/setup/orac_users.txt"

if [[ ! -f "${USER_LIST_FILE}" ]]; then
  echo "[$(timestamp)] ${PROG} Missing user list file: ${USER_LIST_FILE}"
  exit 1
fi

mapfile -t ORAC_USERS < <(grep -v '^[[:space:]]*$' "${USER_LIST_FILE}")

if [[ ${#ORAC_USERS[@]} -eq 0 ]]; then
  echo "[$(timestamp)] ${PROG} No users defined in ${USER_LIST_FILE}"
  exit 1
fi

pushd "${APEX_HOME}" >/dev/null

echo "${PROG} Started"
echo "${PROG} Launching sqlplus; creating application users..."
sqlplus / as sysdba <<EOF
alter session set container=${ORACLE_PDB};

EOF

for user_name in "${ORAC_USERS[@]}"; do
  echo "[$(timestamp)] ${PROG} Ensuring user ${user_name} exists"
  sqlplus / as sysdba <<EOF
alter session set container=${ORACLE_PDB};

declare
  l_count number;
begin
  select count(*)
    into l_count
    from dba_users
   where username = upper('${user_name}');

  if l_count = 0 then
    execute immediate q'[
      create user ${user_name} identified by ${ORACLE_PWD}
        default tablespace users
        temporary tablespace temp
        quota unlimited on users
    ]';
  end if;
end;
/

grant create session, create table, create view, create sequence,
      create procedure, create trigger, create type, create synonym
to ${user_name};
EOF
done

popd >/dev/null
echo "[$(timestamp)] ${PROG}: Done."
