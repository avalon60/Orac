--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 25-Oct-2026
-- Description: Lets Core business packages use the APEX search API view.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:grant_orac_api_knowledge_apex_search_requests_v_to_orac_code context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.knowledge_apex_search_requests_v to orac_code;
--rollback revoke select, insert, update, delete on orac_api.knowledge_apex_search_requests_v from orac_code;
