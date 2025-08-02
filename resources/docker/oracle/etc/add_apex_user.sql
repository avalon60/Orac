define passwd='%ORACLE_PWD%'
define oracle_sid='%ORACLE_SID%'
define pdb_name='%ORACLE_PDB%'
set verify off
alter session set container=&&pdb_name; 
prompt Create APEX account for %USERNAME% ...

col username new_value apex_user noprint
set verify off

select username
from dba_users
where regexp_like(username, 'APEX_[0-9]+');

alter session set current_schema = &&apex_user;

declare
  l_pwd            varchar2(64) := '%ORACLE_PWD%';
  l_workspace_id   number;
begin
    select workspace_id into l_workspace_id
     from apex_workspaces
    where workspace = '%APEX_WORKSPACE%';

    apex_application_install.set_workspace_id (l_workspace_id);
    apex_util.set_security_group_id (p_security_group_id => apex_application_install.get_workspace_id);
    apex_util.set_workspace(
        p_workspace      => '%APEX_WORKSPACE%'
    );


    apex_util.set_workspace(
        p_workspace      => '%APEX_WORKSPACE%'
    );
         
    apex_util.create_user(
        p_user_name                    => '%USERNAME%',
        p_first_name                   => '%FIRST_NAME%',
        p_last_name                    => '%LAST_NAME%',
        p_email_address                => '%EMAIL_ID%',
        p_web_password                 => l_pwd,
        p_developer_privs              => '%APEX_PRIVILEGES%',
        p_default_schema               => '%DEFAULT_SCHEMA%',
        p_change_password_on_first_use => 'N' 
    );
 
    commit;
end;
/
exit;
