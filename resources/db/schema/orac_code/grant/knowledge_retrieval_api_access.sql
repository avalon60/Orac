--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 13-Aug-2026
-- Description: Grants the Core runtime only the authorised retrieval entrypoint.

--changeset clive:grant_execute_orac_code_knowledge_retrieval_api_to_orac context:core labels:core stripComments:false runOnChange:true
grant execute on orac_code.knowledge_retrieval_api to orac;
--rollback revoke execute on orac_code.knowledge_retrieval_api from orac;
