--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Adds governed annotations for llm_input_representations.

--changeset clive:annotate_orac_core_llm_input_representations context:core labels:core stripComments:false runOnChange:true
alter table orac_core.llm_input_representations annotations (
  add if not exists display_name 'LLM input representation',
  add if not exists plural_display_name 'LLM input representations'
);

--changeset clive:annotate_orac_core_llm_inrep_representation_code context:core labels:core stripComments:false runOnChange:true
alter table orac_core.llm_input_representations modify representation_code annotations (
  add if not exists display_name 'Representation code',
  add if not exists semantic_role 'primary_key',
  add if not exists data_kind 'code'
);

