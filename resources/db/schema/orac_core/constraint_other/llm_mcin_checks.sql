--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Enforces effective periods for evidenced model inputs.

--changeset clive:create_constraint_orac_core_llm_mcin_ck1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_MCIN_CK1';
alter table orac_core.llm_model_cap_inputs add constraint llm_mcin_ck1
  check (effective_to is null or effective_to > effective_from);
--rollback alter table orac_core.llm_model_cap_inputs drop constraint llm_mcin_ck1;
