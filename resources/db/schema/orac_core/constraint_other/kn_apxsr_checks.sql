--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 25-Oct-2026
-- Description: Constrains plugin APEX search state and result references.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_constraint_orac_core_kn_apxsr_status_ck context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_APXSR_STATUS_CK';
alter table orac_core.knowledge_apex_search_requests add constraint kn_apxsr_status_ck
  check (status_code in ('QUEUED', 'PROCESSING', 'COMPLETED', 'NO_EVIDENCE', 'FAILED'));
--rollback alter table orac_core.knowledge_apex_search_requests drop constraint kn_apxsr_status_ck;

--changeset clive:create_constraint_orac_core_kn_apxsr_results_ck context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_APXSR_RESULTS_CK';
alter table orac_core.knowledge_apex_search_requests add constraint kn_apxsr_results_ck
  check (result_refs_json is json);
--rollback alter table orac_core.knowledge_apex_search_requests drop constraint kn_apxsr_results_ck;
