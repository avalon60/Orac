--liquibase formatted sql

--changeset clive:annotate_orac_core_user_preferences_definition context:core labels:core stripComments:false runOnChange:true
alter table orac_core.user_preferences modify pref_key annotations (
  add if not exists display_name 'Preference key',
  add if not exists semantic_role 'foreign_key',
  add if not exists data_kind 'code',
  add if not exists rel_target 'orac_core.preference_definitions.pref_key',
  add if not exists rel_type 'belongs_to',
  add if not exists rel_cardinality 'many_to_one',
  add if not exists rel_optionality 'required',
  add if not exists rel_basis 'constraint:user_pref_prfdfn_fk1'
);
