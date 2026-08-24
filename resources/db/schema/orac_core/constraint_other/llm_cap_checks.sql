--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Enforces capability codes and fixed reference domains.

--changeset clive:create_constraints_orac_core_llm_cap_checks context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_CAP_CK1';
alter table orac_core.llm_capabilities add (
  constraint llm_cap_ck1 check (regexp_like(capability_code, '^[a-z][a-z0-9_]{0,99}$')),
  constraint llm_cap_ck2 check (capability_class_domain_code = 'CAPABILITY_CLASS'),
  constraint llm_cap_ck3 check (capability_lifecycle_domain_code = 'CAPABILITY_LIFECYCLE')
);
--rollback alter table orac_core.llm_capabilities drop constraint llm_cap_ck3; alter table orac_core.llm_capabilities drop constraint llm_cap_ck2; alter table orac_core.llm_capabilities drop constraint llm_cap_ck1;
