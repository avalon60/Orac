--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Defines foreign keys for llm_capabilities.

--changeset clive:create_constraint_orac_core_llm_cap_dom_refval_fk1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_CAP_DOM_REFVAL_FK1';
alter table orac_core.llm_capabilities add constraint llm_cap_dom_refval_fk1
  foreign key (capability_class_domain_code, capability_class_ref_value_code)
  references orac_core.domain_ref_values (domain_code, ref_value_code);
--rollback alter table orac_core.llm_capabilities drop constraint llm_cap_dom_refval_fk1;

--changeset clive:create_constraint_orac_core_llm_cap_dom_refval_fk2 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_CAP_DOM_REFVAL_FK2';
alter table orac_core.llm_capabilities add constraint llm_cap_dom_refval_fk2
  foreign key (capability_lifecycle_domain_code, capability_lifecycle_ref_value_code)
  references orac_core.domain_ref_values (domain_code, ref_value_code);
--rollback alter table orac_core.llm_capabilities drop constraint llm_cap_dom_refval_fk2;

