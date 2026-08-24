--liquibase formatted sql

--changeset clive:annotate_orac_core_llm_registry_context_policy context:core labels:core stripComments:false runOnChange:true
alter table orac_core.llm_registry modify llm_context_policy_domain_code annotations (
  add if not exists display_name 'LLM context policy domain',
  add if not exists semantic_role 'foreign_key',
  add if not exists data_kind 'code',
  add if not exists code_set_ref 'codes:LLM_CONTEXT_POLICY',
  add if not exists rel_target 'orac_core.domain_ref_values.domain_code',
  add if not exists rel_type 'classifies',
  add if not exists rel_cardinality 'many_to_one',
  add if not exists rel_optionality 'required',
  add if not exists rel_basis 'constraint:llm_reg_dom_refval_fk1'
);

--changeset clive:annotate_orac_core_llm_registry_context_policy_value context:core labels:core stripComments:false runOnChange:true
alter table orac_core.llm_registry modify llm_context_policy_ref_value_code annotations (
  add if not exists display_name 'LLM context policy',
  add if not exists semantic_role 'foreign_key',
  add if not exists data_kind 'code',
  add if not exists code_set_ref 'codes:LLM_CONTEXT_POLICY',
  add if not exists rel_target 'orac_core.domain_ref_values.ref_value_code',
  add if not exists rel_type 'classifies',
  add if not exists rel_cardinality 'many_to_one',
  add if not exists rel_optionality 'required',
  add if not exists rel_basis 'constraint:llm_reg_dom_refval_fk1'
);

--changeset clive:annotate_orac_core_llm_registry_provider context:core labels:core stripComments:false runOnChange:true
alter table orac_core.llm_registry modify provider annotations (
  add if not exists display_name 'Provider',
  add if not exists semantic_role 'foreign_key',
  add if not exists data_kind 'code',
  add if not exists rel_target 'orac_core.llm_providers.provider_code',
  add if not exists rel_type 'belongs_to',
  add if not exists rel_cardinality 'many_to_one',
  add if not exists rel_optionality 'required',
  add if not exists rel_basis 'constraint:llm_reg_llm_prov_fk1'
);
