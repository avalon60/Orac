--liquibase formatted sql

--changeset clive:create_index_orac_core_index_prfdfn_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'PRFDFN_PK';
-- __author__: clive
-- __date__: 2026-04-27
-- __description__: generated/synchronised by split_ddl; one object per file


create unique index orac_core.prfdfn_pk
  on orac_core.preference_definitions
  (
    pref_def_id asc
  )
;

--rollback drop index orac_core.prfdfn_pk;
