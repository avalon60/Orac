--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Creates the primary key for llm_capabilities.

--changeset clive:create_constraint_orac_core_llm_cap_pk context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_CAP_PK';
alter table orac_core.llm_capabilities add constraint llm_cap_pk primary key (capability_code) using index orac_core.llm_cap_pk;
--rollback alter table orac_core.llm_capabilities drop constraint llm_cap_pk;
