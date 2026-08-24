--liquibase formatted sql

--changeset clive:create_constraint_orac_core_dom_refval_ck3 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'DOM_REFVAL_CK3';
-- __author__: clive
-- __date__: 2026-08-02
-- __description__: display sequence and optimistic-lock version validation

alter table orac_core.domain_ref_values add constraint dom_refval_ck3
  check (display_sequence >= 0 and row_version >= 1);

--rollback alter table orac_core.domain_ref_values drop constraint dom_refval_ck3;
