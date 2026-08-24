--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 13-Aug-2026
-- Description: Grants controlled retrieval audit access to the business layer.

--changeset clive:grant_read_orac_api_knowledge_retrieval_events_v_to_orac_code context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.knowledge_retrieval_events_v to orac_code;
--rollback revoke read on orac_api.knowledge_retrieval_events_v from orac_code;

--changeset clive:grant_execute_orac_api_knowledge_retrieval_events_tapi_to_orac_code context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.knowledge_retrieval_events_tapi to orac_code;
--rollback revoke execute on orac_api.knowledge_retrieval_events_tapi from orac_code;
