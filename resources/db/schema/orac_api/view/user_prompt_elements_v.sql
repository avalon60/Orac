--liquibase formatted sql

--changeset clive:user_prompt_elements_v_create stripComments:false runOnChange:true

create or replace force view orac_api.user_prompt_elements_v as
   select
        element_id
         , user_id
         , category_code
         , prompt_element
         , weight_score
         , is_enabled
         , created_on
         , created_by
         , updated_on
         , updated_by
         , row_version
       from orac_core.user_prompt_elements;
--rollback drop view orac_api.user_prompt_elements_v;
