--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 25-Oct-2026
-- Description: Allows the API layer to maintain Core APEX search requests.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:grant_orac_core_knowledge_apex_search_requests_to_orac_api context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.knowledge_apex_search_requests to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.knowledge_apex_search_requests from orac_api;
