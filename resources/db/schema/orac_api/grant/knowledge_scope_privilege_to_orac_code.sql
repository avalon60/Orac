--liquibase formatted sql

--changeset clive:grant_orac_api_knowledge_scopes_v_to_orac_code context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.knowledge_scopes_v to orac_code with grant option;
--rollback revoke select on orac_api.knowledge_scopes_v from orac_code;

--changeset clive:grant_orac_api_rag_usage_privileges_v_to_orac_code context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.rag_usage_privileges_v to orac_code with grant option;
--rollback revoke select on orac_api.rag_usage_privileges_v from orac_code;

--changeset clive:grant_orac_api_knowledge_scopes_tapi_to_orac_code context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.knowledge_scopes_tapi to orac_code;
--rollback revoke execute on orac_api.knowledge_scopes_tapi from orac_code;

--changeset clive:grant_orac_api_rag_usage_privileges_tapi_to_orac_code context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.rag_usage_privileges_tapi to orac_code;
--rollback revoke execute on orac_api.rag_usage_privileges_tapi from orac_code;
