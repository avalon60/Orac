--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 25-Oct-2026
-- Description: Defines a session-bound search interface for plugin APEX applications.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_package_spec_orac_code_knowledge_apex_search_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package orac_code.knowledge_apex_search_api authid definer as
  procedure submit_search(
    p_query in varchar2,
    p_request_id out number
  );

  procedure read_search(
    p_request_id in number,
    p_status out varchar2,
    p_results out sys_refcursor
  );
end knowledge_apex_search_api;
/
--rollback drop package orac_code.knowledge_apex_search_api;
