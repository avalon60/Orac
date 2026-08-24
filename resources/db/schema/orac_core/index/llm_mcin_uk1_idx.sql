--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Prevents duplicate representation/MIME rows for one model evidence record.

--changeset clive:create_index_orac_core_llm_mcin_uk1_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_MCIN_UK1_IDX';
create unique index orac_core.llm_mcin_uk1_idx
  on orac_core.llm_model_cap_inputs (
    model_capability_id,
    representation_code,
    nvl(media_type, '~')
  );
--rollback drop index orac_core.llm_mcin_uk1_idx;
