--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Adds governed annotations for llm_capabilities.

--changeset clive:annotate_orac_core_llm_capabilities context:core labels:core stripComments:false runOnChange:true
alter table orac_core.llm_capabilities annotations (
  add if not exists display_name 'LLM capability',
  add if not exists plural_display_name 'LLM capabilities'
);

--changeset clive:annotate_orac_core_llm_cap_capability_code context:core labels:core stripComments:false runOnChange:true
alter table orac_core.llm_capabilities modify capability_code annotations (
  add if not exists display_name 'Capability code',
  add if not exists semantic_role 'primary_key',
  add if not exists data_kind 'code'
);

