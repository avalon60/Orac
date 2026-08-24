--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Adds governed annotations for llm_providers.

--changeset clive:annotate_orac_core_llm_providers context:core labels:core stripComments:false runOnChange:true
alter table orac_core.llm_providers annotations (
  add if not exists display_name 'LLM provider',
  add if not exists plural_display_name 'LLM providers'
);

--changeset clive:annotate_orac_core_llm_prov_provider_code context:core labels:core stripComments:false runOnChange:true
alter table orac_core.llm_providers modify provider_code annotations (
  add if not exists display_name 'Provider code',
  add if not exists semantic_role 'primary_key',
  add if not exists data_kind 'code'
);

