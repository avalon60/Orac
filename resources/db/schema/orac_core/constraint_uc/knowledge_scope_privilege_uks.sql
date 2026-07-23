--liquibase formatted sql

--changeset clive:create_constraint_uc_orac_core_kn_scope_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_SCOPE_UK1';
alter table orac_core.knowledge_scopes add constraint kn_scope_uk1
  unique (project_id) using index orac_core.kn_scope_uk1_idx;
--rollback alter table orac_core.knowledge_scopes drop constraint kn_scope_uk1;

--changeset clive:create_constraint_uc_orac_core_kn_scope_uk2 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_SCOPE_UK2';
alter table orac_core.knowledge_scopes add constraint kn_scope_uk2
  unique (plugin_registry_id) using index orac_core.kn_scope_uk2_idx;
--rollback alter table orac_core.knowledge_scopes drop constraint kn_scope_uk2;
