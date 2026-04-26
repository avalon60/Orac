--liquibase formatted sql

--changeset clive:conversations_v_create stripComments:false runOnChange:true

create or replace force view orac_api.conversations_v as
   select
        conversation_id
         , user_id
         , session_id
         , llm_id
         , title
         , state
         , created_on
         , created_by
         , updated_on
         , updated_by
         , row_version
       from orac.conversations;
--rollback drop view orac_api.conversations_v;
