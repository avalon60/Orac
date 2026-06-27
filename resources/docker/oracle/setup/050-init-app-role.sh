# Author: Clive Bostock
#   Date: 15 Mar 2026
#
# Orac script to add ADMINISTRATOR role etc. for the ORAC_ADMIN user.
#
# 050-init-app-role.sh
#
PROG="Orac: 050-init-app-role.sh"
timestamp() { date +"%Y-%m-%d %H:%M:%S"; }
echo "[$(timestamp)] ${PROG} Started"

cleanup_apex_admin_setup() {
  sqlplus -L -s / as sysdba <<SQL
set heading off feedback off pagesize 0 verify off echo off
whenever sqlerror exit failure rollback
alter session set container=${ORACLE_PDB};

begin
  execute immediate 'drop procedure orac_apx_pub.orac_admin_setup_tmp';
exception
  when others then
    if sqlcode != -4043
    then
      raise;
    end if;
end;
/
exit
SQL
}

orac_init_app_role() {
  set -uo pipefail

  export APEX_HOME=${APEX_HOME:-/home/oracle/orac/setup/apex/apex}
  export ORACLE_SID=${ORACLE_SID:-FREE}
  export ORACLE_PDB=${ORACLE_PDB:-FREEPDB1}
  export ORAC_HOME=${ORAC_HOME:-/home/oracle/orac}
  export ORACLE_BASE=${ORACLE_BASE:-/opt/oracle}

  local setup_output

  if [[ -z "${ORACLE_PWD:-}" ]]; then
    echo "ORAC_APEX_ADMIN_SETUP_FAILED: ORACLE_PWD is not set."
    return 1
  fi

  cd "${APEX_HOME}" || return 1

  echo "${PROG} Launching sqlplus; configuring APEX admin role..."
  setup_output=$(sqlplus -L -s / as sysdba <<SQL
whenever sqlerror exit failure rollback
set define off
set feedback on
set serveroutput on size unlimited
alter session set container=${ORACLE_PDB};

begin
  execute immediate 'drop procedure orac_apx_pub.orac_admin_setup_tmp';
exception
  when others then
    if sqlcode != -4043
    then
      raise;
    end if;
end;
/

create or replace procedure orac_apx_pub.orac_admin_setup_tmp
authid definer
is
  l_workspace_id number;

  procedure add_role_if_missing(p_role_static_id in varchar2)
  is
    l_role_count number;
  begin
    select count(*)
      into l_role_count
      from apex_appl_acl_user_roles
     where workspace = 'ORAC'
       and application_id = 1042
       and user_name = 'ORAC_ADMIN'
       and role_static_id = p_role_static_id;

    if l_role_count = 0
    then
      apex_acl.add_user_role (
        p_application_id => 1042,
        p_user_name      => 'ORAC_ADMIN',
        p_role_static_id => p_role_static_id
      );
    end if;
  end add_role_if_missing;
begin
  select workspace_id
    into l_workspace_id
    from apex_workspaces
   where workspace = 'ORAC';

  apex_application_install.set_workspace_id(l_workspace_id);
  apex_util.set_security_group_id(l_workspace_id);
  apex_util.set_workspace(p_workspace => 'ORAC');

  apex_util.reset_password (
    p_user_name                    => 'ORAC_ADMIN',
    p_new_password                 => '${ORACLE_PWD}',
    p_change_password_on_first_use => false
  );

  apex_util.unlock_account (
    p_user_name => 'ORAC_ADMIN'
  );

  apex_util.unexpire_workspace_account (
    p_user_name => 'ORAC_ADMIN'
  );

  add_role_if_missing('ADMINISTRATOR');
  add_role_if_missing('CONTRIBUTOR');
  add_role_if_missing('READER');

  commit;
end orac_admin_setup_tmp;
/

declare
  l_error_count number;
begin
  select count(*)
    into l_error_count
    from dba_errors
   where owner = 'ORAC_APX_PUB'
     and name = 'ORAC_ADMIN_SETUP_TMP'
     and type = 'PROCEDURE';

  if l_error_count > 0
  then
    for rec in (
      select line, position, text
        from dba_errors
       where owner = 'ORAC_APX_PUB'
         and name = 'ORAC_ADMIN_SETUP_TMP'
         and type = 'PROCEDURE'
       order by sequence
    )
    loop
      dbms_output.put_line(rec.line || ':' || rec.position || ': ' || rec.text);
    end loop;

    raise_application_error(-20000, 'orac_apx_pub.orac_admin_setup_tmp has compilation errors.');
  end if;
end;
/

begin
  orac_apx_pub.orac_admin_setup_tmp;
end;
/

begin
  execute immediate 'drop procedure orac_apx_pub.orac_admin_setup_tmp';
end;
/
exit
SQL
  ) || {
    cleanup_apex_admin_setup >/dev/null 2>&1 || true
    echo "ORAC_APEX_ADMIN_SETUP_FAILED: ${PROG} failed while configuring ORAC_ADMIN."
    echo "${setup_output}"
    return 1
  }

  echo "${setup_output}"
}

(
  orac_init_app_role
)
app_role_status=$?

if [[ ${app_role_status} -ne 0 ]]; then
  echo "ORAC_APEX_ADMIN_SETUP_FAILED: ${PROG} failed with status ${app_role_status}."
  return "${app_role_status}" 2>/dev/null || false
fi

echo "ORAC_APEX_ADMIN_SETUP_COMPLETE: ORAC_ADMIN is configured for application 1042."
echo "[$(timestamp)] ${PROG}: Done."
return 0 2>/dev/null || true
