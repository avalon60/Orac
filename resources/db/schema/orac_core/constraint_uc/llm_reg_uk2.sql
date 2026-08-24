--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Defines unique provider/model registry identities.

--changeset clive:create_constraint_orac_core_llm_reg_uk2 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_REG_UK2';
alter table orac_core.llm_registry add constraint llm_reg_uk2
  unique (provider, model) using index orac_core.llm_reg_uk2_idx;
--rollback alter table orac_core.llm_registry drop constraint llm_reg_uk2;
