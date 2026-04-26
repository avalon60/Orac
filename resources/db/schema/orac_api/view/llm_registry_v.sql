--liquibase formatted sql

--changeset clive:llm_registry_v_create stripComments:false runOnChange:true

create or replace force view orac_api.llm_registry_v as
   select
        llm_id
         , name
         , provider
         , model
         , context_policy
         , max_context_tokens
         , is_enabled
         , properties
         , created_on
         , created_by
         , updated_on
         , updated_by
         , row_version
       from orac.llm_registry;
--rollback drop view orac_api.llm_registry_v;
