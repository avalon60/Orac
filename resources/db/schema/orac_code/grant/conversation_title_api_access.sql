--liquibase formatted sql
--changeset clive:grant_conversation_title_api_to_orac context:core labels:core stripComments:false runOnChange:true
grant execute on orac_code.conversation_title_api to orac;
grant read on orac_code.conversation_title_requests_v to orac;
grant read on orac_code.conversation_title_dialogue_v to orac;
--rollback revoke read on orac_code.conversation_title_dialogue_v from orac;
--rollback revoke read on orac_code.conversation_title_requests_v from orac;
--rollback revoke execute on orac_code.conversation_title_api from orac;
