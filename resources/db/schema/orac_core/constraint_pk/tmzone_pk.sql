--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_pk_tmzone_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'TMZONE_PK';
-- __author__: clive
-- __date__: 2026-04-27
-- __description__: primary key constraint for timezones

alter table orac_core.timezones
  add constraint tmzone_pk
  primary key (timezone_id)
;

--rollback alter table orac_core.timezones drop constraint tmzone_pk;
