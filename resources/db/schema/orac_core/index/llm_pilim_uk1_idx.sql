--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Prevents duplicate provider limit dimensions in one effective period.

--changeset clive:create_index_orac_core_llm_pilim_uk1_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_PILIM_UK1_IDX';
create unique index orac_core.llm_pilim_uk1_idx
  on orac_core.llm_provider_input_limits (
    provider_input_id,
    limit_dimension_ref_value_code,
    effective_from
  );
--rollback drop index orac_core.llm_pilim_uk1_idx;
