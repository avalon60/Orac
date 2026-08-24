--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Adds governed annotations for llm_input_media_types.

--changeset clive:annotate_orac_core_llm_input_media_types context:core labels:core stripComments:false runOnChange:true
alter table orac_core.llm_input_media_types annotations (
  add if not exists display_name 'LLM input media type',
  add if not exists plural_display_name 'LLM input media types'
);

--changeset clive:annotate_orac_core_llm_mtype_media_type context:core labels:core stripComments:false runOnChange:true
alter table orac_core.llm_input_media_types modify media_type annotations (
  add if not exists display_name 'Media type',
  add if not exists semantic_role 'primary_key',
  add if not exists data_kind 'code'
);

