--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 29-Aug-2026
-- Description: Grants the runtime read-only access to current model tool evidence.

--changeset clive:grant_read_orac_code_governed_retrieval_capability_to_orac_p2a context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.llm_current_model_evidence_v to orac;
--rollback revoke read on orac_code.llm_current_model_evidence_v from orac;
