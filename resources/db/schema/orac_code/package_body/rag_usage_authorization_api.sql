--liquibase formatted sql

--changeset clive:create_package_body_orac_code_rag_usage_authorization_api context:core labels:core stripComments:false endDelimiter:/ runOnChange:true splitStatements:false
-- __author__: clive
-- __date__: 2026-07-20
-- __description__: fail-closed runtime RAG usage decision API body
create or replace package body orac_code.rag_usage_authorization_api
as
  function authorization_result(
    p_username   in varchar2,
    p_scope_type in varchar2,
    p_scope_key  in varchar2
  ) return varchar2
  is
    l_user_id  number;
    l_active   varchar2(1 char);
    l_scope_id number;
    l_count    number;
    l_expired  number;
    l_username varchar2(4000 char) := trim(p_username);
  begin
    if l_username is null
    then
      return 'RAG_USAGE_PRINCIPAL_UNKNOWN';
    end if;

    begin
      select user_id, is_active
        into l_user_id, l_active
        from orac_api.users_v
       where username = l_username;
    exception
      when no_data_found then
        return 'RAG_USAGE_PRINCIPAL_UNKNOWN';
    end;
    if l_active <> 'Y' then return 'RAG_USAGE_PRINCIPAL_INACTIVE'; end if;

    l_scope_id := orac_code.knowledge_scope_api.resolve_scope_id(
                    p_scope_type, p_scope_key
                  );
    if l_scope_id is null then return 'RAG_USAGE_SCOPE_UNKNOWN'; end if;
    select count(*),
           count(case when expires_on is not null and expires_on <= systimestamp then 1 end)
      into l_count, l_expired
      from orac_api.rag_usage_privileges_v
     where user_id = l_user_id
       and knowledge_scope_id = l_scope_id
       and privilege_code = 'USE'
       and active_yn = 'Y'
       and effective_on <= systimestamp;

    if l_count = 0 then return 'RAG_USAGE_NOT_GRANTED'; end if;
    if l_expired = l_count then return 'RAG_USAGE_EXPIRED'; end if;
    return 'RAG_USAGE_GRANTED';
  exception
    when others then
      return 'RAG_USAGE_AUTHORIZATION_UNAVAILABLE';
  end authorization_result;
end rag_usage_authorization_api;
/
--rollback drop package body orac_code.rag_usage_authorization_api;
