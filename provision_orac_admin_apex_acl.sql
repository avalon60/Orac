-- Author: Clive Bostock
-- Date: 27-Jun-2026
-- Purpose: Re-provision ORAC_ADMIN APEX ACL roles for Orac application 1042.
-- Usage: sqlplus -L / as sysdba @provision_orac_admin_apex_acl.sql
--        Run after re-importing resources/db/apex/orac_apps/f1042.sql.
--        If the local PDB name differs, change orac_pdb below before running.

whenever sqlerror exit failure rollback

set define on
set feedback on
set serveroutput on size unlimited
set verify off

define orac_pdb = FREEPDB1
define orac_workspace = ORAC
define orac_app_id = 1042
define orac_app_user = ORAC_ADMIN

alter session set container=&orac_pdb.;

prompt Re-provisioning APEX ACL roles for &orac_app_user. in workspace &orac_workspace., app &orac_app_id.

declare
  l_workspace_id number;
  l_user_count   number;

  procedure add_role_if_missing(p_role_static_id in varchar2)
  is
    l_role_count number;
  begin
    select count(*)
      into l_role_count
      from apex_appl_acl_user_roles
     where workspace = upper('&&orac_workspace.')
       and application_id = &&orac_app_id.
       and user_name = upper('&&orac_app_user.')
       and role_static_id = p_role_static_id;

    if l_role_count = 0
    then
      apex_acl.add_user_role(
        p_application_id => &&orac_app_id.,
        p_user_name      => upper('&&orac_app_user.'),
        p_role_static_id => p_role_static_id
      );

      dbms_output.put_line('Added role: ' || p_role_static_id);
    else
      dbms_output.put_line('Role already present: ' || p_role_static_id);
    end if;
  end add_role_if_missing;
begin
  select workspace_id
    into l_workspace_id
    from apex_workspaces
   where workspace = upper('&&orac_workspace.');

  apex_application_install.set_workspace_id(l_workspace_id);
  apex_util.set_security_group_id(l_workspace_id);
  apex_util.set_workspace(p_workspace => upper('&&orac_workspace.'));

  select count(*)
    into l_user_count
    from apex_workspace_apex_users
   where workspace_name = upper('&&orac_workspace.')
     and user_name = upper('&&orac_app_user.');

  if l_user_count = 0
  then
    raise_application_error(
      -20000,
      'APEX user '
      || upper('&&orac_app_user.')
      || ' does not exist in workspace '
      || upper('&&orac_workspace.')
      || '.'
    );
  end if;

  add_role_if_missing('ADMINISTRATOR');
  add_role_if_missing('CONTRIBUTOR');
  add_role_if_missing('READER');

  commit;
end;
/

select role_static_id
  from apex_appl_acl_user_roles
 where workspace = upper('&&orac_workspace.')
   and application_id = &&orac_app_id.
   and user_name = upper('&&orac_app_user.')
   and role_static_id in ('ADMINISTRATOR', 'CONTRIBUTOR', 'READER')
 order by role_static_id;

prompt APEX ACL provisioning complete.

exit success
