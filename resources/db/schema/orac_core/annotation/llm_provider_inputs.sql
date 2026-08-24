--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Adds governed annotations for llm_provider_inputs.

--changeset clive:annotate_orac_core_llm_provider_inputs context:core labels:core stripComments:false runOnChange:true
alter table orac_core.llm_provider_inputs annotations (
  add if not exists display_name 'LLM provider input',
  add if not exists plural_display_name 'LLM provider inputs'
);

--changeset clive:annotate_orac_core_llm_prvin_provider_input_id context:core labels:core stripComments:false runOnChange:true
alter table orac_core.llm_provider_inputs modify provider_input_id annotations (
  add if not exists display_name 'Provider input identifier',
  add if not exists semantic_role 'primary_key',
  add if not exists data_kind 'identifier'
);

