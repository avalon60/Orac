--liquibase formatted sql

--changeset clive:create_index_orac_core_index_tmzone_uk1_idx context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'TMZONE_UK1_IDX';
-- __author__: clive
-- __date__: 2026-04-27
-- __description__: unique index for canonical timezone name

create unique index orac_core.tmzone_uk1_idx
  on orac_core.timezones
  (
    tz_name asc
  )
;

--rollback drop index orac_core.tmzone_uk1_idx;
