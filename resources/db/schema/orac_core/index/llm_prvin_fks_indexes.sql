--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Creates foreign-key indexes for llm_provider_inputs.

--changeset clive:create_index_orac_core_llm_prvin_llm_prov_fk1_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_PRVIN_LLM_PROV_FK1_IDX';
create index orac_core.llm_prvin_llm_prov_fk1_idx on orac_core.llm_provider_inputs (provider_code);
--rollback drop index orac_core.llm_prvin_llm_prov_fk1_idx;

--changeset clive:create_index_orac_core_llm_prvin_llm_inrep_fk1_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_PRVIN_LLM_INREP_FK1_IDX';
create index orac_core.llm_prvin_llm_inrep_fk1_idx on orac_core.llm_provider_inputs (representation_code);
--rollback drop index orac_core.llm_prvin_llm_inrep_fk1_idx;

--changeset clive:create_index_orac_core_llm_prvin_llm_mtype_fk1_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_PRVIN_LLM_MTYPE_FK1_IDX';
create index orac_core.llm_prvin_llm_mtype_fk1_idx on orac_core.llm_provider_inputs (media_type);
--rollback drop index orac_core.llm_prvin_llm_mtype_fk1_idx;

--changeset clive:create_index_orac_core_llm_prvin_dom_refval_fk1_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_PRVIN_DOM_REFVAL_FK1_IDX';
create index orac_core.llm_prvin_dom_refval_fk1_idx on orac_core.llm_provider_inputs (evidence_state_domain_code, evidence_state_ref_value_code);
--rollback drop index orac_core.llm_prvin_dom_refval_fk1_idx;

--changeset clive:create_index_orac_core_llm_prvin_dom_refval_fk2_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_PRVIN_DOM_REFVAL_FK2_IDX';
create index orac_core.llm_prvin_dom_refval_fk2_idx on orac_core.llm_provider_inputs (adapter_status_domain_code, adapter_status_ref_value_code);
--rollback drop index orac_core.llm_prvin_dom_refval_fk2_idx;

