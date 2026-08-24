--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Relates every registry row to a reviewed provider adapter.

--changeset clive:create_constraint_orac_core_llm_reg_llm_prov_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from orac_core.llm_registry r where not exists (select 1 from orac_core.llm_providers p where p.provider_code = r.provider);
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_REG_LLM_PROV_FK1';
alter table orac_core.llm_registry add constraint llm_reg_llm_prov_fk1
  foreign key (provider)
  references orac_core.llm_providers (provider_code);
--rollback alter table orac_core.llm_registry drop constraint llm_reg_llm_prov_fk1;

