--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 04-Oct-2026
-- Description: Grants controlled title-request table access to the API layer.

--changeset clive:grant_conversation_title_core_access context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.conversation_title_requests to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.conversation_title_requests from orac_api;
