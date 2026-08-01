--liquibase formatted sql

--changeset clive:create_knowledge_tag_indexes context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_indexes where owner = 'ORAC_CORE' and index_name in ('KN_TAG_PK','KN_TAG_UK1_IDX','KN_DOCVTAG_PK','KN_DOCVTAG_UK1_IDX','KN_DOCVTAG_UK2_IDX');
create unique index orac_core.kn_tag_pk on orac_core.knowledge_tags (knowledge_tag_id);
create unique index orac_core.kn_tag_uk1_idx on orac_core.knowledge_tags (tag_code);
create unique index orac_core.kn_docvtag_pk on orac_core.knowledge_document_version_tags (knowledge_document_version_tag_id);
create unique index orac_core.kn_docvtag_uk1_idx on orac_core.knowledge_document_version_tags (document_version_id, knowledge_tag_id);
create unique index orac_core.kn_docvtag_uk2_idx on orac_core.knowledge_document_version_tags (document_version_id, tag_order);
--rollback drop index orac_core.kn_docvtag_uk2_idx; drop index orac_core.kn_docvtag_uk1_idx; drop index orac_core.kn_docvtag_pk; drop index orac_core.kn_tag_uk1_idx; drop index orac_core.kn_tag_pk;
