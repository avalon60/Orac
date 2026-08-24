--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Creates foreign-key indexes for llm_model_capabilities.

--changeset clive:create_index_orac_core_llm_modcap_llm_reg_fk1_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_MODCAP_LLM_REG_FK1_IDX';
create index orac_core.llm_modcap_llm_reg_fk1_idx on orac_core.llm_model_capabilities (llm_id);
--rollback drop index orac_core.llm_modcap_llm_reg_fk1_idx;

--changeset clive:create_index_orac_core_llm_modcap_llm_prov_fk1_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_MODCAP_LLM_PROV_FK1_IDX';
create index orac_core.llm_modcap_llm_prov_fk1_idx on orac_core.llm_model_capabilities (provider_code);
--rollback drop index orac_core.llm_modcap_llm_prov_fk1_idx;

--changeset clive:create_index_orac_core_llm_modcap_llm_cap_fk1_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_MODCAP_LLM_CAP_FK1_IDX';
create index orac_core.llm_modcap_llm_cap_fk1_idx on orac_core.llm_model_capabilities (capability_code);
--rollback drop index orac_core.llm_modcap_llm_cap_fk1_idx;

--changeset clive:create_index_orac_core_llm_modcap_dom_refval_fk1_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_MODCAP_DOM_REFVAL_FK1_IDX';
create index orac_core.llm_modcap_dom_refval_fk1_idx on orac_core.llm_model_capabilities (evidence_state_domain_code, evidence_state_ref_value_code);
--rollback drop index orac_core.llm_modcap_dom_refval_fk1_idx;

