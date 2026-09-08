--liquibase formatted sql
-- Author: clive
-- Date: 31-Aug-2026
-- Description: Allows only one open evidence row per model capability.

--changeset clive:create_index_orac_core_llm_modcap_uk1_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_MODCAP_UK1_IDX';
create unique index orac_core.llm_modcap_uk1_idx
  on orac_core.llm_model_capabilities (
    case when effective_to is null then llm_id end,
    case when effective_to is null then capability_code end
  );
--rollback drop index orac_core.llm_modcap_uk1_idx;
