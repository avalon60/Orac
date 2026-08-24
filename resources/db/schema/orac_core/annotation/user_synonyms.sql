--liquibase formatted sql

--changeset clive:annotate_orac_core_user_synonyms_alias_type context:core labels:core stripComments:false runOnChange:true
alter table orac_core.user_synonyms modify user_alias_type_domain_code annotations (
  add if not exists display_name 'User alias type domain',
  add if not exists semantic_role 'foreign_key',
  add if not exists data_kind 'code',
  add if not exists code_set_ref 'codes:USER_ALIAS_TYPE',
  add if not exists rel_target 'orac_core.domain_ref_values.domain_code',
  add if not exists rel_type 'classifies',
  add if not exists rel_cardinality 'many_to_one',
  add if not exists rel_optionality 'required',
  add if not exists rel_basis 'constraint:user_syns_dom_refval_fk1'
);

--changeset clive:annotate_orac_core_user_synonyms_alias_type_value context:core labels:core stripComments:false runOnChange:true
alter table orac_core.user_synonyms modify user_alias_type_ref_value_code annotations (
  add if not exists display_name 'User alias type',
  add if not exists semantic_role 'foreign_key',
  add if not exists data_kind 'code',
  add if not exists code_set_ref 'codes:USER_ALIAS_TYPE',
  add if not exists rel_target 'orac_core.domain_ref_values.ref_value_code',
  add if not exists rel_type 'classifies',
  add if not exists rel_cardinality 'many_to_one',
  add if not exists rel_optionality 'required',
  add if not exists rel_basis 'constraint:user_syns_dom_refval_fk1'
);
