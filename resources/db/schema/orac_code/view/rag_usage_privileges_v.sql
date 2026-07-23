--liquibase formatted sql

--changeset clive:create_view_orac_code_rag_usage_privileges_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-07-20
-- __description__: APEX-safe historical RAG usage privilege reporting
create or replace force view orac_code.rag_usage_privileges_v as
select privilege.rag_usage_privilege_id,
       usr.user_id,
       usr.username,
       usr.display_name,
       usr.is_active principal_active_yn,
       scope.knowledge_scope_id,
       scope.scope_type,
       scope.scope_key,
       scope.canonical_scope,
       scope.project_id,
       scope.plugin_registry_id,
       privilege.privilege_code,
       privilege.active_yn stored_active_yn,
       case
         when privilege.active_yn = 'N' then 'REVOKED'
         when privilege.expires_on is not null
          and privilege.expires_on <= systimestamp then 'EXPIRED'
         when privilege.effective_on > systimestamp then 'SCHEDULED'
         else 'ACTIVE'
       end privilege_state,
       privilege.effective_on,
       privilege.expires_on,
       privilege.granted_on,
       privilege.granted_by,
       privilege.grant_reason_code,
       privilege.revoked_on,
       privilege.revoked_by,
       privilege.revoke_reason_code,
       privilege.created_on,
       privilege.updated_on,
       privilege.row_version
  from orac_api.rag_usage_privileges_v privilege
  join orac_api.users_v usr
    on usr.user_id = privilege.user_id
  join orac_code.knowledge_scope_registry_v scope
    on scope.knowledge_scope_id = privilege.knowledge_scope_id;
--rollback drop view orac_code.rag_usage_privileges_v;
