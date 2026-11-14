--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 25-Oct-2026
-- Description: Supports bounded queue claiming and expiry cleanup.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_index_orac_core_kn_apxsr_queue_ix context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_APXSR_QUEUE_IX';
create index orac_core.kn_apxsr_queue_ix
  on orac_core.knowledge_apex_search_requests (status_code, created_on);
--rollback drop index orac_core.kn_apxsr_queue_ix;

--changeset clive:create_index_orac_core_kn_apxsr_exp_ix context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_APXSR_EXP_IX';
create index orac_core.kn_apxsr_exp_ix
  on orac_core.knowledge_apex_search_requests (expires_on);
--rollback drop index orac_core.kn_apxsr_exp_ix;
