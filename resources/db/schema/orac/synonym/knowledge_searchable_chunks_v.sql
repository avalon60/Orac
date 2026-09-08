--liquibase formatted sql

--changeset clive:drop_synonym_orac_knowledge_searchable_chunks_v_p1_06 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_synonyms where owner = 'ORAC' and synonym_name = 'KNOWLEDGE_SEARCHABLE_CHUNKS_V';
drop synonym orac.knowledge_searchable_chunks_v;
--rollback create synonym orac.knowledge_searchable_chunks_v for orac_code.knowledge_searchable_chunks_v;
