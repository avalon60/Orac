--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_fk_orac_srch_res_orac_srch_q_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'ORAC_SRCH_RES_ORAC_SRCH_Q_FK1';
-- __author__: clive
-- __date__: 2026-05-26
-- __description__: search query foreign key for orac_search_results


alter table orac_core.orac_search_results
  add constraint orac_srch_res_orac_srch_q_fk1
  foreign key
  (
    search_query_id
  )
  references orac_core.orac_search_queries
  (
    search_query_id
  )
;


--rollback alter table orac_core.orac_search_results drop constraint orac_srch_res_orac_srch_q_fk1;
