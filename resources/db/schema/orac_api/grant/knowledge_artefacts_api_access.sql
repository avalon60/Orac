--liquibase formatted sql
-- Author: clive
-- Date: 2026-08-12
-- Description: Grants the business layer controlled knowledge artefact access.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:grant_read_orac_api_knowledge_artefacts_v_to_orac_code context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.knowledge_artefacts_v to orac_code with grant option;
--rollback revoke read on orac_api.knowledge_artefacts_v from orac_code;

--changeset clive:grant_execute_orac_api_knowledge_artefacts_tapi_to_orac_code context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.knowledge_artefacts_tapi to orac_code;
--rollback revoke execute on orac_api.knowledge_artefacts_tapi from orac_code;
