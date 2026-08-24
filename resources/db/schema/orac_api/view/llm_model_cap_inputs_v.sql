--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Exposes the llm_model_cap_inputs API projection.

--changeset clive:create_view_orac_api_llm_model_cap_inputs_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.llm_model_cap_inputs_v as
select model_cap_input_id
     , model_capability_id
     , representation_code
     , media_type
     , effective_from
     , effective_to
     , provenance
     , created_by
     , created_on
     , updated_by
     , updated_on
     , row_version
  from orac_core.llm_model_cap_inputs;
--rollback drop view orac_api.llm_model_cap_inputs_v;

