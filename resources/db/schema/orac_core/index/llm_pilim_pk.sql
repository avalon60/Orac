--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Creates the primary-key index for llm_provider_input_limits.

--changeset clive:create_index_orac_core_llm_pilim_pk context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_PILIM_PK';
create unique index orac_core.llm_pilim_pk on orac_core.llm_provider_input_limits (provider_input_limit_id);
--rollback drop index orac_core.llm_pilim_pk;
