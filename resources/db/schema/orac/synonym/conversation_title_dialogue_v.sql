--liquibase formatted sql
--changeset clive:create_synonym_orac_conversation_title_dialogue_v context:core labels:core stripComments:false runOnChange:true
create or replace synonym orac.conversation_title_dialogue_v for orac_code.conversation_title_dialogue_v;
--rollback drop synonym orac.conversation_title_dialogue_v;
