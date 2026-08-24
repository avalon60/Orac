--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Defines foreign keys for llm_model_capabilities.

--changeset clive:create_constraint_orac_core_llm_modcap_llm_reg_fk1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_MODCAP_LLM_REG_FK1';
alter table orac_core.llm_model_capabilities add constraint llm_modcap_llm_reg_fk1
  foreign key (llm_id)
  references orac_core.llm_registry (llm_id);
--rollback alter table orac_core.llm_model_capabilities drop constraint llm_modcap_llm_reg_fk1;

--changeset clive:create_constraint_orac_core_llm_modcap_llm_prov_fk1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_MODCAP_LLM_PROV_FK1';
alter table orac_core.llm_model_capabilities add constraint llm_modcap_llm_prov_fk1
  foreign key (provider_code)
  references orac_core.llm_providers (provider_code);
--rollback alter table orac_core.llm_model_capabilities drop constraint llm_modcap_llm_prov_fk1;

--changeset clive:create_constraint_orac_core_llm_modcap_llm_cap_fk1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_MODCAP_LLM_CAP_FK1';
alter table orac_core.llm_model_capabilities add constraint llm_modcap_llm_cap_fk1
  foreign key (capability_code)
  references orac_core.llm_capabilities (capability_code);
--rollback alter table orac_core.llm_model_capabilities drop constraint llm_modcap_llm_cap_fk1;

--changeset clive:create_constraint_orac_core_llm_modcap_dom_refval_fk1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_MODCAP_DOM_REFVAL_FK1';
alter table orac_core.llm_model_capabilities add constraint llm_modcap_dom_refval_fk1
  foreign key (evidence_state_domain_code, evidence_state_ref_value_code)
  references orac_core.domain_ref_values (domain_code, ref_value_code);
--rollback alter table orac_core.llm_model_capabilities drop constraint llm_modcap_dom_refval_fk1;

