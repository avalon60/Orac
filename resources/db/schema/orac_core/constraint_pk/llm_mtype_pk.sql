--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Creates the primary key for llm_input_media_types.

--changeset clive:create_constraint_orac_core_llm_mtype_pk context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_MTYPE_PK';
alter table orac_core.llm_input_media_types add constraint llm_mtype_pk primary key (media_type) using index orac_core.llm_mtype_pk;
--rollback alter table orac_core.llm_input_media_types drop constraint llm_mtype_pk;
