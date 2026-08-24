--liquibase formatted sql

--changeset clive:create_index_orac_core_kn_docvtag_uk1_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_DOCVTAG_UK1_IDX';

create unique index orac_core.kn_docvtag_uk1_idx
  on orac_core.knowledge_document_version_tags (document_version_id, tag_order);

--rollback drop index orac_core.kn_docvtag_uk1_idx;
