--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Creates the primary-key index for llm_input_media_types.

--changeset clive:create_index_orac_core_llm_mtype_pk context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_MTYPE_PK';
create unique index orac_core.llm_mtype_pk on orac_core.llm_input_media_types (media_type);
--rollback drop index orac_core.llm_mtype_pk;
