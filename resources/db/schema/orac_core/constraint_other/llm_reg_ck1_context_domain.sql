--liquibase formatted sql

--changeset clive:create_constraint_orac_core_llm_reg_ck1_context_domain context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_REG_CK1';
alter table orac_core.llm_registry add constraint llm_reg_ck1
  check (llm_context_policy_domain_code = 'LLM_CONTEXT_POLICY');
--rollback alter table orac_core.llm_registry drop constraint llm_reg_ck1;
