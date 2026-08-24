--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Creates the primary key for llm_providers.

--changeset clive:create_constraint_orac_core_llm_prov_pk context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_PROV_PK';
alter table orac_core.llm_providers add constraint llm_prov_pk primary key (provider_code) using index orac_core.llm_prov_pk;
--rollback alter table orac_core.llm_providers drop constraint llm_prov_pk;
