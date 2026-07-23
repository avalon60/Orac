--liquibase formatted sql

--changeset clive:create_view_orac_api_knowledge_scopes_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.knowledge_scopes_v as
select knowledge_scope_id,
       scope_type,
       project_id,
       plugin_registry_id,
       created_by,
       created_on,
       updated_by,
       updated_on,
       row_version
  from orac_core.knowledge_scopes;
--rollback drop view orac_api.knowledge_scopes_v;
