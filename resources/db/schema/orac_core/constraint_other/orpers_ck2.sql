--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_other_orpers_ck2 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'ORPERS_CK2';
alter table orac_core.orac_personalities
  add constraint orpers_ck2
  check (sarcasm_level in (0,1,2));

--rollback alter table orac_core.orac_personalities drop constraint orpers_ck2;
