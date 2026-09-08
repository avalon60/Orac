--liquibase formatted sql

--changeset clive:grant_execute_orac_code_knowledge_embedding_api_to_orac context:core labels:core stripComments:false runOnChange:true
grant execute on orac_code.knowledge_embedding_api to orac;
--rollback revoke execute on orac_code.knowledge_embedding_api from orac;
