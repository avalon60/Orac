--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 25-Oct-2026
-- Description: Binds plugin APEX semantic searches to the current user and installed app.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_package_body_orac_code_knowledge_apex_search_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package body orac_code.knowledge_apex_search_api as
  procedure current_apex_identity(
    p_username out varchar2,
    p_application_id out number
  )
  is
    l_app_id varchar2(30 char);
    l_app_user varchar2(4000 char);
  begin
    l_app_user := nullif(trim(sys_context('APEX$SESSION', 'APP_USER')), '');
    l_app_id := nullif(trim(sys_context('APEX$SESSION', 'APP_ID')), '');
    if l_app_user is null or length(l_app_user) > 128 or l_app_id is null
       or not regexp_like(l_app_id, '^[0-9]{1,12}$')
    then
      raise_application_error(-20710, 'KNOWLEDGE_APEX_SESSION_REQUIRED');
    end if;
    p_username := l_app_user;
    p_application_id := to_number(l_app_id);
  end current_apex_identity;

  function app_scope_id(p_application_id in number) return number
  is
    l_plugin_id orac_api.plugin_apex_apps_v.plugin_id%type;
    l_scope_id number;
  begin
    select app.plugin_id, plugin.knowledge_scope_id
      into l_plugin_id, l_scope_id
      from orac_api.plugin_apex_apps_v app
      join orac_code.plugin_registry_v plugin
        on plugin.plugin_id = app.plugin_id
     where app.installed_app_id = p_application_id
       and app.workspace = 'ORAC'
       and app.parsing_schema = 'ORAC_APX_PUB'
       and app.enabled = 'Y'
       and app.install_status = 'installed'
       and plugin.enabled = 'Y'
       and plugin.removal_id is null
       and json_value(app.installation_receipt,
           '$.plugin_registry_id' returning number) = plugin.plugin_registry_id
       and json_value(app.installation_receipt,
           '$.application_id' returning number) = p_application_id;
    if orac_code.plugin_apex_app_auth_api.plugin_is_available(
         l_plugin_id, p_application_id
       ) <> 1
       or nvl(orac_code.knowledge_scope_api.scope_status_by_id(l_scope_id), 'X')
          <> 'RAG_USAGE_SCOPE_ELIGIBLE'
    then
      raise_application_error(-20711, 'KNOWLEDGE_APEX_UNAVAILABLE');
    end if;
    return l_scope_id;
  exception
    when no_data_found or too_many_rows then
      raise_application_error(-20711, 'KNOWLEDGE_APEX_UNAVAILABLE');
  end app_scope_id;

  procedure require_use(p_username in varchar2, p_scope_id in number)
  is
  begin
    if nvl(orac_code.rag_usage_authorization_api.authorization_result_by_id(
         p_username, p_scope_id
       ), 'X') <> 'RAG_USAGE_GRANTED'
    then
      raise_application_error(-20712, 'KNOWLEDGE_APEX_NOT_AUTHORISED');
    end if;
  end require_use;

  procedure submit_search(
    p_query in varchar2,
    p_request_id out number
  )
  is
    l_username varchar2(128 char);
    l_app_id number;
    l_scope_id number;
    l_plugin_registry_id number;
    l_query varchar2(2048 char);
    l_recent_count number;
    l_pending_count number;
  begin
    current_apex_identity(l_username, l_app_id);
    if p_query is null or length(trim(p_query)) > 2048
    then
      raise_application_error(-20713, 'KNOWLEDGE_APEX_QUERY_INVALID');
    end if;
    l_query := trim(p_query);
    if l_query is null
    then
      raise_application_error(-20713, 'KNOWLEDGE_APEX_QUERY_INVALID');
    end if;
    l_scope_id := app_scope_id(l_app_id);
    require_use(l_username, l_scope_id);
    select count(*),
           count(case when status_code in ('QUEUED', 'PROCESSING') then 1 end)
      into l_recent_count, l_pending_count
      from orac_api.knowledge_apex_search_requests_v
     where username = l_username
       and application_id = l_app_id
       and created_on > systimestamp - interval '1' hour;
    if l_recent_count >= 30 or l_pending_count >= 5
    then
      raise_application_error(-20714, 'KNOWLEDGE_APEX_RATE_LIMITED');
    end if;
    select plugin_registry_id
      into l_plugin_registry_id
      from orac_api.plugin_registry_v
     where knowledge_scope_id = l_scope_id;
    insert into orac_api.knowledge_apex_search_requests_v (
      username, application_id, plugin_registry_id,
      knowledge_scope_id, query_text
    ) values (
      l_username, l_app_id, l_plugin_registry_id,
      l_scope_id, l_query
    ) returning search_request_id into p_request_id;
  end submit_search;

  procedure read_search(
    p_request_id in number,
    p_status out varchar2,
    p_results out sys_refcursor
  )
  is
    l_username varchar2(128 char);
    l_app_id number;
    l_scope_id number;
    l_request orac_api.knowledge_apex_search_requests_v%rowtype;
  begin
    current_apex_identity(l_username, l_app_id);
    select * into l_request
      from orac_api.knowledge_apex_search_requests_v
     where search_request_id = p_request_id
       and username = l_username
       and application_id = l_app_id;
    l_scope_id := app_scope_id(l_app_id);
    if l_request.knowledge_scope_id <> l_scope_id
    then
      raise_application_error(-20711, 'KNOWLEDGE_APEX_UNAVAILABLE');
    end if;
    require_use(l_username, l_scope_id);
    p_status := case when l_request.expires_on <= systimestamp
                     then 'EXPIRED' else l_request.status_code end;
    open p_results for
      select jt.ordinal, chunk.document_id, chunk.document_version_id,
             chunk.chunk_id, chunk.chunk_no, chunk.title,
             jt.relevance_score,
             dbms_lob.substr(chunk.chunk_text, 2200, 1) excerpt
        from json_table(
               case when p_status = 'COMPLETED'
                    then l_request.result_refs_json else to_clob('[]') end,
               '$[*]' columns (
                 ordinal for ordinality,
                 document_id number path '$.document_id',
                 document_version_id number path '$.document_version_id',
                 chunk_id number path '$.chunk_id',
                 chunk_no number path '$.chunk_no',
                 relevance_score number path '$.relevance_score'
               )
             ) jt
        join orac_code.knowledge_native_searchable_chunks_v chunk
          on chunk.chunk_id = jt.chunk_id
         and chunk.document_id = jt.document_id
         and chunk.document_version_id = jt.document_version_id
         and chunk.chunk_no = jt.chunk_no
       where chunk.knowledge_scope_id = l_scope_id
         and jt.ordinal <= 6
       order by jt.ordinal;
  exception
    when no_data_found then
      raise_application_error(-20712, 'KNOWLEDGE_APEX_NOT_AUTHORISED');
  end read_search;
end knowledge_apex_search_api;
/
--rollback drop package body orac_code.knowledge_apex_search_api;
