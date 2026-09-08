--liquibase formatted sql
-- Author: clive
-- Date: 31-Aug-2026
-- Description: Grants the narrow capability evidence API to the Orac runtime.

--changeset clive:grant_execute_llm_capability_evidence_api_to_orac context:core labels:core stripComments:false runOnChange:true
grant execute on orac_code.llm_capability_evidence_api to orac;
--rollback revoke execute on orac_code.llm_capability_evidence_api from orac;
