--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_uc_tmzone_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'TMZONE_UK1';
-- __author__: clive
-- __date__: 2026-04-27
-- __description__: unique constraint for canonical timezone name

alter table orac_core.timezones
  add constraint tmzone_uk1
  unique (tz_name)
;

--rollback alter table orac_core.timezones drop constraint tmzone_uk1;
