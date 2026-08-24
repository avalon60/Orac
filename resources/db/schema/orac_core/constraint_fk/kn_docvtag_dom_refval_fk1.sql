--liquibase formatted sql

--changeset clive:create_constraint_orac_core_kn_docvtag_dom_refval_fk1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_DOCVTAG_DOM_REFVAL_FK1';

alter table orac_core.knowledge_document_version_tags
  add constraint kn_docvtag_dom_refval_fk1
  foreign key (doc_class_domain_code, doc_class_ref_value_code)
  references orac_core.domain_ref_values (domain_code, ref_value_code);

--rollback alter table orac_core.knowledge_document_version_tags drop constraint kn_docvtag_dom_refval_fk1;
