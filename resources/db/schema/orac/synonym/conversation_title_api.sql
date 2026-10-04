--liquibase formatted sql
--changeset clive:create_synonym_orac_conversation_title_api context:core labels:core stripComments:false runOnChange:true
create or replace synonym orac.conversation_title_api for orac_code.conversation_title_api;
--rollback drop synonym orac.conversation_title_api;
