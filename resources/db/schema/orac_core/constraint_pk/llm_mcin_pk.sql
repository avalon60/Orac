--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Creates the primary key for llm_model_cap_inputs.

--changeset clive:create_constraint_orac_core_llm_mcin_pk context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_MCIN_PK';
alter table orac_core.llm_model_cap_inputs add constraint llm_mcin_pk primary key (model_cap_input_id) using index orac_core.llm_mcin_pk;
--rollback alter table orac_core.llm_model_cap_inputs drop constraint llm_mcin_pk;
