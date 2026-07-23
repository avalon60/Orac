--liquibase formatted sql

--changeset clive:grant_rag_usage_authorization_api_to_orac context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-07-20
-- __description__: grant runtime only the RAG usage decision surface
grant execute on orac_code.rag_usage_authorization_api to orac;
--rollback revoke execute on orac_code.rag_usage_authorization_api from orac;

--changeset clive:grant_knowledge_scope_validation_api_to_orac_plugin context:core labels:core stripComments:false runOnChange:true
grant execute on orac_code.knowledge_scope_validation_api to orac_plugin;
--rollback revoke execute on orac_code.knowledge_scope_validation_api from orac_plugin;


--changeset clive:grant_rag_usage_privilege_api_to_orac_apx_pub context:core labels:core stripComments:false runOnChange:true
grant execute on orac_code.rag_usage_privilege_api to orac_apx_pub;
--rollback revoke execute on orac_code.rag_usage_privilege_api from orac_apx_pub;

--changeset clive:grant_rag_usage_privileges_v_to_orac_apx_pub context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.rag_usage_privileges_v to orac_apx_pub;
--rollback revoke read on orac_code.rag_usage_privileges_v from orac_apx_pub;

--changeset clive:grant_rag_usage_scope_lov_v_to_orac_apx_pub context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.rag_usage_scope_lov_v to orac_apx_pub;
--rollback revoke read on orac_code.rag_usage_scope_lov_v from orac_apx_pub;

--changeset clive:grant_knowledge_scope_registry_v_to_orac_apx_pub context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.knowledge_scope_registry_v to orac_apx_pub;
--rollback revoke read on orac_code.knowledge_scope_registry_v from orac_apx_pub;

--changeset clive:grant_knowledge_scope_dependencies_v_to_orac_apx_pub context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.knowledge_scope_dependencies_v to orac_apx_pub;
--rollback revoke read on orac_code.knowledge_scope_dependencies_v from orac_apx_pub;
