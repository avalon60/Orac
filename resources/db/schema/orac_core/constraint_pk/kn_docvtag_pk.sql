--liquibase formatted sql

--changeset clive:create_constraint_orac_core_kn_docvtag_pk context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_DOCVTAG_PK';

alter table orac_core.knowledge_document_version_tags add constraint kn_docvtag_pk
  primary key (document_version_id, doc_class_domain_code, doc_class_ref_value_code)
  using index orac_core.kn_docvtag_pk;

--rollback alter table orac_core.knowledge_document_version_tags drop constraint kn_docvtag_pk;
