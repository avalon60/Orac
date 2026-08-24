--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Enforces controlled model-input limit dimensions and values.

--changeset clive:create_constraints_orac_core_llm_milim_checks context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_MILIM_CK1';
alter table orac_core.llm_model_input_limits add (
  constraint llm_milim_ck1 check (limit_dimension_domain_code = 'LIMIT_DIMENSION'),
  constraint llm_milim_ck2 check (bound_operator_domain_code = 'BOUND_OPERATOR'),
  constraint llm_milim_ck3 check (limit_unit_domain_code = 'LIMIT_UNIT'),
  constraint llm_milim_ck4 check (limit_value >= 0),
  constraint llm_milim_ck5 check (effective_to is null or effective_to > effective_from)
);
--rollback alter table orac_core.llm_model_input_limits drop constraint llm_milim_ck5; alter table orac_core.llm_model_input_limits drop constraint llm_milim_ck4; alter table orac_core.llm_model_input_limits drop constraint llm_milim_ck3; alter table orac_core.llm_model_input_limits drop constraint llm_milim_ck2; alter table orac_core.llm_model_input_limits drop constraint llm_milim_ck1;
