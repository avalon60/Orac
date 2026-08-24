--liquibase formatted sql

--changeset clive:create_constraint_orac_core_dom_refval_dom_codes_fk1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'DOM_REFVAL_DOM_CODES_FK1';
-- __author__: clive
-- __date__: 2026-08-02
-- __description__: reference-value ownership by a reference-data domain

alter table orac_core.domain_ref_values
  add constraint dom_refval_dom_codes_fk1 foreign key (domain_code)
  references orac_core.domain_codes (domain_code);

--rollback alter table orac_core.domain_ref_values drop constraint dom_refval_dom_codes_fk1;
