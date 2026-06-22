--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_other_prfdfn_ck1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PRFDFN_CK1';
-- __author__: clive
-- __date__: 2026-04-27
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac_core.preference_definitions
  add constraint prfdfn_ck1
  check (value_type in ('string', 'number', 'boolean', 'json'))
;

--rollback alter table orac_core.preference_definitions drop constraint prfdfn_ck1;
