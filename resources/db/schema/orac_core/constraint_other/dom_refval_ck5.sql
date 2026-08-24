--liquibase formatted sql

--changeset clive:create_constraint_orac_core_dom_refval_ck5 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'DOM_REFVAL_CK5';
-- __author__: clive
-- __date__: 2026-08-08
-- __description__: prevent a reference value from naming itself as its parent

alter table orac_core.domain_ref_values add constraint dom_refval_ck5
  check (
    parent_domain_code is null
    or domain_code <> parent_domain_code
    or ref_value_code <> parent_ref_value_code
  );

--rollback alter table orac_core.domain_ref_values drop constraint dom_refval_ck5;
