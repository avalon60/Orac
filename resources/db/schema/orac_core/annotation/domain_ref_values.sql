--liquibase formatted sql

--changeset clive:annotate_orac_core_domain_ref_values context:core labels:core stripComments:false runOnChange:true
alter table orac_core.domain_ref_values annotations (
  add if not exists display_name 'Domain reference value',
  add if not exists plural_display_name 'Domain reference values'
);

--changeset clive:annotate_orac_core_domain_ref_values_domain_code context:core labels:core stripComments:false runOnChange:true
alter table orac_core.domain_ref_values modify domain_code annotations (
  add if not exists display_name 'Domain code',
  add if not exists semantic_role 'foreign_key',
  add if not exists data_kind 'code',
  add if not exists rel_target 'orac_core.domain_codes.domain_code',
  add if not exists rel_type 'belongs_to',
  add if not exists rel_cardinality 'many_to_one',
  add if not exists rel_optionality 'required',
  add if not exists rel_basis 'constraint:dom_refval_dom_codes_fk1'
);

--changeset clive:annotate_orac_core_domain_ref_values_ref_value_code context:core labels:core stripComments:false runOnChange:true
alter table orac_core.domain_ref_values modify ref_value_code annotations (
  add if not exists display_name 'Reference value code',
  add if not exists semantic_role 'natural_key',
  add if not exists data_kind 'code'
);

--changeset clive:annotate_orac_core_domain_ref_values_parent_domain_code context:core labels:core stripComments:false runOnChange:true
alter table orac_core.domain_ref_values modify parent_domain_code annotations (
  add if not exists display_name 'Parent domain code',
  add if not exists semantic_role 'foreign_key',
  add if not exists data_kind 'code',
  add if not exists rel_target 'orac_core.domain_ref_values.domain_code',
  add if not exists rel_type 'belongs_to',
  add if not exists rel_cardinality 'many_to_one',
  add if not exists rel_optionality 'optional',
  add if not exists rel_basis 'constraint:dom_refval_dom_refval_fk1'
);

--changeset clive:annotate_orac_core_domain_ref_values_parent_ref_value_code context:core labels:core stripComments:false runOnChange:true
alter table orac_core.domain_ref_values modify parent_ref_value_code annotations (
  add if not exists display_name 'Parent reference value code',
  add if not exists semantic_role 'foreign_key',
  add if not exists data_kind 'code',
  add if not exists rel_target 'orac_core.domain_ref_values.ref_value_code',
  add if not exists rel_type 'belongs_to',
  add if not exists rel_cardinality 'many_to_one',
  add if not exists rel_optionality 'optional',
  add if not exists rel_basis 'constraint:dom_refval_dom_refval_fk1'
);

--changeset clive:annotate_orac_core_domain_ref_values_display_value context:core labels:core stripComments:false runOnChange:true
alter table orac_core.domain_ref_values modify display_value annotations (
  add if not exists display_name 'Display value',
  add if not exists data_kind 'text'
);
