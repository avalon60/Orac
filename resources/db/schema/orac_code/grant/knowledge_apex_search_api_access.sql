--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 25-Oct-2026
-- Description: Grants only the APEX search surface to the parsing schema.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:grant_orac_code_knowledge_apex_search_api_to_orac_apx_pub context:core labels:core stripComments:false runOnChange:true
grant execute on orac_code.knowledge_apex_search_api to orac_apx_pub;
--rollback revoke execute on orac_code.knowledge_apex_search_api from orac_apx_pub;
