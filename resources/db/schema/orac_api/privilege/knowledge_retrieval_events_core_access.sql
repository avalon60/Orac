--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 13-Aug-2026
-- Description: Grants the API layer minimal retrieval audit table access.

--changeset clive:grant_orac_core_knowledge_retrieval_events_to_orac_api context:core labels:core stripComments:false runOnChange:true
grant select, insert on orac_core.knowledge_retrieval_events to orac_api with grant option;
--rollback revoke select, insert on orac_core.knowledge_retrieval_events from orac_api;
