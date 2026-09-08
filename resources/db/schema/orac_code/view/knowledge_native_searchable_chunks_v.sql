--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 01-Sep-2026
-- Description: Projects current chunks with the active native embedding profile.

--changeset clive:create_view_orac_code_knowledge_native_searchable_chunks_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_code.knowledge_native_searchable_chunks_v as
select chunk.*,
       emb.chunk_vector_embedding_id,
       emb.embedding_vector,
       emb.embedding_text_sha256,
       profile.embedding_profile_id,
       profile.profile_version,
       profile.model_digest,
       profile.retrieval_policy_version,
       profile.semantic_threshold,
       profile.semantic_candidate_limit,
       profile.lexical_candidate_limit,
       profile.storage_layout_code,
       model.provider_code,
       model.model_name embedding_model_identifier,
       model.model_revision embedding_model_revision,
       model.dimensions embedding_dimensions,
       model.distance_metric,
       model.normalisation
  from orac_code.knowledge_searchable_chunk_content_v chunk
  join orac_api.knowledge_embedding_activations_v activation
    on activation.purpose_code = 'KNOWLEDGE_CHUNK_RETRIEVAL'
  join orac_api.knowledge_embedding_profiles_v profile
    on profile.embedding_profile_id = activation.embedding_profile_id
   and profile.semantic_yn = 'Y'
   and profile.production_allowed_yn = 'Y'
  join orac_api.knowledge_embedding_models_v model
    on model.embedding_model_id = profile.embedding_model_id
   and model.dimensions > 0
   and model.distance_metric = 'COSINE'
   and profile.storage_layout_code =
       'ORACLE_VECTOR_' || to_char(model.dimensions) || '_FLOAT32_V1'
  join orac_api.knowledge_chunk_vector_embeddings_v emb
    on emb.chunk_id = chunk.chunk_id
   and emb.embedding_profile_id = profile.embedding_profile_id
   and emb.embedding_text_sha256 = chunk.chunk_content_sha256
   and vector_dimension_count(emb.embedding_vector) = model.dimensions
   and vector_dimension_format(emb.embedding_vector) = 'FLOAT32';
--rollback drop view orac_code.knowledge_native_searchable_chunks_v;
