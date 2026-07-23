--liquibase formatted sql

--changeset clive:create_view_orac_code_knowledge_scope_registry_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-07-20
-- __description__: canonical scope registry with derived immutable identifiers and status
create or replace force view orac_code.knowledge_scope_registry_v as
select scope.knowledge_scope_id,
       scope.scope_type,
       coalesce(project.project_code, plugin.plugin_id) scope_key,
       scope.scope_type || ':' || coalesce(project.project_code, plugin.plugin_id) canonical_scope,
       scope.project_id,
       scope.plugin_registry_id,
       project.display_name project_display_name,
       plugin.plugin_name,
       case
         when scope.scope_type = 'PROJECT' then project.active_yn
         else plugin.enabled
       end active_yn,
       plugin.install_status,
       plugin.configuration_status,
       plugin.dependency_status,
       plugin.database_status,
       plugin.readiness_status,
       scope.created_by,
       scope.created_on,
       scope.updated_by,
       scope.updated_on,
       scope.row_version
  from orac_api.knowledge_scopes_v scope
  left join orac_api.project_registry_v project
    on project.project_id = scope.project_id
  left join orac_api.plugin_registry_v plugin
    on plugin.plugin_registry_id = scope.plugin_registry_id;
--rollback drop view orac_code.knowledge_scope_registry_v;
