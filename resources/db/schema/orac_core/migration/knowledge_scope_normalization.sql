--liquibase formatted sql

--changeset clive:remove_legacy_knowledge_scope_columns context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:2 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name in ('KN_SRCOBJ_SCOPE_CK', 'KN_DOC_SCOPE_CK');
--precondition-sql-check expectedResult:4 select count(1) from all_tab_columns where owner = 'ORAC_CORE' and ((table_name = 'KNOWLEDGE_SOURCE_OBJECTS' and column_name in ('TARGET_SCOPE_TYPE', 'TARGET_SCOPE_KEY')) or (table_name = 'KNOWLEDGE_DOCUMENTS' and column_name in ('TARGET_SCOPE_TYPE', 'TARGET_SCOPE_KEY')));
-- __author__: clive
-- __date__: 2026-07-20
-- __description__: remove denormalized scope strings after legacy constraints have been installed

alter table orac_core.knowledge_source_objects drop constraint kn_srcobj_scope_ck;
alter table orac_core.knowledge_documents drop constraint kn_doc_scope_ck;
alter table orac_core.knowledge_source_objects drop (target_scope_type, target_scope_key);
alter table orac_core.knowledge_documents drop (target_scope_type, target_scope_key);
--rollback alter table orac_core.knowledge_source_objects add (target_scope_type varchar2(50 char), target_scope_key varchar2(200 char));
--rollback alter table orac_core.knowledge_documents add (target_scope_type varchar2(50 char), target_scope_key varchar2(200 char));
--rollback update orac_core.knowledge_source_objects src set (target_scope_type, target_scope_key) = (select scope.scope_type, coalesce(project.project_code, plugin.plugin_id) from orac_core.knowledge_scopes scope left join orac_core.project_registry project on project.project_id = scope.project_id left join orac_core.plugin_registry plugin on plugin.plugin_registry_id = scope.plugin_registry_id where scope.knowledge_scope_id = src.knowledge_scope_id);
--rollback update orac_core.knowledge_documents doc set (target_scope_type, target_scope_key) = (select src.target_scope_type, src.target_scope_key from orac_core.knowledge_source_objects src where src.source_object_id = doc.source_object_id);
--rollback alter table orac_core.knowledge_source_objects modify (target_scope_type not null, target_scope_key not null);
--rollback alter table orac_core.knowledge_documents modify (target_scope_type not null, target_scope_key not null);
--rollback alter table orac_core.knowledge_source_objects add constraint kn_srcobj_scope_ck check (target_scope_type in ('PROJECT', 'PLUGIN'));
--rollback alter table orac_core.knowledge_documents add constraint kn_doc_scope_ck check (target_scope_type in ('PROJECT', 'PLUGIN'));
