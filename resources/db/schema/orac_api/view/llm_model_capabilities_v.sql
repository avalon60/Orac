--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Exposes the llm_model_capabilities API projection.

--changeset clive:create_view_orac_api_llm_model_capabilities_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.llm_model_capabilities_v as
select model_capability_id
     , llm_id
     , provider_code
     , model_identity
     , capability_code
     , evidence_state_domain_code
     , evidence_state_ref_value_code
     , model_revision
     , source_reference
     , checked_on
     , effective_from
     , effective_to
     , reviewed_by
     , provenance
     , fixture_identity
     , probe_identity
     , acceptance_criteria_ref
     , rejection_reason
     , native_properties
     , created_by
     , created_on
     , updated_by
     , updated_on
     , row_version
  from orac_core.llm_model_capabilities;
--rollback drop view orac_api.llm_model_capabilities_v;

