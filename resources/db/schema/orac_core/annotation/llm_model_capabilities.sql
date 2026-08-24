--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Adds governed annotations for llm_model_capabilities.

--changeset clive:annotate_orac_core_llm_model_capabilities context:core labels:core stripComments:false runOnChange:true
alter table orac_core.llm_model_capabilities annotations (
  add if not exists display_name 'LLM model capability evidence',
  add if not exists plural_display_name 'LLM model capability evidence'
);

--changeset clive:annotate_orac_core_llm_modcap_model_capability_id context:core labels:core stripComments:false runOnChange:true
alter table orac_core.llm_model_capabilities modify model_capability_id annotations (
  add if not exists display_name 'Model capability identifier',
  add if not exists semantic_role 'primary_key',
  add if not exists data_kind 'identifier'
);

