--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Prevents duplicate provider transport declarations.

--changeset clive:create_index_orac_core_llm_prvin_uk1_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_PRVIN_UK1_IDX';
create unique index orac_core.llm_prvin_uk1_idx
  on orac_core.llm_provider_inputs (
    provider_code,
    representation_code,
    nvl(media_type, '~')
  );
--rollback drop index orac_core.llm_prvin_uk1_idx;
