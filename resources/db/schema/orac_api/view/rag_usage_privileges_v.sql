--liquibase formatted sql

--changeset clive:create_view_orac_api_rag_usage_privileges_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.rag_usage_privileges_v as
select rag_usage_privilege_id,
       user_id,
       knowledge_scope_id,
       privilege_code,
       active_yn,
       effective_on,
       expires_on,
       granted_on,
       granted_by,
       grant_reason_code,
       revoked_on,
       revoked_by,
       revoke_reason_code,
       created_by,
       created_on,
       updated_by,
       updated_on,
       row_version
  from orac_core.rag_usage_privileges;
--rollback drop view orac_api.rag_usage_privileges_v;
