--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 01-Sep-2026
-- Description: Enforces native knowledge profile and run state invariants.

--changeset clive:create_constraint_other_orac_core_kn_embprf_shape_ck context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_EMBPRF_SHAPE_CK';
alter table orac_core.knowledge_embedding_profiles add constraint kn_embprf_shape_ck
  check (
    truncate_yn in ('Y', 'N')
    and semantic_yn in ('Y', 'N')
    and production_allowed_yn in ('Y', 'N')
    and semantic_threshold between 0 and 1
    and semantic_candidate_limit between 1 and 50
    and lexical_candidate_limit between 1 and 50
  );
--rollback alter table orac_core.knowledge_embedding_profiles drop constraint kn_embprf_shape_ck;

--changeset clive:create_constraint_other_orac_core_kn_embprf_native_ck context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_EMBPRF_NATIVE_CK';
alter table orac_core.knowledge_embedding_profiles add constraint kn_embprf_native_ck
  check (
    storage_layout_code = 'ORACLE_VECTOR_768_FLOAT32_V1'
    and semantic_yn = 'Y'
  );
--rollback alter table orac_core.knowledge_embedding_profiles drop constraint kn_embprf_native_ck;

--changeset clive:create_constraint_other_orac_core_kn_reembr_shape_ck context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_REEMBR_SHAPE_CK';
alter table orac_core.knowledge_reembedding_runs add constraint kn_reembr_shape_ck
  check (
    status_code in ('BUILDING', 'VALIDATING', 'VALIDATED', 'ACTIVE', 'FAILED', 'CANCELLED')
    and expected_chunk_count >= 0
    and completed_chunk_count >= 0
    and stale_chunk_count >= 0
    and failed_chunk_count >= 0
  );
--rollback alter table orac_core.knowledge_reembedding_runs drop constraint kn_reembr_shape_ck;

--changeset clive:create_constraint_other_orac_core_kn_chnkve_hash_ck context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_CHNKVE_HASH_CK';
alter table orac_core.knowledge_chunk_vector_embeddings add constraint kn_chnkve_hash_ck
  check (regexp_like(embedding_text_sha256, '^[0-9a-f]{64}$'));
--rollback alter table orac_core.knowledge_chunk_vector_embeddings drop constraint kn_chnkve_hash_ck;
