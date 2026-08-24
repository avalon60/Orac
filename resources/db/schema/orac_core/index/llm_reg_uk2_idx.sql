--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Enforces unique provider/model registry identities.

--changeset clive:create_index_orac_core_llm_reg_uk2_idx context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from (select provider, model from orac_core.llm_registry group by provider, model having count(*) > 1);
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_REG_UK2_IDX';
create unique index orac_core.llm_reg_uk2_idx
  on orac_core.llm_registry (provider, model);
--rollback drop index orac_core.llm_reg_uk2_idx;
