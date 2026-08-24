--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Creates the primary key for llm_input_representations.

--changeset clive:create_constraint_orac_core_llm_inrep_pk context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_INREP_PK';
alter table orac_core.llm_input_representations add constraint llm_inrep_pk primary key (representation_code) using index orac_core.llm_inrep_pk;
--rollback alter table orac_core.llm_input_representations drop constraint llm_inrep_pk;
