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
  begin
    return authorization_result_by_id(
      p_username => p_username,
      p_knowledge_scope_id => orac_code.knowledge_scope_api.resolve_scope_id(
        p_scope_type, p_scope_key
      )
    );
  exception
    when others then
      return 'RAG_USAGE_AUTHORIZATION_UNAVAILABLE';
  end authorization_result;

  function authorization_result_by_id(
    p_username           in varchar2,
    p_knowledge_scope_id in number
  ) return varchar2
  is
    l_user_id  number;
    l_active   varchar2(1 char);
    l_count    number;
    l_expired  number;
    l_username varchar2(4000 char) := trim(p_username);
    l_scope_status varchar2(100 char);
    l_scope_type varchar2(30 char);
    l_scope_key varchar2(255 char);
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

    begin
      execute immediate
        'begin :status := orac_code.knowledge_scope_api.' ||
        'scope_status_by_id(:scope_id); end;'
        using out l_scope_status, in p_knowledge_scope_id;
    exception
      when others then
        if sqlcode <> -6550
        then
          raise;
        end if;
        select scope_type, scope_key
          into l_scope_type, l_scope_key
          from orac_code.knowledge_scope_registry_v
         where knowledge_scope_id = p_knowledge_scope_id;
        l_scope_status := orac_code.knowledge_scope_api.scope_status(
                            l_scope_type, l_scope_key
                          );
    end;
    if l_scope_status <> 'RAG_USAGE_SCOPE_ELIGIBLE'
    then
      return l_scope_status;
    end if;
    select count(*),
           count(case when expires_on is not null and expires_on <= systimestamp then 1 end)
      into l_count, l_expired
      from orac_api.rag_usage_privileges_v
     where user_id = l_user_id
       and knowledge_scope_id = p_knowledge_scope_id
       and privilege_code = 'USE'
       and active_yn = 'Y'
       and effective_on <= systimestamp;

    if l_count = 0 then return 'RAG_USAGE_NOT_GRANTED'; end if;
    if l_expired = l_count then return 'RAG_USAGE_EXPIRED'; end if;
    return 'RAG_USAGE_GRANTED';
  exception
    when others then
      return 'RAG_USAGE_AUTHORIZATION_UNAVAILABLE';
  end authorization_result_by_id;

  procedure open_authorised_project_domains(
    p_username        in varchar2,
    p_candidate_limit in number,
    p_domains            out sys_refcursor
  )
  is
    l_username varchar2(4000 char) := trim(p_username);
  begin
    if l_username is null
    then
      open p_domains for
        select cast(null as varchar2(100)) project_code,
               cast(null as varchar2(200)) display_name,
               cast(null as varchar2(1000)) description,
               cast(null as varchar2(64)) descriptor_version,
               cast(null as number) authorised_catalogue_size
          from dual
         where 1 = 0;
      return;
    end if;

    if p_candidate_limit is null
       or p_candidate_limit <= 0
       or p_candidate_limit > 10001
    then
      open p_domains for
        select cast(null as varchar2(100)) project_code,
               cast(null as varchar2(200)) display_name,
               cast(null as varchar2(1000)) description,
               cast(null as varchar2(64)) descriptor_version,
               cast(null as number) authorised_catalogue_size
          from dual
         where 1 = 0;
      return;
    end if;

    open p_domains for
      with authorised_projects as (
        select project.project_id,
               project.project_code,
               project.display_name,
               project.description,
               project.row_version
          from orac_api.users_v usr
          join orac_api.rag_usage_privileges_v privilege
            on privilege.user_id = usr.user_id
           and privilege.privilege_code = 'USE'
           and privilege.active_yn = 'Y'
           and privilege.effective_on <= systimestamp
           and (
                 privilege.expires_on is null
                 or privilege.expires_on > systimestamp
               )
          join orac_api.knowledge_scopes_v scope
            on scope.knowledge_scope_id = privilege.knowledge_scope_id
           and scope.scope_type = 'PROJECT'
          join orac_api.project_registry_v project
            on project.project_id = scope.project_id
           and project.active_yn = 'Y'
         where lower(usr.username) = lower(l_username)
           and usr.is_active = 'Y'
         group by project.project_id,
                  project.project_code,
                  project.display_name,
                  project.description,
                  project.row_version
      )
      select project_code,
             display_name,
             description,
             to_char(row_version) descriptor_version,
             count(*) over () authorised_catalogue_size
        from authorised_projects
       order by project_id
       fetch first p_candidate_limit rows only;
  exception
    when others then
      open p_domains for
        select cast(null as varchar2(100)) project_code,
               cast(null as varchar2(200)) display_name,
               cast(null as varchar2(1000)) description,
               cast(null as varchar2(64)) descriptor_version,
               cast(null as number) authorised_catalogue_size
          from dual
         where 1 = 0;
  end open_authorised_project_domains;
end rag_usage_authorization_api;
/
--rollback drop package body orac_code.rag_usage_authorization_api;
