--liquibase formatted sql

--changeset clive:annotate_orac_core_message_embeddings_distance_metric context:core labels:core stripComments:false runOnChange:true
alter table orac_core.message_embeddings modify vector_distance_metric_domain_code annotations (
  add if not exists display_name 'Vector distance metric domain',
  add if not exists semantic_role 'foreign_key',
  add if not exists data_kind 'code',
  add if not exists code_set_ref 'codes:VECTOR_DISTANCE_METRIC',
  add if not exists rel_target 'orac_core.domain_ref_values.domain_code',
  add if not exists rel_type 'classifies',
  add if not exists rel_cardinality 'many_to_one',
  add if not exists rel_optionality 'required',
  add if not exists rel_basis 'constraint:mesg_emb_dom_refval_fk1'
);

--changeset clive:annotate_orac_core_message_embeddings_distance_metric_value context:core labels:core stripComments:false runOnChange:true
alter table orac_core.message_embeddings modify vector_distance_metric_ref_value_code annotations (
  add if not exists display_name 'Vector distance metric',
  add if not exists semantic_role 'foreign_key',
  add if not exists data_kind 'code',
  add if not exists code_set_ref 'codes:VECTOR_DISTANCE_METRIC',
  add if not exists rel_target 'orac_core.domain_ref_values.ref_value_code',
  add if not exists rel_type 'classifies',
  add if not exists rel_cardinality 'many_to_one',
  add if not exists rel_optionality 'required',
  add if not exists rel_basis 'constraint:mesg_emb_dom_refval_fk1'
);
