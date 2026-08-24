--liquibase formatted sql

--changeset clive:create_constraint_orac_core_dom_codes_pk context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'DOM_CODES_PK';
-- __author__: clive
-- __date__: 2026-08-02
-- __description__: primary key for domain_codes

alter table orac_core.domain_codes add constraint dom_codes_pk
  primary key (domain_code) using index orac_core.dom_codes_pk;

--rollback alter table orac_core.domain_codes drop constraint dom_codes_pk;
