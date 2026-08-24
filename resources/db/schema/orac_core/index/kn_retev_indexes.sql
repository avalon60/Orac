--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 13-Aug-2026
-- Description: Creates indexes for knowledge retrieval audit events.

--changeset clive:create_index_orac_core_kn_retev_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_RETEV_PK';
create unique index orac_core.kn_retev_pk
  on orac_core.knowledge_retrieval_events (retrieval_event_id);
--rollback drop index orac_core.kn_retev_pk;

--changeset clive:create_index_orac_core_kn_retev_uk1_idx context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_RETEV_UK1_IDX';
create unique index orac_core.kn_retev_uk1_idx
  on orac_core.knowledge_retrieval_events (retrieval_id, event_type_code);
--rollback drop index orac_core.kn_retev_uk1_idx;

--changeset clive:create_index_orac_core_kn_retev_idx1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_RETEV_IDX1';
create index orac_core.kn_retev_idx1
  on orac_core.knowledge_retrieval_events (knowledge_scope_id, event_on);
--rollback drop index orac_core.kn_retev_idx1;

--changeset clive:create_index_orac_core_kn_retev_idx2 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_RETEV_IDX2';
create index orac_core.kn_retev_idx2
  on orac_core.knowledge_retrieval_events (user_id, event_on);
--rollback drop index orac_core.kn_retev_idx2;
