--liquibase formatted sql

--changeset clive:create_index_orac_core_index_orac_srch_res_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'ORAC_SRCH_RES_PK';
-- __author__: clive
-- __date__: 2026-05-26
-- __description__: primary key index for orac_search_results


create unique index orac_core.orac_srch_res_pk
  on orac_core.orac_search_results
  (
    search_result_id asc
  )
;


--rollback drop index orac_core.orac_srch_res_pk;
