--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Defines foreign keys for llm_model_cap_inputs.

--changeset clive:create_constraint_orac_core_llm_mcin_llm_modcap_fk1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_MCIN_LLM_MODCAP_FK1';
alter table orac_core.llm_model_cap_inputs add constraint llm_mcin_llm_modcap_fk1
  foreign key (model_capability_id)
  references orac_core.llm_model_capabilities (model_capability_id);
--rollback alter table orac_core.llm_model_cap_inputs drop constraint llm_mcin_llm_modcap_fk1;

--changeset clive:create_constraint_orac_core_llm_mcin_llm_inrep_fk1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_MCIN_LLM_INREP_FK1';
alter table orac_core.llm_model_cap_inputs add constraint llm_mcin_llm_inrep_fk1
  foreign key (representation_code)
  references orac_core.llm_input_representations (representation_code);
--rollback alter table orac_core.llm_model_cap_inputs drop constraint llm_mcin_llm_inrep_fk1;

--changeset clive:create_constraint_orac_core_llm_mcin_llm_mtype_fk1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_MCIN_LLM_MTYPE_FK1';
alter table orac_core.llm_model_cap_inputs add constraint llm_mcin_llm_mtype_fk1
  foreign key (media_type)
  references orac_core.llm_input_media_types (media_type);
--rollback alter table orac_core.llm_model_cap_inputs drop constraint llm_mcin_llm_mtype_fk1;

