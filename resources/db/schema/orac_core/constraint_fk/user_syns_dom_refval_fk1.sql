--liquibase formatted sql

--changeset clive:create_constraint_orac_core_user_syns_dom_refval_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'USER_SYNS_DOM_REFVAL_FK1';
alter table orac_core.user_synonyms add constraint user_syns_dom_refval_fk1
  foreign key (user_alias_type_domain_code, user_alias_type_ref_value_code)
  references orac_core.domain_ref_values (domain_code, ref_value_code);
--rollback alter table orac_core.user_synonyms drop constraint user_syns_dom_refval_fk1;
