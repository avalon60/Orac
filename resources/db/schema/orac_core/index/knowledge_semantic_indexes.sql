--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 01-Sep-2026
-- Description: Creates relational indexes for native knowledge embeddings.

--changeset clive:create_index_orac_core_kn_embprf_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_EMBPRF_PK';
create unique index orac_core.kn_embprf_pk
  on orac_core.knowledge_embedding_profiles (embedding_profile_id);
--rollback drop index orac_core.kn_embprf_pk;

--changeset clive:create_index_orac_core_kn_embprf_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_EMBPRF_UK1_IDX';
create unique index orac_core.kn_embprf_uk1_idx
  on orac_core.knowledge_embedding_profiles (purpose_code, profile_version);
--rollback drop index orac_core.kn_embprf_uk1_idx;

--changeset clive:create_index_orac_core_kn_embact_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_EMBACT_PK';
create unique index orac_core.kn_embact_pk
  on orac_core.knowledge_embedding_activations (purpose_code);
--rollback drop index orac_core.kn_embact_pk;

--changeset clive:create_index_orac_core_kn_reembr_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_REEMBR_PK';
create unique index orac_core.kn_reembr_pk
  on orac_core.knowledge_reembedding_runs (reembedding_run_id);
--rollback drop index orac_core.kn_reembr_pk;

--changeset clive:create_index_orac_core_kn_reembr_prf_idx context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_REEMBR_PRF_IDX';
create index orac_core.kn_reembr_prf_idx
  on orac_core.knowledge_reembedding_runs (embedding_profile_id, status_code);
--rollback drop index orac_core.kn_reembr_prf_idx;

--changeset clive:create_index_orac_core_kn_chnkve_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_CHNKVE_PK';
create unique index orac_core.kn_chnkve_pk
  on orac_core.knowledge_chunk_vector_embeddings (chunk_vector_embedding_id);
--rollback drop index orac_core.kn_chnkve_pk;

--changeset clive:create_index_orac_core_kn_chnkve_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_CHNKVE_UK1_IDX';
create unique index orac_core.kn_chnkve_uk1_idx
  on orac_core.knowledge_chunk_vector_embeddings (
    chunk_id,
    embedding_profile_id,
    embedding_text_sha256
  );
--rollback drop index orac_core.kn_chnkve_uk1_idx;

--changeset clive:create_index_orac_core_kn_chnkve_prf_idx context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_CHNKVE_PRF_IDX';
create index orac_core.kn_chnkve_prf_idx
  on orac_core.knowledge_chunk_vector_embeddings (
    embedding_profile_id,
    chunk_id
  );
--rollback drop index orac_core.kn_chnkve_prf_idx;

-- No Oracle vector index is created. Initial retrieval uses FETCH EXACT.
