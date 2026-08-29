--liquibase formatted sql
-- Author: clive
-- Date: 28-Aug-2026
-- Description: Grants the API layer controlled conversation-memory table access.

--changeset clive:grant_orac_core_conversation_memory_requests_to_orac_api context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.conversation_memory_requests to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.conversation_memory_requests from orac_api;

--changeset clive:grant_orac_core_conversation_summary_checkpoints_to_orac_api context:core labels:core stripComments:false runOnChange:true
grant select, insert, delete on orac_core.conversation_summary_checkpoints to orac_api with grant option;
--rollback revoke select, insert, delete on orac_core.conversation_summary_checkpoints from orac_api;

--changeset clive:grant_orac_core_conversation_summary_sources_to_orac_api context:core labels:core stripComments:false runOnChange:true
grant select, insert, delete on orac_core.conversation_summary_sources to orac_api with grant option;
--rollback revoke select, insert, delete on orac_core.conversation_summary_sources from orac_api;
