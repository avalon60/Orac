--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 01-Sep-2026
-- Description: Creates primary keys for native knowledge embedding lifecycle tables.

--changeset clive:create_constraint_pk_orac_core_kn_embprf_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_EMBPRF_PK';
alter table orac_core.knowledge_embedding_profiles add constraint kn_embprf_pk
  primary key (embedding_profile_id)
  using index orac_core.kn_embprf_pk;
--rollback alter table orac_core.knowledge_embedding_profiles drop constraint kn_embprf_pk;

--changeset clive:create_constraint_pk_orac_core_kn_embact_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_EMBACT_PK';
alter table orac_core.knowledge_embedding_activations add constraint kn_embact_pk
  primary key (purpose_code)
  using index orac_core.kn_embact_pk;
--rollback alter table orac_core.knowledge_embedding_activations drop constraint kn_embact_pk;

--changeset clive:create_constraint_pk_orac_core_kn_reembr_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_REEMBR_PK';
alter table orac_core.knowledge_reembedding_runs add constraint kn_reembr_pk
  primary key (reembedding_run_id)
  using index orac_core.kn_reembr_pk;
--rollback alter table orac_core.knowledge_reembedding_runs drop constraint kn_reembr_pk;

--changeset clive:create_constraint_pk_orac_core_kn_chnkve_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_CHNKVE_PK';
alter table orac_core.knowledge_chunk_vector_embeddings add constraint kn_chnkve_pk
  primary key (chunk_vector_embedding_id)
  using index orac_core.kn_chnkve_pk;
--rollback alter table orac_core.knowledge_chunk_vector_embeddings drop constraint kn_chnkve_pk;
