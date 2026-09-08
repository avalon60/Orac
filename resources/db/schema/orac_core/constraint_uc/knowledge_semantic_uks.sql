--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 01-Sep-2026
-- Description: Creates immutable identity keys for native knowledge embeddings.

--changeset clive:create_constraint_uc_orac_core_kn_embprf_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_EMBPRF_UK1';
alter table orac_core.knowledge_embedding_profiles add constraint kn_embprf_uk1
  unique (purpose_code, profile_version)
  using index orac_core.kn_embprf_uk1_idx;
--rollback alter table orac_core.knowledge_embedding_profiles drop constraint kn_embprf_uk1;

--changeset clive:create_constraint_uc_orac_core_kn_chnkve_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_CHNKVE_UK1';
alter table orac_core.knowledge_chunk_vector_embeddings add constraint kn_chnkve_uk1
  unique (chunk_id, embedding_profile_id, embedding_text_sha256)
  using index orac_core.kn_chnkve_uk1_idx;
--rollback alter table orac_core.knowledge_chunk_vector_embeddings drop constraint kn_chnkve_uk1;
