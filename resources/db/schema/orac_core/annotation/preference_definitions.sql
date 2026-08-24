--liquibase formatted sql

--changeset clive:annotate_orac_core_prfdfn_pref_value_type context:core labels:core stripComments:false runOnChange:true
alter table orac_core.preference_definitions modify pref_value_type_domain_code annotations (
  add if not exists display_name 'Preference value type domain',
  add if not exists semantic_role 'foreign_key',
  add if not exists data_kind 'code',
  add if not exists code_set_ref 'codes:PREF_VALUE_TYPE',
  add if not exists rel_target 'orac_core.domain_ref_values.domain_code',
  add if not exists rel_type 'classifies',
  add if not exists rel_cardinality 'many_to_one',
  add if not exists rel_optionality 'required',
  add if not exists rel_basis 'constraint:prfdfn_dom_refval_fk1'
);

--changeset clive:annotate_orac_core_prfdfn_pref_value_type_value context:core labels:core stripComments:false runOnChange:true
alter table orac_core.preference_definitions modify pref_value_type_ref_value_code annotations (
  add if not exists display_name 'Preference value type',
  add if not exists semantic_role 'foreign_key',
  add if not exists data_kind 'code',
  add if not exists code_set_ref 'codes:PREF_VALUE_TYPE',
  add if not exists rel_target 'orac_core.domain_ref_values.ref_value_code',
  add if not exists rel_type 'classifies',
  add if not exists rel_cardinality 'many_to_one',
  add if not exists rel_optionality 'required',
  add if not exists rel_basis 'constraint:prfdfn_dom_refval_fk1'
);

--changeset clive:annotate_orac_core_prfdfn_pref_control_type context:core labels:core stripComments:false runOnChange:true
alter table orac_core.preference_definitions modify pref_control_type_domain_code annotations (
  add if not exists display_name 'Preference control type domain',
  add if not exists semantic_role 'foreign_key',
  add if not exists data_kind 'code',
  add if not exists code_set_ref 'codes:PREF_CONTROL_TYPE',
  add if not exists rel_target 'orac_core.domain_ref_values.domain_code',
  add if not exists rel_type 'classifies',
  add if not exists rel_cardinality 'many_to_one',
  add if not exists rel_optionality 'required',
  add if not exists rel_basis 'constraint:prfdfn_dom_refval_fk2'
);

--changeset clive:annotate_orac_core_prfdfn_pref_control_type_value context:core labels:core stripComments:false runOnChange:true
alter table orac_core.preference_definitions modify pref_control_type_ref_value_code annotations (
  add if not exists display_name 'Preference control type',
  add if not exists semantic_role 'foreign_key',
  add if not exists data_kind 'code',
  add if not exists code_set_ref 'codes:PREF_CONTROL_TYPE',
  add if not exists rel_target 'orac_core.domain_ref_values.ref_value_code',
  add if not exists rel_type 'classifies',
  add if not exists rel_cardinality 'many_to_one',
  add if not exists rel_optionality 'required',
  add if not exists rel_basis 'constraint:prfdfn_dom_refval_fk2'
);

--changeset clive:annotate_orac_core_prfdfn_pref_lov_type context:core labels:core stripComments:false runOnChange:true
alter table orac_core.preference_definitions modify pref_lov_type_domain_code annotations (
  add if not exists display_name 'Preference LOV type domain',
  add if not exists semantic_role 'foreign_key',
  add if not exists data_kind 'code',
  add if not exists code_set_ref 'codes:PREF_LOV_TYPE',
  add if not exists rel_target 'orac_core.domain_ref_values.domain_code',
  add if not exists rel_type 'classifies',
  add if not exists rel_cardinality 'many_to_one',
  add if not exists rel_optionality 'required',
  add if not exists rel_basis 'constraint:prfdfn_dom_refval_fk3'
);

--changeset clive:annotate_orac_core_prfdfn_pref_lov_type_value context:core labels:core stripComments:false runOnChange:true
alter table orac_core.preference_definitions modify pref_lov_type_ref_value_code annotations (
  add if not exists display_name 'Preference LOV type',
  add if not exists semantic_role 'foreign_key',
  add if not exists data_kind 'code',
  add if not exists code_set_ref 'codes:PREF_LOV_TYPE',
  add if not exists rel_target 'orac_core.domain_ref_values.ref_value_code',
  add if not exists rel_type 'classifies',
  add if not exists rel_cardinality 'many_to_one',
  add if not exists rel_optionality 'optional',
  add if not exists rel_basis 'constraint:prfdfn_dom_refval_fk3'
);
