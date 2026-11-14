--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 25-Oct-2026
-- Description: Grants worker-only APEX search operations to the trusted runtime.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:grant_orac_code_knowledge_apex_search_worker_api_to_orac context:core labels:core stripComments:false runOnChange:true
grant execute on orac_code.knowledge_apex_search_worker_api to orac;
--rollback revoke execute on orac_code.knowledge_apex_search_worker_api from orac;
