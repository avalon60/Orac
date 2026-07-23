--liquibase formatted sql

--changeset clive:create_constraint_fk_orac_core_kn_scope_project_fk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_SCOPE_PROJECT_FK';
alter table orac_core.knowledge_scopes add constraint kn_scope_project_fk
  foreign key (project_id) references orac_core.project_registry (project_id);
--rollback alter table orac_core.knowledge_scopes drop constraint kn_scope_project_fk;

--changeset clive:create_constraint_fk_orac_core_kn_scope_plugin_fk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_SCOPE_PLUGIN_FK';
alter table orac_core.knowledge_scopes add constraint kn_scope_plugin_fk
  foreign key (plugin_registry_id) references orac_core.plugin_registry (plugin_registry_id);
--rollback alter table orac_core.knowledge_scopes drop constraint kn_scope_plugin_fk;

--changeset clive:create_constraint_fk_orac_core_rag_useprv_user_fk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'RAG_USEPRV_USER_FK';
alter table orac_core.rag_usage_privileges add constraint rag_useprv_user_fk
  foreign key (user_id) references orac_core.users (user_id);
--rollback alter table orac_core.rag_usage_privileges drop constraint rag_useprv_user_fk;

--changeset clive:create_constraint_fk_orac_core_rag_useprv_scope_fk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'RAG_USEPRV_SCOPE_FK';
alter table orac_core.rag_usage_privileges add constraint rag_useprv_scope_fk
  foreign key (knowledge_scope_id) references orac_core.knowledge_scopes (knowledge_scope_id);
--rollback alter table orac_core.rag_usage_privileges drop constraint rag_useprv_scope_fk;

--changeset clive:create_constraint_fk_orac_core_kn_srcobj_scope_fk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_SRCOBJ_SCOPE_FK';
alter table orac_core.knowledge_source_objects add constraint kn_srcobj_scope_fk
  foreign key (knowledge_scope_id) references orac_core.knowledge_scopes (knowledge_scope_id);
--rollback alter table orac_core.knowledge_source_objects drop constraint kn_srcobj_scope_fk;

--changeset clive:create_constraint_fk_orac_core_plgsvc_registry_fk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLGSVC_REGISTRY_FK';
alter table orac_core.plugin_services add constraint plgsvc_registry_fk
  foreign key (plugin_registry_id) references orac_core.plugin_registry (plugin_registry_id);
--rollback alter table orac_core.plugin_services drop constraint plgsvc_registry_fk;
