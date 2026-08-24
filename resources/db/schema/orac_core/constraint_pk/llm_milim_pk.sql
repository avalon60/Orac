--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Creates the primary key for llm_model_input_limits.

--changeset clive:create_constraint_orac_core_llm_milim_pk context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_MILIM_PK';
alter table orac_core.llm_model_input_limits add constraint llm_milim_pk primary key (model_input_limit_id) using index orac_core.llm_milim_pk;
--rollback alter table orac_core.llm_model_input_limits drop constraint llm_milim_pk;
