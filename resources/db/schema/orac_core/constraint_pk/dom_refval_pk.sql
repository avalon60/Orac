--liquibase formatted sql

--changeset clive:create_constraint_orac_core_dom_refval_pk context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'DOM_REFVAL_PK';
-- __author__: clive
-- __date__: 2026-08-02
-- __description__: primary key for domain_ref_values

alter table orac_core.domain_ref_values add constraint dom_refval_pk
  primary key (domain_code, ref_value_code) using index orac_core.dom_refval_pk;

--rollback alter table orac_core.domain_ref_values drop constraint dom_refval_pk;
