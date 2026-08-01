--liquibase formatted sql

--changeset clive:create_knowledge_tag_pks context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_constraints where owner = 'ORAC_CORE' and constraint_name in ('KN_TAG_PK','KN_DOCVTAG_PK');
alter table orac_core.knowledge_tags add constraint kn_tag_pk primary key (knowledge_tag_id) using index orac_core.kn_tag_pk;
alter table orac_core.knowledge_document_version_tags add constraint kn_docvtag_pk primary key (knowledge_document_version_tag_id) using index orac_core.kn_docvtag_pk;
--rollback alter table orac_core.knowledge_document_version_tags drop constraint kn_docvtag_pk; alter table orac_core.knowledge_tags drop constraint kn_tag_pk;
