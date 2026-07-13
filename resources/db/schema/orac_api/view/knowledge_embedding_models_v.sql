--liquibase formatted sql

--changeset clive:create_view_orac_api_knowledge_embedding_models_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.knowledge_embedding_models_v as
select embedding_model_id,
       provider_code,
       model_name,
       model_revision,
       dimensions,
       distance_metric,
       normalisation,
       active_yn,
       created_by,
       created_on,
       updated_by,
       updated_on,
       row_version
  from orac_core.knowledge_embedding_models;
--rollback drop view orac_api.knowledge_embedding_models_v;
