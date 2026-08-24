--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Creates the primary key for llm_provider_input_limits.

--changeset clive:create_constraint_orac_core_llm_pilim_pk context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_PILIM_PK';
alter table orac_core.llm_provider_input_limits add constraint llm_pilim_pk primary key (provider_input_limit_id) using index orac_core.llm_pilim_pk;
--rollback alter table orac_core.llm_provider_input_limits drop constraint llm_pilim_pk;
