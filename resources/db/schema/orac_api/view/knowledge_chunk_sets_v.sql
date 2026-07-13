--liquibase formatted sql

--changeset clive:create_view_orac_api_knowledge_chunk_sets_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.knowledge_chunk_sets_v as
select chunk_set_id,
       extraction_id,
       chunker_code,
       chunker_version,
       chunk_size_tokens,
       overlap_tokens,
       created_by,
       created_on,
       updated_by,
       updated_on,
       row_version
  from orac_core.knowledge_chunk_sets;
--rollback drop view orac_api.knowledge_chunk_sets_v;
