--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 25-Oct-2026
-- Description: Pass-through API view for Core APEX search requests.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_view_orac_api_knowledge_apex_search_requests_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.knowledge_apex_search_requests_v as
select search_request_id, username, application_id, plugin_registry_id,
       knowledge_scope_id, query_text, status_code, attempts, lease_owner,
       lease_token, lease_expires_on, result_refs_json, failure_code,
       created_on, completed_on, expires_on
  from orac_core.knowledge_apex_search_requests;
--rollback drop view orac_api.knowledge_apex_search_requests_v;
