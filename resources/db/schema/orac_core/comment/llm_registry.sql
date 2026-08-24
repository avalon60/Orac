--liquibase formatted sql

--changeset clive:comment_orac_core_comment_llm_registry context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.llm_registry is
  'Registry of available large language models (LLMs) and their configuration.'
;

comment on column orac_core.llm_registry.llm_id is
  'Primary key for the orac_core.llm_registry table.'
;

comment on column orac_core.llm_registry.name is
  'Human-readable unique name for the model configuration.'
;

comment on column orac_core.llm_registry.provider is
  'Reviewed provider adapter code from orac_core.llm_providers.'
;

comment on column orac_core.llm_registry.model is
  'Provider model identifier.'
;

comment on column orac_core.llm_registry.llm_context_policy_domain_code is
  'Fixed LLM_CONTEXT_POLICY reference domain for the model context policy.'
;

comment on column orac_core.llm_registry.llm_context_policy_ref_value_code is
  'How conversation state is managed for this model.'
;

comment on column orac_core.llm_registry.max_context_tokens is
  'Maximum supported context window in tokens.'
;

comment on column orac_core.llm_registry.properties is
  'Legacy compatibility JSON; controlled capability, evidence, locality, MIME, revision, and limits metadata is stored relationally.'
;
