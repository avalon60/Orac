--liquibase formatted sql

--changeset clive:comment_orac_core_knowledge_scopes context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.knowledge_scopes is 'Canonical relational knowledge scopes owned by exactly one registered project or plugin.';
comment on column orac_core.knowledge_scopes.scope_type is 'Canonical owner type: PROJECT or PLUGIN.';
comment on column orac_core.knowledge_scopes.project_id is 'Project parent for a PROJECT scope.';
comment on column orac_core.knowledge_scopes.plugin_registry_id is 'Plugin registry parent for a PLUGIN scope.';
--rollback not required;

--changeset clive:comment_orac_core_rag_usage_privileges context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.rag_usage_privileges is 'Historical database-maintained RAG usage privilege grants.';
comment on column orac_core.rag_usage_privileges.active_yn is 'Stored active state used by deterministic current-grant uniqueness.';
comment on column orac_core.rag_usage_privileges.expires_on is 'Optional effective expiry handled explicitly by the privilege API.';
comment on column orac_core.rag_usage_privileges.grant_reason_code is 'Safe administrative reason code; never prompt or evidence content.';
comment on column orac_core.rag_usage_privileges.revoke_reason_code is 'Safe revoke or expiry reason code; never prompt or evidence content.';
--rollback not required;
