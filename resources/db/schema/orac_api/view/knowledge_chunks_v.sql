--liquibase formatted sql

--changeset clive:create_view_orac_api_knowledge_chunks_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.knowledge_chunks_v as
select chunk_id,
       chunk_set_id,
       chunk_no,
       span_start,
       span_end,
       token_count,
       content_sha256,
       chunk_text,
       created_by,
       created_on,
       updated_by,
       updated_on,
       row_version
  from orac_core.knowledge_chunks;
--rollback drop view orac_api.knowledge_chunks_v;
