--liquibase formatted sql

--changeset clive:create_synonym_orac_knowledge_searchable_chunks_v context:core labels:core stripComments:false runOnChange:true
create or replace synonym orac.knowledge_searchable_chunks_v
  for orac_code.knowledge_searchable_chunks_v;
--rollback drop synonym orac.knowledge_searchable_chunks_v;
