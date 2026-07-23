--liquibase formatted sql

--changeset clive:grant_orac_core_knowledge_scopes_to_orac_api context:core labels:core stripComments:false runOnChange:true
grant select, insert on orac_core.knowledge_scopes to orac_api with grant option;
--rollback revoke select, insert on orac_core.knowledge_scopes from orac_api;

--changeset clive:grant_orac_core_rag_usage_privileges_to_orac_api context:core labels:core stripComments:false runOnChange:true
grant select, insert, update on orac_core.rag_usage_privileges to orac_api with grant option;
--rollback revoke select, insert, update on orac_core.rag_usage_privileges from orac_api;
