--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Exposes the llm_model_input_limits API projection.

--changeset clive:create_view_orac_api_llm_model_input_limits_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.llm_model_input_limits_v as
select model_input_limit_id
     , model_cap_input_id
     , limit_dimension_domain_code
     , limit_dimension_ref_value_code
     , bound_operator_domain_code
     , bound_operator_ref_value_code
     , limit_value
     , limit_unit_domain_code
     , limit_unit_ref_value_code
     , effective_from
     , effective_to
     , provenance
     , created_by
     , created_on
     , updated_by
     , updated_on
     , row_version
  from orac_core.llm_model_input_limits;
--rollback drop view orac_api.llm_model_input_limits_v;

