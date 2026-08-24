--liquibase formatted sql

--changeset clive:create_constraint_orac_core_prfdfn_ck3_pref_lov_type context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PRFDFN_CK3';
alter table orac_core.preference_definitions add constraint prfdfn_ck3
  check (pref_lov_type_domain_code = 'PREF_LOV_TYPE');
--rollback alter table orac_core.preference_definitions drop constraint prfdfn_ck3;
