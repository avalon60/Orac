--liquibase formatted sql
-- Author: clive
-- Date: 28-Aug-2026
-- Description: Grants the business layer only required memory views and TAPIs.

--changeset clive:grant_read_conversation_memory_views_to_orac_code context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.conversation_memory_requests_v to orac_code;
grant read on orac_api.conversation_summary_checkpoints_v to orac_code;
grant read on orac_api.conversation_summary_sources_v to orac_code;
--rollback revoke read on orac_api.conversation_memory_requests_v from orac_code;
--rollback revoke read on orac_api.conversation_summary_checkpoints_v from orac_code;
--rollback revoke read on orac_api.conversation_summary_sources_v from orac_code;

--changeset clive:grant_execute_conversation_memory_tapis_to_orac_code context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.conversation_memory_requests_tapi to orac_code;
grant execute on orac_api.conversation_summary_checkpoints_tapi to orac_code;
grant execute on orac_api.conversation_summary_sources_tapi to orac_code;
--rollback revoke execute on orac_api.conversation_memory_requests_tapi from orac_code;
--rollback revoke execute on orac_api.conversation_summary_checkpoints_tapi from orac_code;
--rollback revoke execute on orac_api.conversation_summary_sources_tapi from orac_code;
