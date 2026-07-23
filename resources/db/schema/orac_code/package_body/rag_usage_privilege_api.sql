--liquibase formatted sql

--changeset clive:create_package_body_orac_code_rag_usage_privilege_api context:core labels:core stripComments:false endDelimiter:/ runOnChange:true splitStatements:false
-- __author__: clive
-- __date__: 2026-07-20
-- __description__: administrative lifecycle API body for RAG usage privileges
create or replace package body orac_code.rag_usage_privilege_api
as
  function actor_name(p_actor in varchar2) return varchar2
  is
  begin
    return coalesce(
             trim(p_actor),
             sys_context('apex$session', 'app_user'),
             sys_context('userenv', 'proxy_user'),
             sys_context('userenv', 'session_user'),
             user
           );
  end actor_name;

  function active_user_id(p_username in varchar2) return number
  is
    l_user_id number;
    l_active  varchar2(1 char);
    l_username varchar2(4000 char) := trim(p_username);
  begin
    if l_username is null
    then
      return null;
    end if;

    select user_id, is_active
      into l_user_id, l_active
      from orac_api.users_v
     where username = l_username;

    if l_active <> 'Y'
    then
      return -1;
    end if;
    return l_user_id;
  exception
    when no_data_found then
      return null;
  end active_user_id;

  function grant_scope_usage(
    p_username          in varchar2,
    p_scope_type        in varchar2,
    p_scope_key         in varchar2,
    p_effective_on      in timestamp with time zone default systimestamp,
    p_expires_on        in timestamp with time zone default null,
    p_granted_by        in varchar2 default null,
    p_grant_reason_code in varchar2 default 'ADMIN_GRANT'
  ) return varchar2
  is
    l_user_id  number;
    l_scope_id number;
    l_row      orac_api.rag_usage_privileges_v%rowtype;
    l_new_row  orac_api.rag_usage_privileges_v%rowtype;
  begin
    l_user_id := active_user_id(p_username);
    if l_user_id is null then return 'RAG_USAGE_PRINCIPAL_UNKNOWN'; end if;
    if l_user_id = -1 then return 'RAG_USAGE_PRINCIPAL_INACTIVE'; end if;

    l_scope_id := orac_code.knowledge_scope_api.resolve_scope_id(
                    p_scope_type, p_scope_key
                  );
    if l_scope_id is null then return 'RAG_USAGE_SCOPE_UNKNOWN'; end if;
    if orac_code.knowledge_scope_api.scope_status(p_scope_type, p_scope_key) =
       'RAG_USAGE_SCOPE_INACTIVE'
    then
      return 'RAG_USAGE_SCOPE_INACTIVE';
    elsif orac_code.knowledge_scope_api.scope_status(p_scope_type, p_scope_key) <>
          'RAG_USAGE_SCOPE_ELIGIBLE'
    then
      return 'RAG_USAGE_SCOPE_INELIGIBLE';
    end if;

    begin
      select *
        into l_row
        from orac_api.rag_usage_privileges_v
       where user_id = l_user_id
         and knowledge_scope_id = l_scope_id
         and privilege_code = 'USE'
         and active_yn = 'Y'
       for update;

      if l_row.expires_on is null or l_row.expires_on > systimestamp
      then
        return 'RAG_USAGE_ALREADY_GRANTED';
      end if;

      l_row.active_yn := 'N';
      l_row.revoked_on := systimestamp;
      l_row.revoked_by := actor_name(p_granted_by);
      l_row.revoke_reason_code := 'EXPIRED';
      orac_api.rag_usage_privileges_tapi.upd(
        l_row.rag_usage_privilege_id, l_row, l_row.row_version
      );
    exception
      when no_data_found then
        null;
    end;

    l_new_row.user_id := l_user_id;
    l_new_row.knowledge_scope_id := l_scope_id;
    l_new_row.privilege_code := 'USE';
    l_new_row.active_yn := 'Y';
    l_new_row.effective_on := coalesce(p_effective_on, systimestamp);
    l_new_row.expires_on := p_expires_on;
    l_new_row.granted_on := systimestamp;
    l_new_row.granted_by := actor_name(p_granted_by);
    l_new_row.grant_reason_code := trim(coalesce(p_grant_reason_code, 'ADMIN_GRANT'));
    orac_api.rag_usage_privileges_tapi.ins(l_new_row);
    return 'RAG_USAGE_GRANTED';
  exception
    when dup_val_on_index then
      return 'RAG_USAGE_ALREADY_GRANTED';
  end grant_scope_usage;

  function revoke_scope_usage(
    p_username           in varchar2,
    p_scope_type         in varchar2,
    p_scope_key          in varchar2,
    p_revoked_by         in varchar2 default null,
    p_revoke_reason_code in varchar2 default 'ADMIN_REVOKE'
  ) return varchar2
  is
    l_user_id  number;
    l_scope_id number;
    l_row      orac_api.rag_usage_privileges_v%rowtype;
  begin
    l_user_id := active_user_id(p_username);
    if l_user_id is null then return 'RAG_USAGE_PRINCIPAL_UNKNOWN'; end if;
    if l_user_id = -1 then return 'RAG_USAGE_PRINCIPAL_INACTIVE'; end if;
    l_scope_id := orac_code.knowledge_scope_api.resolve_scope_id(
                    p_scope_type, p_scope_key
                  );
    if l_scope_id is null then return 'RAG_USAGE_SCOPE_UNKNOWN'; end if;

    begin
      select *
        into l_row
        from orac_api.rag_usage_privileges_v
       where user_id = l_user_id
         and knowledge_scope_id = l_scope_id
         and privilege_code = 'USE'
         and active_yn = 'Y'
       for update;
    exception
      when no_data_found then
        return 'RAG_USAGE_NOT_GRANTED';
    end;

    l_row.active_yn := 'N';
    l_row.revoked_on := systimestamp;
    l_row.revoked_by := actor_name(p_revoked_by);
    l_row.revoke_reason_code := trim(coalesce(p_revoke_reason_code, 'ADMIN_REVOKE'));
    orac_api.rag_usage_privileges_tapi.upd(
      l_row.rag_usage_privilege_id, l_row, l_row.row_version
    );
    return 'RAG_USAGE_REVOKED';
  end revoke_scope_usage;
end rag_usage_privilege_api;
/
--rollback drop package body orac_code.rag_usage_privilege_api;
