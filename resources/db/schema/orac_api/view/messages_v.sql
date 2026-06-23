--liquibase formatted sql

--changeset clive:messages_v_create stripComments:false runOnChange:true context:core labels:core

create or replace force view orac_api.messages_v as
   select
        message_id
         , conversation_id
         , turn_index
         , role
         , message_type
         , content
         , tokens_used
         , meta
         , llm_id
         , created_on
         , created_by
         , updated_on
         , updated_by
         , row_version
       from orac_core.messages;
--rollback drop view orac_api.messages_v;
