--liquibase formatted sql

--changeset clive:create_view_orac_api_knowledge_chunk_embeddings_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.knowledge_chunk_embeddings_v as
select chunk_embedding_id,
       chunk_id,
       embedding_model_id,
       embedding_text_sha256,
       embedding_vector,
       created_by,
       created_on,
       updated_by,
       updated_on,
       row_version
  from orac_core.knowledge_chunk_embeddings;
--rollback drop view orac_api.knowledge_chunk_embeddings_v;
