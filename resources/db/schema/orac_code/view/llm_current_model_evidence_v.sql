--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Defines a safe read projection for controlled LLM metadata.

--changeset clive:create_view_orac_code_llm_current_model_evidence_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_code.llm_current_model_evidence_v as
select model_capability_id
     , llm_id
     , provider_code
     , model_identity
     , capability_code
     , evidence_state_ref_value_code evidence_state
     , model_revision
     , source_reference
     , checked_on
     , effective_from
     , reviewed_by
     , fixture_identity
     , probe_identity
     , acceptance_criteria_ref
     , rejection_reason
  from orac_api.llm_model_capabilities_v
 where effective_from <= systimestamp
   and (effective_to is null or effective_to > systimestamp);
--rollback drop view orac_code.llm_current_model_evidence_v;

