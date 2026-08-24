--liquibase formatted sql

--changeset clive:create_constraint_orac_core_dom_refval_dom_refval_fk1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'DOM_REFVAL_DOM_REFVAL_FK1';
-- __author__: clive
-- __date__: 2026-08-08
-- __description__: optional parent reference value for cross-domain grouping

alter table orac_core.domain_ref_values
  add constraint dom_refval_dom_refval_fk1
  foreign key (parent_domain_code, parent_ref_value_code)
  references orac_core.domain_ref_values (domain_code, ref_value_code);

--rollback alter table orac_core.domain_ref_values drop constraint dom_refval_dom_refval_fk1;
