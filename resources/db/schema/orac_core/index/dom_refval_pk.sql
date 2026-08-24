--liquibase formatted sql

--changeset clive:create_index_orac_core_dom_refval_pk context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'DOM_REFVAL_PK';
-- __author__: clive
-- __date__: 2026-08-02
-- __description__: primary-key index for domain_ref_values

create unique index orac_core.dom_refval_pk
  on orac_core.domain_ref_values (domain_code, ref_value_code);

--rollback drop index orac_core.dom_refval_pk;
