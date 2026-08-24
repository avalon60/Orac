--liquibase formatted sql

--changeset clive:create_constraint_orac_core_kn_docvtag_uk1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_DOCVTAG_UK1';

alter table orac_core.knowledge_document_version_tags add constraint kn_docvtag_uk1
  unique (document_version_id, tag_order)
  using index orac_core.kn_docvtag_uk1_idx;

--rollback alter table orac_core.knowledge_document_version_tags drop constraint kn_docvtag_uk1;
