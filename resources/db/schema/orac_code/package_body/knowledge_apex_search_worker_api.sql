--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 25-Oct-2026
-- Description: Claims and completes transient searches for the trusted Core worker.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_package_body_orac_code_knowledge_apex_search_worker_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package body orac_code.knowledge_apex_search_worker_api as
  procedure claim_next(
    p_worker_id in varchar2,
    p_request_id out number,
    p_lease_token out varchar2,
    p_username out varchar2,
    p_plugin_id out varchar2,
    p_query out varchar2
  )
  is
    cursor c_requests is
      select search_request_id, username, application_id,
             plugin_registry_id, knowledge_scope_id, query_text, attempts
        from orac_api.knowledge_apex_search_requests_v
       where expires_on > systimestamp
         and (status_code = 'QUEUED'
              or (status_code = 'PROCESSING'
                  and lease_expires_on < systimestamp))
       order by created_on, search_request_id
       for update skip locked;
    l_plugin_id orac_api.plugin_registry_v.plugin_id%type;
  begin
    p_request_id := null;
    p_lease_token := null;
    p_username := null;
    p_plugin_id := null;
    p_query := null;
    if nullif(trim(p_worker_id), '') is null or length(p_worker_id) > 255
    then
      raise_application_error(-20720, 'KNOWLEDGE_APEX_WORKER_INVALID');
    end if;
    for rec in c_requests loop
      if rec.attempts >= 3 then
        update orac_api.knowledge_apex_search_requests_v
           set status_code = 'FAILED', failure_code = 'RETRY_EXHAUSTED',
               completed_on = systimestamp, lease_owner = null,
               lease_token = null, lease_expires_on = null
         where search_request_id = rec.search_request_id;
        continue;
      end if;
      begin
        select plugin.plugin_id into l_plugin_id
          from orac_code.plugin_registry_v plugin
         where plugin.plugin_registry_id = rec.plugin_registry_id
           and plugin.knowledge_scope_id = rec.knowledge_scope_id
           and plugin.enabled = 'Y'
           and plugin.removal_id is null;
        if orac_code.plugin_apex_app_auth_api.plugin_is_available(
             l_plugin_id, rec.application_id
           ) <> 1
           or nvl(orac_code.rag_usage_authorization_api.authorization_result_by_id(
             rec.username, rec.knowledge_scope_id
           ), 'X') <> 'RAG_USAGE_GRANTED'
        then
          raise no_data_found;
        end if;
      exception
        when no_data_found then
          update orac_api.knowledge_apex_search_requests_v
             set status_code = 'FAILED', failure_code = 'NOT_AUTHORISED',
                 completed_on = systimestamp
           where search_request_id = rec.search_request_id;
          continue;
      end;
      p_request_id := rec.search_request_id;
      p_lease_token := rawtohex(sys_guid());
      p_username := rec.username;
      p_plugin_id := l_plugin_id;
      p_query := rec.query_text;
      update orac_api.knowledge_apex_search_requests_v
         set status_code = 'PROCESSING', attempts = rec.attempts + 1,
             lease_owner = p_worker_id, lease_token = p_lease_token,
             lease_expires_on = systimestamp + interval '5' minute,
             failure_code = null
       where search_request_id = p_request_id;
      exit;
    end loop;
  end claim_next;

  procedure complete_search(
    p_request_id in number,
    p_worker_id in varchar2,
    p_lease_token in varchar2,
    p_result_refs_json in clob
  )
  is
    l_count number;
    l_username varchar2(128 char);
    l_scope_id number;
  begin
    if p_result_refs_json is null or p_result_refs_json is not json
    then
      raise_application_error(-20721, 'KNOWLEDGE_APEX_RESULT_INVALID');
    end if;
    select count(*) into l_count
      from json_table(p_result_refs_json, '$[*]' columns (chunk_id number path '$.chunk_id'));
    if l_count > 6 or dbms_lob.getlength(p_result_refs_json) > 4096
    then
      raise_application_error(-20721, 'KNOWLEDGE_APEX_RESULT_INVALID');
    end if;
    select username, knowledge_scope_id into l_username, l_scope_id
      from orac_api.knowledge_apex_search_requests_v
     where search_request_id = p_request_id
       and status_code = 'PROCESSING'
       and lease_owner = p_worker_id
       and lease_token = p_lease_token
       and lease_expires_on > systimestamp
       and expires_on > systimestamp
       for update;
    if nvl(orac_code.rag_usage_authorization_api.authorization_result_by_id(
         l_username, l_scope_id
       ), 'X') <> 'RAG_USAGE_GRANTED'
    then
      raise_application_error(-20722, 'KNOWLEDGE_APEX_NOT_AUTHORISED');
    end if;
    update orac_api.knowledge_apex_search_requests_v
       set status_code = case when l_count = 0 then 'NO_EVIDENCE' else 'COMPLETED' end,
           result_refs_json = p_result_refs_json,
           completed_on = systimestamp, lease_owner = null,
           lease_token = null, lease_expires_on = null
     where search_request_id = p_request_id;
  exception
    when no_data_found then
      raise_application_error(-20723, 'KNOWLEDGE_APEX_LEASE_INVALID');
  end complete_search;

  procedure fail_search(
    p_request_id in number,
    p_worker_id in varchar2,
    p_lease_token in varchar2,
    p_failure_code in varchar2,
    p_retryable_yn in varchar2
  )
  is
  begin
    update orac_api.knowledge_apex_search_requests_v
       set status_code = case when p_retryable_yn = 'Y' and attempts < 3
                              and expires_on > systimestamp
                              then 'QUEUED' else 'FAILED' end,
           failure_code = substr(p_failure_code, 1, 100),
           completed_on = case when p_retryable_yn = 'Y' and attempts < 3
                                and expires_on > systimestamp
                                then null else systimestamp end,
           lease_owner = null, lease_token = null, lease_expires_on = null
     where search_request_id = p_request_id
       and status_code = 'PROCESSING'
       and lease_owner = p_worker_id
       and lease_token = p_lease_token;
    if sql%rowcount <> 1
    then
      raise_application_error(-20723, 'KNOWLEDGE_APEX_LEASE_INVALID');
    end if;
  end fail_search;

  procedure purge_expired
  is
  begin
    delete from orac_api.knowledge_apex_search_requests_v
     where expires_on <= systimestamp;
  end purge_expired;
end knowledge_apex_search_worker_api;
/
--rollback drop package body orac_code.knowledge_apex_search_worker_api;
