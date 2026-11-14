--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 25-Oct-2026
-- Description: Links transient APEX searches to immutable plugin and knowledge scope records.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_constraint_orac_core_kn_apxsr_plugin_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_APXSR_PLUGIN_FK1';
alter table orac_core.knowledge_apex_search_requests add constraint kn_apxsr_plugin_fk1
  foreign key (plugin_registry_id) references orac_core.plugin_registry (plugin_registry_id)
  on delete cascade;
--rollback alter table orac_core.knowledge_apex_search_requests drop constraint kn_apxsr_plugin_fk1;

--changeset clive:create_constraint_orac_core_kn_apxsr_scope_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_APXSR_SCOPE_FK1';
alter table orac_core.knowledge_apex_search_requests add constraint kn_apxsr_scope_fk1
  foreign key (knowledge_scope_id) references orac_core.knowledge_scopes (knowledge_scope_id);
--rollback alter table orac_core.knowledge_apex_search_requests drop constraint kn_apxsr_scope_fk1;
