--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 25-Oct-2026
-- Description: Defines Core worker operations for queued plugin APEX searches.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_package_spec_orac_code_knowledge_apex_search_worker_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package orac_code.knowledge_apex_search_worker_api authid definer as
  procedure claim_next(
    p_worker_id in varchar2,
    p_request_id out number,
    p_lease_token out varchar2,
    p_username out varchar2,
    p_plugin_id out varchar2,
    p_query out varchar2
  );

  procedure complete_search(
    p_request_id in number,
    p_worker_id in varchar2,
    p_lease_token in varchar2,
    p_result_refs_json in clob
  );

  procedure fail_search(
    p_request_id in number,
    p_worker_id in varchar2,
    p_lease_token in varchar2,
    p_failure_code in varchar2,
    p_retryable_yn in varchar2
  );

  procedure purge_expired;
end knowledge_apex_search_worker_api;
/
--rollback drop package orac_code.knowledge_apex_search_worker_api;
