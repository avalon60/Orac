--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Exposes the llm_provider_inputs API projection.

--changeset clive:create_view_orac_api_llm_provider_inputs_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.llm_provider_inputs_v as
select provider_input_id
     , provider_code
     , representation_code
     , media_type
     , evidence_state_domain_code
     , evidence_state_ref_value_code
     , adapter_status_domain_code
     , adapter_status_ref_value_code
     , source_uri
     , checked_on
     , effective_from
     , effective_to
     , reviewed_by
     , provenance
     , rejection_reason
     , native_properties
     , created_by
     , created_on
     , updated_by
     , updated_on
     , row_version
  from orac_core.llm_provider_inputs;
--rollback drop view orac_api.llm_provider_inputs_v;

