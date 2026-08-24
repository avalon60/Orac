--liquibase formatted sql

--changeset clive:annotate_orac_core_knowledge_document_version_tags context:core labels:core stripComments:false runOnChange:true
alter table orac_core.knowledge_document_version_tags annotations (
  add if not exists display_name 'Knowledge document version classification',
  add if not exists plural_display_name 'Knowledge document version classifications'
);

--changeset clive:annotate_orac_core_kn_docvtag_document_version_id context:core labels:core stripComments:false runOnChange:true
alter table orac_core.knowledge_document_version_tags
  modify document_version_id annotations (
    add if not exists display_name 'Document version',
    add if not exists semantic_role 'foreign_key',
    add if not exists data_kind 'identifier',
    add if not exists rel_target 'orac_core.knowledge_document_versions.document_version_id',
    add if not exists rel_type 'belongs_to',
    add if not exists rel_cardinality 'many_to_one',
    add if not exists rel_optionality 'required',
    add if not exists rel_basis 'constraint:kn_docvtag_kn_docver_fk1'
  );

--changeset clive:annotate_orac_core_kn_docvtag_doc_class_domain_code context:core labels:core stripComments:false runOnChange:true
alter table orac_core.knowledge_document_version_tags
  modify doc_class_domain_code annotations (
    add if not exists display_name 'Document classification domain',
    add if not exists semantic_role 'foreign_key',
    add if not exists data_kind 'code',
    add if not exists code_set_ref 'codes:DOC_CLASS',
    add if not exists rel_target 'orac_core.domain_ref_values.domain_code',
    add if not exists rel_type 'classifies',
    add if not exists rel_cardinality 'many_to_one',
    add if not exists rel_optionality 'required',
    add if not exists rel_basis 'constraint:kn_docvtag_dom_refval_fk1'
  );

--changeset clive:annotate_orac_core_kn_docvtag_doc_class_ref_value_code context:core labels:core stripComments:false runOnChange:true
alter table orac_core.knowledge_document_version_tags
  modify doc_class_ref_value_code annotations (
    add if not exists display_name 'Document classification',
    add if not exists semantic_role 'foreign_key',
    add if not exists data_kind 'code',
    add if not exists code_set_ref 'codes:DOC_CLASS',
    add if not exists rel_target 'orac_core.domain_ref_values.ref_value_code',
    add if not exists rel_type 'classifies',
    add if not exists rel_cardinality 'many_to_one',
    add if not exists rel_optionality 'required',
    add if not exists rel_basis 'constraint:kn_docvtag_dom_refval_fk1'
  );
