--liquibase formatted sql

--changeset clive:create_view_orac_api_knowledge_embedding_activations_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.knowledge_embedding_activations_v as
select purpose_code,
       embedding_profile_id,
       activated_by,
       activated_on,
       created_by,
       created_on,
       updated_by,
       updated_on,
       row_version
  from orac_core.knowledge_embedding_activations;
--rollback drop view orac_api.knowledge_embedding_activations_v;
