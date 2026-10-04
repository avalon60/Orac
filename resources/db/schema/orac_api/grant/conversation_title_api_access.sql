--liquibase formatted sql
--changeset clive:grant_conversation_title_api_access context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.conversation_title_requests_v to orac_code with grant option;
grant execute on orac_api.conversation_title_requests_tapi to orac_code;
grant read on orac_api.conversations_v to orac_code;
grant read on orac_api.messages_v to orac_code;
--rollback revoke read on orac_api.messages_v from orac_code;
--rollback revoke read on orac_api.conversations_v from orac_code;
--rollback revoke execute on orac_api.conversation_title_requests_tapi from orac_code;
--rollback revoke read on orac_api.conversation_title_requests_v from orac_code;
