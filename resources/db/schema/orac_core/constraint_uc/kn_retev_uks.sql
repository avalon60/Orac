--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 13-Aug-2026
-- Description: Prevents duplicate decision and outcome audit events.

--changeset clive:create_constraint_uc_orac_core_kn_retev_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_RETEV_UK1';
alter table orac_core.knowledge_retrieval_events add constraint kn_retev_uk1
  unique (retrieval_id, event_type_code)
  using index orac_core.kn_retev_uk1_idx;
--rollback alter table orac_core.knowledge_retrieval_events drop constraint kn_retev_uk1;
