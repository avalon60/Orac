--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_other_orpers_ck1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'ORPERS_CK1';
alter table orac_core.orac_personalities
  add constraint orpers_ck1
  check (attitude_base_level in (0,1,2));

--rollback alter table orac_core.orac_personalities drop constraint orpers_ck1;
