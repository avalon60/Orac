--liquibase formatted sql

--changeset clive:create_constraint_orac_core_dom_codes_ck1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'DOM_CODES_CK1';
-- __author__: clive
-- __date__: 2026-08-02
-- __description__: flag validation for domain_codes

alter table orac_core.domain_codes add constraint dom_codes_ck1
  check (active_yn in ('Y', 'N') and system_required_yn in ('Y', 'N'));

--rollback alter table orac_core.domain_codes drop constraint dom_codes_ck1;
