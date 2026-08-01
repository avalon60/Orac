--liquibase formatted sql
-- Author: clive
-- Date: 26-Jul-2026
-- Description: Moves existing ORAC_DOCS knowledge sources to the canonical Core project.

--changeset clive:migrate_orac_docs_sources_to_orac_core_scope context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from orac_api.knowledge_scopes_v scope join orac_api.project_registry_v project on project.project_id = scope.project_id where scope.scope_type = 'PROJECT' and project.project_code = 'ORAC_CORE' and project.active_yn = 'Y';
-- __author__: clive
-- __date__: 2026-07-26
-- __description__: reassign existing ORAC_DOCS source lineage from the adapter plugin scope to the canonical Orac project

update orac_api.knowledge_source_objects_v source
   set knowledge_scope_id = (
         select scope.knowledge_scope_id
           from orac_api.knowledge_scopes_v scope
           join orac_api.project_registry_v project
             on project.project_id = scope.project_id
          where scope.scope_type = 'PROJECT'
            and project.project_code = 'ORAC_CORE'
       )
 where source.source_type = 'DROP_BOX'
   and source.parent_source_reference like 'ORAC_DOCS:%'
   and source.knowledge_scope_id in (
         select scope.knowledge_scope_id
           from orac_api.knowledge_scopes_v scope
           join orac_api.plugin_registry_v plugin
             on plugin.plugin_registry_id = scope.plugin_registry_id
          where scope.scope_type = 'PLUGIN'
            and plugin.plugin_id = 'drop_box'
       );

--rollback select 1 from dual;
