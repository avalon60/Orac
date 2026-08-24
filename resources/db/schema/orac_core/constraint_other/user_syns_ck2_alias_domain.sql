--liquibase formatted sql

--changeset clive:create_constraint_orac_core_user_syns_ck2_alias_domain context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'USER_SYNS_CK2';
alter table orac_core.user_synonyms add constraint user_syns_ck2
  check (user_alias_type_domain_code = 'USER_ALIAS_TYPE');
--rollback alter table orac_core.user_synonyms drop constraint user_syns_ck2;
