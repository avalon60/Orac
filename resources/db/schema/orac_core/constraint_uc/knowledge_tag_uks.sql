--liquibase formatted sql

--changeset clive:create_knowledge_tag_uks context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_constraints where owner = 'ORAC_CORE' and constraint_name in ('KN_TAG_UK1','KN_DOCVTAG_UK1','KN_DOCVTAG_UK2');
alter table orac_core.knowledge_tags add constraint kn_tag_uk1 unique (tag_code) using index orac_core.kn_tag_uk1_idx;
alter table orac_core.knowledge_document_version_tags add constraint kn_docvtag_uk1 unique (document_version_id, knowledge_tag_id) using index orac_core.kn_docvtag_uk1_idx;
alter table orac_core.knowledge_document_version_tags add constraint kn_docvtag_uk2 unique (document_version_id, tag_order) using index orac_core.kn_docvtag_uk2_idx;
--rollback alter table orac_core.knowledge_document_version_tags drop constraint kn_docvtag_uk2; alter table orac_core.knowledge_document_version_tags drop constraint kn_docvtag_uk1; alter table orac_core.knowledge_tags drop constraint kn_tag_uk1;
