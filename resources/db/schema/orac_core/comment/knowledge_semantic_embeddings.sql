--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 01-Sep-2026
-- Description: Documents native semantic knowledge embedding lifecycle objects.

--changeset clive:comment_orac_core_knowledge_semantic_embeddings context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.knowledge_embedding_profiles is
  'Immutable purpose-specific identities for production native knowledge embeddings.';
comment on column orac_core.knowledge_embedding_profiles.profile_version is
  'Operator-assigned immutable version; a model digest or input transform change requires a new value.';
comment on column orac_core.knowledge_embedding_profiles.model_digest is
  'Resolved immutable Ollama model digest used to generate this profile.';
comment on column orac_core.knowledge_embedding_profiles.semantic_threshold is
  'Profile-specific semantic admission threshold, calibrated for this exact model digest and input transform.';
comment on column orac_core.knowledge_embedding_profiles.storage_layout_code is
  'Strongly typed Oracle VECTOR storage compatibility identity.';

comment on table orac_core.knowledge_embedding_activations is
  'Atomic pointer to the active embedding profile for each retrieval purpose.';
comment on column orac_core.knowledge_embedding_activations.embedding_profile_id is
  'Currently active immutable profile; vectors from other profiles must not be mixed.';

comment on table orac_core.knowledge_reembedding_runs is
  'Resumable validation and activation state for native knowledge re-embedding.';
comment on column orac_core.knowledge_reembedding_runs.stale_chunk_count is
  'Vectors whose recorded source-text hash differs from current searchable chunk content.';

comment on table orac_core.knowledge_chunk_vector_embeddings is
  'Production semantic chunk embeddings stored natively as VECTOR(768,FLOAT32).';
comment on column orac_core.knowledge_chunk_vector_embeddings.embedding_text_sha256 is
  'SHA-256 of normalized chunk text used for stale-vector and lineage validation.';
comment on column orac_core.knowledge_chunk_vector_embeddings.embedding_vector is
  'Unit-normalized 768-dimensional FLOAT32 semantic vector; never returned in retrieval evidence rows.';
--rollback select 1 from dual;
