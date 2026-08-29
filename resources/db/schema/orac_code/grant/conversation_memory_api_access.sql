--liquibase formatted sql
-- Author: clive
-- Date: 28-Aug-2026
-- Description: Grants only the governed conversational-memory entrypoint to runtime.

--changeset clive:grant_execute_orac_code_conversation_memory_api_to_orac context:core labels:core stripComments:false runOnChange:true
grant execute on orac_code.conversation_memory_api to orac;
--rollback revoke execute on orac_code.conversation_memory_api from orac;
