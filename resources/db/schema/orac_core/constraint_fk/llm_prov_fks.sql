--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Defines foreign keys for llm_providers.

--changeset clive:create_constraint_orac_core_llm_prov_dom_refval_fk1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_PROV_DOM_REFVAL_FK1';
alter table orac_core.llm_providers add constraint llm_prov_dom_refval_fk1
  foreign key (processing_locality_domain_code, processing_locality_ref_value_code)
  references orac_core.domain_ref_values (domain_code, ref_value_code);
--rollback alter table orac_core.llm_providers drop constraint llm_prov_dom_refval_fk1;

--changeset clive:create_constraint_orac_core_llm_prov_dom_refval_fk2 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_PROV_DOM_REFVAL_FK2';
alter table orac_core.llm_providers add constraint llm_prov_dom_refval_fk2
  foreign key (metadata_status_domain_code, metadata_status_ref_value_code)
  references orac_core.domain_ref_values (domain_code, ref_value_code);
--rollback alter table orac_core.llm_providers drop constraint llm_prov_dom_refval_fk2;

