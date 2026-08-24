--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Defines a safe read projection for controlled LLM metadata.

--changeset clive:create_view_orac_code_llm_model_input_support_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_code.llm_model_input_support_v as
select inp.model_cap_input_id
     , inp.model_capability_id
     , ev.llm_id
     , ev.provider_code
     , ev.model_identity
     , ev.capability_code
     , ev.evidence_state
     , inp.representation_code
     , inp.media_type
     , inp.effective_from
     , inp.effective_to
  from orac_api.llm_model_cap_inputs_v inp
  join orac_code.llm_current_model_evidence_v ev
    on ev.model_capability_id = inp.model_capability_id
 where ev.evidence_state in (
         'MODEL_METADATA_VERIFIED',
         'BOUNDED_PROBE_VERIFIED'
       )
   and inp.effective_from <= systimestamp
   and (inp.effective_to is null or inp.effective_to > systimestamp);
--rollback drop view orac_code.llm_model_input_support_v;

