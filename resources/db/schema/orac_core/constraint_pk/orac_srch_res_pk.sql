--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_pk_orac_srch_res_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'ORAC_SRCH_RES_PK';
-- __author__: clive
-- __date__: 2026-05-26
-- __description__: primary key for orac_search_results


alter table orac_core.orac_search_results
  add constraint orac_srch_res_pk
  primary key (search_result_id)
;


--rollback alter table orac_core.orac_search_results drop constraint orac_srch_res_pk;
