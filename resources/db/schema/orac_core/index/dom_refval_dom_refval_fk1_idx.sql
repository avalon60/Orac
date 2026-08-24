--liquibase formatted sql

--changeset clive:create_index_orac_core_dom_refval_dom_refval_fk1_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'DOM_REFVAL_DOM_REFVAL_FK1_IDX';
-- __author__: clive
-- __date__: 2026-08-08
-- __description__: supports parent reference joins and self-referencing foreign-key locking

create index orac_core.dom_refval_dom_refval_fk1_idx
  on orac_core.domain_ref_values (parent_domain_code, parent_ref_value_code);

--rollback drop index orac_core.dom_refval_dom_refval_fk1_idx;
