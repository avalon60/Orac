--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 13-Aug-2026
-- Description: Creates the knowledge retrieval event primary key.

--changeset clive:create_constraint_pk_orac_core_kn_retev_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_RETEV_PK';
alter table orac_core.knowledge_retrieval_events add constraint kn_retev_pk
  primary key (retrieval_event_id)
  using index orac_core.kn_retev_pk;
--rollback alter table orac_core.knowledge_retrieval_events drop constraint kn_retev_pk;
