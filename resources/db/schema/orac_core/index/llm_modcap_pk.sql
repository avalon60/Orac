--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Creates the primary-key index for llm_model_capabilities.

--changeset clive:create_index_orac_core_llm_modcap_pk context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_MODCAP_PK';
create unique index orac_core.llm_modcap_pk on orac_core.llm_model_capabilities (model_capability_id);
--rollback drop index orac_core.llm_modcap_pk;
