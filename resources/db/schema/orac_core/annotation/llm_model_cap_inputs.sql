--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Adds governed annotations for llm_model_cap_inputs.

--changeset clive:annotate_orac_core_llm_model_cap_inputs context:core labels:core stripComments:false runOnChange:true
alter table orac_core.llm_model_cap_inputs annotations (
  add if not exists display_name 'LLM model capability input',
  add if not exists plural_display_name 'LLM model capability inputs'
);

--changeset clive:annotate_orac_core_llm_mcin_model_cap_input_id context:core labels:core stripComments:false runOnChange:true
alter table orac_core.llm_model_cap_inputs modify model_cap_input_id annotations (
  add if not exists display_name 'Model capability input identifier',
  add if not exists semantic_role 'primary_key',
  add if not exists data_kind 'identifier'
);

