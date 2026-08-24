--liquibase formatted sql

--changeset clive:create_constraint_orac_core_prfdfn_ck1_pref_value_type context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PRFDFN_CK1';
alter table orac_core.preference_definitions add constraint prfdfn_ck1
  check (pref_value_type_domain_code = 'PREF_VALUE_TYPE');
--rollback alter table orac_core.preference_definitions drop constraint prfdfn_ck1;
