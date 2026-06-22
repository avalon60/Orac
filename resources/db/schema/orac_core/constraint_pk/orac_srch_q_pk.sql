--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_pk_orac_srch_q_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'ORAC_SRCH_Q_PK';
-- __author__: clive
-- __date__: 2026-05-26
-- __description__: primary key for orac_search_queries


alter table orac_core.orac_search_queries
  add constraint orac_srch_q_pk
  primary key (search_query_id)
;


--rollback alter table orac_core.orac_search_queries drop constraint orac_srch_q_pk;
