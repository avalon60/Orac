--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 25-Oct-2026
-- Description: Identifies one plugin APEX knowledge search request.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_constraint_orac_core_kn_apxsr_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_APXSR_PK';
alter table orac_core.knowledge_apex_search_requests add constraint kn_apxsr_pk
  primary key (search_request_id);
--rollback alter table orac_core.knowledge_apex_search_requests drop constraint kn_apxsr_pk;
