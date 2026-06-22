--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_other_llm_reg_ck1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_REG_CK1';
-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac_core.llm_registry
  add constraint llm_reg_ck1
  check (context_policy in ('app', 'external', 'hybrid', 'model', 'unresolved'))
;

--rollback alter table orac_core.llm_registry drop constraint llm_reg_ck1;
