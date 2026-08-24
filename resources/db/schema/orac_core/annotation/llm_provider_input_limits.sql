--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Adds governed annotations for llm_provider_input_limits.

--changeset clive:annotate_orac_core_llm_provider_input_limits context:core labels:core stripComments:false runOnChange:true
alter table orac_core.llm_provider_input_limits annotations (
  add if not exists display_name 'LLM provider input limit',
  add if not exists plural_display_name 'LLM provider input limits'
);

--changeset clive:annotate_orac_core_llm_pilim_provider_input_limit_id context:core labels:core stripComments:false runOnChange:true
alter table orac_core.llm_provider_input_limits modify provider_input_limit_id annotations (
  add if not exists display_name 'Provider input limit identifier',
  add if not exists semantic_role 'primary_key',
  add if not exists data_kind 'identifier'
);

