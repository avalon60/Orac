--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Creates the registry provider foreign-key index.

--changeset clive:create_index_orac_core_llm_reg_llm_prov_fk1_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_REG_LLM_PROV_FK1_IDX';
create index orac_core.llm_reg_llm_prov_fk1_idx
  on orac_core.llm_registry (provider);
--rollback drop index orac_core.llm_reg_llm_prov_fk1_idx;

