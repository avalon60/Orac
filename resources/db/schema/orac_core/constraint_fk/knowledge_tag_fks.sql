--liquibase formatted sql

--changeset clive:create_knowledge_tag_fks context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_constraints where owner = 'ORAC_CORE' and constraint_name in ('KN_DOCVTAG_DOCVER_FK','KN_DOCVTAG_TAG_FK');
alter table orac_core.knowledge_document_version_tags add constraint kn_docvtag_docver_fk foreign key (document_version_id) references orac_core.knowledge_document_versions (document_version_id);
alter table orac_core.knowledge_document_version_tags add constraint kn_docvtag_tag_fk foreign key (knowledge_tag_id) references orac_core.knowledge_tags (knowledge_tag_id);
--rollback alter table orac_core.knowledge_document_version_tags drop constraint kn_docvtag_tag_fk; alter table orac_core.knowledge_document_version_tags drop constraint kn_docvtag_docver_fk;
