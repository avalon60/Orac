--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Creates the primary key for llm_model_capabilities.

--changeset clive:create_constraint_orac_core_llm_modcap_pk context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_MODCAP_PK';
alter table orac_core.llm_model_capabilities add constraint llm_modcap_pk primary key (model_capability_id) using index orac_core.llm_modcap_pk;
--rollback alter table orac_core.llm_model_capabilities drop constraint llm_modcap_pk;
