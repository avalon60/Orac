--liquibase formatted sql

--changeset clive:create_constraint_orac_core_user_pref_prfdfn_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'USER_PREF_PRFDFN_FK1';
alter table orac_core.user_preferences add constraint user_pref_prfdfn_fk1
  foreign key (pref_key) references orac_core.preference_definitions (pref_key);
--rollback alter table orac_core.user_preferences drop constraint user_pref_prfdfn_fk1;
