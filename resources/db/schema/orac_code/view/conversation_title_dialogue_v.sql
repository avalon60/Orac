--liquibase formatted sql
--changeset clive:create_view_orac_code_conversation_title_dialogue_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_code.conversation_title_dialogue_v as
select conversation_id, turn_index, role,
       json_value(content, '$.text' returning varchar2(4000 char)) content_text
  from orac_api.messages_v
 where role in ('user', 'assistant');
--rollback drop view orac_code.conversation_title_dialogue_v;
