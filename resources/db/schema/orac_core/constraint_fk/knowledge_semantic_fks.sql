--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 01-Sep-2026
-- Description: Connects native knowledge embeddings to model and chunk lineage.

--changeset clive:create_constraint_fk_orac_core_kn_embprf_model_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_EMBPRF_MODEL_FK1';
alter table orac_core.knowledge_embedding_profiles add constraint kn_embprf_model_fk1
  foreign key (embedding_model_id)
  references orac_core.knowledge_embedding_models (embedding_model_id);
--rollback alter table orac_core.knowledge_embedding_profiles drop constraint kn_embprf_model_fk1;

--changeset clive:create_constraint_fk_orac_core_kn_embact_prf_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_EMBACT_PRF_FK1';
alter table orac_core.knowledge_embedding_activations add constraint kn_embact_prf_fk1
  foreign key (embedding_profile_id)
  references orac_core.knowledge_embedding_profiles (embedding_profile_id);
--rollback alter table orac_core.knowledge_embedding_activations drop constraint kn_embact_prf_fk1;

--changeset clive:create_constraint_fk_orac_core_kn_reembr_prf_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_REEMBR_PRF_FK1';
alter table orac_core.knowledge_reembedding_runs add constraint kn_reembr_prf_fk1
  foreign key (embedding_profile_id)
  references orac_core.knowledge_embedding_profiles (embedding_profile_id);
--rollback alter table orac_core.knowledge_reembedding_runs drop constraint kn_reembr_prf_fk1;

--changeset clive:create_constraint_fk_orac_core_kn_chnkve_chnk_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_CHNKVE_CHNK_FK1';
alter table orac_core.knowledge_chunk_vector_embeddings add constraint kn_chnkve_chnk_fk1
  foreign key (chunk_id)
  references orac_core.knowledge_chunks (chunk_id);
--rollback alter table orac_core.knowledge_chunk_vector_embeddings drop constraint kn_chnkve_chnk_fk1;

--changeset clive:create_constraint_fk_orac_core_kn_chnkve_prf_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_CHNKVE_PRF_FK1';
alter table orac_core.knowledge_chunk_vector_embeddings add constraint kn_chnkve_prf_fk1
  foreign key (embedding_profile_id)
  references orac_core.knowledge_embedding_profiles (embedding_profile_id);
--rollback alter table orac_core.knowledge_chunk_vector_embeddings drop constraint kn_chnkve_prf_fk1;

--changeset clive:create_constraint_fk_orac_core_kn_chnkve_run_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_CHNKVE_RUN_FK1';
alter table orac_core.knowledge_chunk_vector_embeddings add constraint kn_chnkve_run_fk1
  foreign key (reembedding_run_id)
  references orac_core.knowledge_reembedding_runs (reembedding_run_id);
--rollback alter table orac_core.knowledge_chunk_vector_embeddings drop constraint kn_chnkve_run_fk1;
