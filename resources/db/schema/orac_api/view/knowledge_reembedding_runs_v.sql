--liquibase formatted sql

--changeset clive:create_view_orac_api_knowledge_reembedding_runs_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.knowledge_reembedding_runs_v as
select reembedding_run_id,
       embedding_profile_id,
       status_code,
       expected_chunk_count,
       completed_chunk_count,
       stale_chunk_count,
       failed_chunk_count,
       last_error_code,
       started_on,
       completed_on,
       created_by,
       created_on,
       updated_by,
       updated_on,
       row_version
  from orac_core.knowledge_reembedding_runs;
--rollback drop view orac_api.knowledge_reembedding_runs_v;
