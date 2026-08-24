--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Creates foreign-key indexes for llm_model_cap_inputs.

--changeset clive:create_index_orac_core_llm_mcin_llm_modcap_fk1_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_MCIN_LLM_MODCAP_FK1_IDX';
create index orac_core.llm_mcin_llm_modcap_fk1_idx on orac_core.llm_model_cap_inputs (model_capability_id);
--rollback drop index orac_core.llm_mcin_llm_modcap_fk1_idx;

--changeset clive:create_index_orac_core_llm_mcin_llm_inrep_fk1_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_MCIN_LLM_INREP_FK1_IDX';
create index orac_core.llm_mcin_llm_inrep_fk1_idx on orac_core.llm_model_cap_inputs (representation_code);
--rollback drop index orac_core.llm_mcin_llm_inrep_fk1_idx;

--changeset clive:create_index_orac_core_llm_mcin_llm_mtype_fk1_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_MCIN_LLM_MTYPE_FK1_IDX';
create index orac_core.llm_mcin_llm_mtype_fk1_idx on orac_core.llm_model_cap_inputs (media_type);
--rollback drop index orac_core.llm_mcin_llm_mtype_fk1_idx;

