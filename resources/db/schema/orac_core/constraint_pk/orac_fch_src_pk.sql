--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_pk_orac_fch_src_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'ORAC_FCH_SRC_PK';
-- __author__: clive
-- __date__: 2026-05-26
-- __description__: primary key for orac_fetched_sources


alter table orac_core.orac_fetched_sources
  add constraint orac_fch_src_pk
  primary key (fetched_source_id)
;


--rollback alter table orac_core.orac_fetched_sources drop constraint orac_fch_src_pk;
