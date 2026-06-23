--liquibase formatted sql

--changeset clive:create_package_body_orac_code_package_body_plugin_apex_app_auth_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-06-22
-- __description__: plugin APEX application authorization helper API body

create or replace package body orac_code.plugin_apex_app_auth_api as
  c_hub_app_id constant number := 1043;
  c_workspace  constant varchar2(30 char) := 'ORAC';

  procedure set_workspace_context
  is
    l_security_group_id number;
  begin
    l_security_group_id := apex_util.find_security_group_id(
                             p_workspace => c_workspace
                           );

    apex_util.set_security_group_id(
      p_security_group_id => l_security_group_id
    );
  exception
    when others then
      null;
  end set_workspace_context;

  function current_app_user(
    p_app_user in varchar2
  ) return varchar2
  is
    l_app_user varchar2(255 char);
  begin
    l_app_user := nullif(trim(p_app_user), '');

    if l_app_user is null
    then
      l_app_user := nullif(trim(v('APP_USER')), '');
    end if;

    return upper(l_app_user);
  exception
    when others then
      return upper(nullif(trim(p_app_user), ''));
  end current_app_user;

  function has_acl_role(
    p_app_user       in varchar2,
    p_role_static_id in varchar2
  ) return boolean
  is
    l_role_count pls_integer;
  begin
    set_workspace_context;

    select count(1)
      into l_role_count
      from apex_appl_acl_user_roles
     where application_id = c_hub_app_id
       and upper(user_name) = upper(p_app_user)
       and role_static_id = p_role_static_id;

    return l_role_count > 0;
  exception
    when others then
      return false;
  end has_acl_role;

  function has_required_role(
    p_required_role in varchar2,
    p_app_user      in varchar2 default null
  ) return number
  is
    l_app_user      varchar2(255 char);
    l_required_role varchar2(128 char);
    l_authorized    boolean := false;
  begin
    l_app_user := current_app_user(p_app_user);
    l_required_role := upper(nullif(trim(p_required_role), ''));

    if l_app_user is null or l_required_role is null
    then
      return 0;
    end if;

    case l_required_role
      when 'ORAC_ADMIN' then
        l_authorized := has_acl_role(l_app_user, 'ADMINISTRATOR');
      when 'ORAC_CONTRIBUTOR' then
        l_authorized := has_acl_role(l_app_user, 'ADMINISTRATOR')
                        or has_acl_role(l_app_user, 'CONTRIBUTOR');
      when 'ORAC_READER' then
        l_authorized := has_acl_role(l_app_user, 'ADMINISTRATOR')
                        or has_acl_role(l_app_user, 'CONTRIBUTOR')
                        or has_acl_role(l_app_user, 'READER');
      else
        l_authorized := false;
    end case;

    if l_authorized
    then
      return 1;
    end if;

    return 0;
  exception
    when others then
      return 0;
  end has_required_role;
end plugin_apex_app_auth_api;
/

--rollback drop package body orac_code.plugin_apex_app_auth_api;
