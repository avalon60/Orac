--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Defines foreign keys for llm_provider_input_limits.

--changeset clive:create_constraint_orac_core_llm_pilim_llm_prvin_fk1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_PILIM_LLM_PRVIN_FK1';
alter table orac_core.llm_provider_input_limits add constraint llm_pilim_llm_prvin_fk1
  foreign key (provider_input_id)
  references orac_core.llm_provider_inputs (provider_input_id);
--rollback alter table orac_core.llm_provider_input_limits drop constraint llm_pilim_llm_prvin_fk1;

--changeset clive:create_constraint_orac_core_llm_pilim_dom_refval_fk1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_PILIM_DOM_REFVAL_FK1';
alter table orac_core.llm_provider_input_limits add constraint llm_pilim_dom_refval_fk1
  foreign key (limit_dimension_domain_code, limit_dimension_ref_value_code)
  references orac_core.domain_ref_values (domain_code, ref_value_code);
--rollback alter table orac_core.llm_provider_input_limits drop constraint llm_pilim_dom_refval_fk1;

--changeset clive:create_constraint_orac_core_llm_pilim_dom_refval_fk2 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_PILIM_DOM_REFVAL_FK2';
alter table orac_core.llm_provider_input_limits add constraint llm_pilim_dom_refval_fk2
  foreign key (bound_operator_domain_code, bound_operator_ref_value_code)
  references orac_core.domain_ref_values (domain_code, ref_value_code);
--rollback alter table orac_core.llm_provider_input_limits drop constraint llm_pilim_dom_refval_fk2;

--changeset clive:create_constraint_orac_core_llm_pilim_dom_refval_fk3 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_PILIM_DOM_REFVAL_FK3';
alter table orac_core.llm_provider_input_limits add constraint llm_pilim_dom_refval_fk3
  foreign key (limit_unit_domain_code, limit_unit_ref_value_code)
  references orac_core.domain_ref_values (domain_code, ref_value_code);
--rollback alter table orac_core.llm_provider_input_limits drop constraint llm_pilim_dom_refval_fk3;

