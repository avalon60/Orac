--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_fk_orac_fch_src_srch_res_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'ORAC_FCH_SRC_SRCH_RES_FK1';
-- __author__: clive
-- __date__: 2026-05-26
-- __description__: search result foreign key for orac_fetched_sources


alter table orac_core.orac_fetched_sources
  add constraint orac_fch_src_srch_res_fk1
  foreign key
  (
    search_result_id
  )
  references orac_core.orac_search_results
  (
    search_result_id
  )
;


--rollback alter table orac_core.orac_fetched_sources drop constraint orac_fch_src_srch_res_fk1;
