--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Enforces representation code syntax.

--changeset clive:create_constraint_orac_core_llm_inrep_ck1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_INREP_CK1';
alter table orac_core.llm_input_representations add constraint llm_inrep_ck1
  check (regexp_like(representation_code, '^[a-z][a-z0-9_]{0,99}$'));
--rollback alter table orac_core.llm_input_representations drop constraint llm_inrep_ck1;
