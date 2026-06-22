--liquibase formatted sql

--changeset clive:create_index_orac_core_index_tmzone_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'TMZONE_PK';
-- __author__: clive
-- __date__: 2026-04-27
-- __description__: primary key index for timezones

create unique index orac_core.tmzone_pk
  on orac_core.timezones
  (
    timezone_id asc
  )
;

--rollback drop index orac_core.tmzone_pk;
