--liquibase formatted sql

--changeset clive:backfill_orac_core_knowledge_scopes context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from (select project_code from orac_core.project_registry group by project_code having count(*) > 1 union all select plugin_id from orac_core.plugin_registry group by plugin_id having count(*) > 1);
-- __author__: clive
-- __date__: 2026-07-20
-- __description__: backfill canonical registry scopes without guessing ambiguous identities

insert into orac_core.knowledge_scopes (scope_type, project_id)
select 'PROJECT', project_id
  from orac_core.project_registry project
 where not exists (
         select 1
           from orac_core.knowledge_scopes scope
          where scope.project_id = project.project_id
       );

insert into orac_core.knowledge_scopes (scope_type, plugin_registry_id)
select 'PLUGIN', plugin_registry_id
  from orac_core.plugin_registry plugin
 where not exists (
         select 1
           from orac_core.knowledge_scopes scope
          where scope.plugin_registry_id = plugin.plugin_registry_id
       );
--rollback delete from orac_core.knowledge_scopes;

--changeset clive:backfill_orac_core_knowledge_source_scope_ids context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from orac_core.knowledge_source_objects src left join orac_core.project_registry project on src.target_scope_type = 'PROJECT' and project.project_code = src.target_scope_key left join orac_core.plugin_registry plugin on src.target_scope_type = 'PLUGIN' and plugin.plugin_id = src.target_scope_key where (case when project.project_id is not null then 1 else 0 end + case when plugin.plugin_registry_id is not null then 1 else 0 end) <> 1;
--precondition-sql-check expectedResult:0 select count(1) from orac_core.knowledge_documents doc join orac_core.knowledge_source_objects src on src.source_object_id = doc.source_object_id where doc.target_scope_type <> src.target_scope_type or doc.target_scope_key <> src.target_scope_key;

update orac_core.knowledge_source_objects src
   set knowledge_scope_id = (
         select scope.knowledge_scope_id
           from orac_core.knowledge_scopes scope
           left join orac_core.project_registry project
             on project.project_id = scope.project_id
           left join orac_core.plugin_registry plugin
             on plugin.plugin_registry_id = scope.plugin_registry_id
          where scope.scope_type = src.target_scope_type
            and coalesce(project.project_code, plugin.plugin_id) = src.target_scope_key
       );

alter table orac_core.knowledge_source_objects modify knowledge_scope_id not null;
--rollback alter table orac_core.knowledge_source_objects modify knowledge_scope_id null;

--changeset clive:add_and_backfill_plugin_service_owners context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from orac_core.plugin_services service left join orac_core.plugin_registry plugin on plugin.plugin_id = service.plugin_id where plugin.plugin_registry_id is null and service.plugin_id <> 'orac_core';

alter table orac_core.plugin_services add
(
  service_owner_type varchar2(20 char),
  plugin_registry_id number
);

update orac_core.plugin_services service
   set service_owner_type = case
                              when service.plugin_id = 'orac_core' then 'CORE'
                              else 'PLUGIN'
                            end,
       plugin_registry_id = (
         select plugin.plugin_registry_id
           from orac_core.plugin_registry plugin
          where plugin.plugin_id = service.plugin_id
       );

alter table orac_core.plugin_services modify service_owner_type not null;
--rollback alter table orac_core.plugin_services drop (service_owner_type, plugin_registry_id);
