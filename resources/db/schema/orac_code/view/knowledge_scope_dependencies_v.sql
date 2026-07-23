--liquibase formatted sql

--changeset clive:create_view_orac_code_knowledge_scope_dependencies_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-07-20
-- __description__: deletion and deactivation dependency summary for canonical scopes
create or replace force view orac_code.knowledge_scope_dependencies_v as
select scope.knowledge_scope_id,
       scope.canonical_scope,
       (select count(*)
          from orac_api.rag_usage_privileges_v privilege
         where privilege.knowledge_scope_id = scope.knowledge_scope_id) privilege_count,
       (select count(*)
          from orac_api.knowledge_source_objects_v source_object
         where source_object.knowledge_scope_id = scope.knowledge_scope_id) source_object_count,
       'Physical deletion is unsupported; deactivate the parent registry row.' delete_explanation,
       'Deactivation preserves privilege and corpus history and makes retrieval unavailable.' deactivation_explanation
  from orac_code.knowledge_scope_registry_v scope;
--rollback drop view orac_code.knowledge_scope_dependencies_v;
