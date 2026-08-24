--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Defines a safe read projection for controlled LLM metadata.

--changeset clive:create_view_orac_code_llm_input_limits_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_code.llm_input_limits_v as
select 'PROVIDER_TRANSPORT' limit_scope
     , provider_input_limit_id limit_id
     , provider_input_id parent_id
     , limit_dimension_ref_value_code limit_dimension
     , bound_operator_ref_value_code bound_operator
     , limit_value
     , limit_unit_ref_value_code limit_unit
     , effective_from
     , effective_to
  from orac_api.llm_provider_input_limits_v
union all
select 'MODEL_INPUT' limit_scope
     , model_input_limit_id limit_id
     , model_cap_input_id parent_id
     , limit_dimension_ref_value_code limit_dimension
     , bound_operator_ref_value_code bound_operator
     , limit_value
     , limit_unit_ref_value_code limit_unit
     , effective_from
     , effective_to
  from orac_api.llm_model_input_limits_v;
--rollback drop view orac_code.llm_input_limits_v;

