--liquibase formatted sql

--changeset clive:create_view_orac_api_knowledge_embedding_profiles_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.knowledge_embedding_profiles_v as
select embedding_profile_id,
       purpose_code,
       profile_version,
       embedding_model_id,
       model_digest,
       document_input_prefix,
       query_input_prefix,
       truncate_yn,
       storage_layout_code,
       retrieval_policy_version,
       semantic_threshold,
       semantic_candidate_limit,
       lexical_candidate_limit,
       semantic_yn,
       production_allowed_yn,
       created_by,
       created_on,
       updated_by,
       updated_on,
       row_version
  from orac_core.knowledge_embedding_profiles;
--rollback drop view orac_api.knowledge_embedding_profiles_v;
