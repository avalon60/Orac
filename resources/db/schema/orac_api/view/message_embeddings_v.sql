--liquibase formatted sql

--changeset clive:message_embeddings_v_create stripComments:false runOnChange:true

create or replace force view orac_api.message_embeddings_v as
   select
        emb_id
         , message_id
         , chunk_index
         , span_start
         , span_end
         , lossless_text
         , content_snapshot
         , embedding
         , embedding_model
         , embedding_provider
         , distance_metric
         , tokens_used
         , created_on
         , created_by
         , updated_on
         , updated_by
         , row_version
       from orac.message_embeddings;
--rollback drop view orac_api.message_embeddings_v;
