--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Defines a safe read projection for controlled LLM metadata.

--changeset clive:create_view_orac_code_llm_provider_input_support_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_code.llm_provider_input_support_v as
select provider_input_id
     , provider_code
     , representation_code
     , media_type
     , evidence_state_ref_value_code evidence_state
     , adapter_status_ref_value_code adapter_support_status
     , source_uri
     , checked_on
     , effective_from
     , effective_to
  from orac_api.llm_provider_inputs_v;
--rollback drop view orac_code.llm_provider_input_support_v;

