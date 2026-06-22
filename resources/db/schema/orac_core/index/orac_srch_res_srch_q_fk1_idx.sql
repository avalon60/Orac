--liquibase formatted sql

--changeset clive:create_index_orac_core_index_orac_srch_res_srch_q_fk1_idx context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'ORAC_SRCH_RES_SRCH_Q_FK1_IDX';
-- __author__: clive
-- __date__: 2026-05-26
-- __description__: foreign key index for orac_search_results to orac_search_queries


create index orac_core.orac_srch_res_srch_q_fk1_idx
  on orac_core.orac_search_results
  (
    search_query_id asc
  )
;


--rollback drop index orac_core.orac_srch_res_srch_q_fk1_idx;
