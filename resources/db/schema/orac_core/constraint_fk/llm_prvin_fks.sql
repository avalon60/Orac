--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Defines foreign keys for llm_provider_inputs.

--changeset clive:create_constraint_orac_core_llm_prvin_llm_prov_fk1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_PRVIN_LLM_PROV_FK1';
alter table orac_core.llm_provider_inputs add constraint llm_prvin_llm_prov_fk1
  foreign key (provider_code)
  references orac_core.llm_providers (provider_code);
--rollback alter table orac_core.llm_provider_inputs drop constraint llm_prvin_llm_prov_fk1;

--changeset clive:create_constraint_orac_core_llm_prvin_llm_inrep_fk1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_PRVIN_LLM_INREP_FK1';
alter table orac_core.llm_provider_inputs add constraint llm_prvin_llm_inrep_fk1
  foreign key (representation_code)
  references orac_core.llm_input_representations (representation_code);
--rollback alter table orac_core.llm_provider_inputs drop constraint llm_prvin_llm_inrep_fk1;

--changeset clive:create_constraint_orac_core_llm_prvin_llm_mtype_fk1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_PRVIN_LLM_MTYPE_FK1';
alter table orac_core.llm_provider_inputs add constraint llm_prvin_llm_mtype_fk1
  foreign key (media_type)
  references orac_core.llm_input_media_types (media_type);
--rollback alter table orac_core.llm_provider_inputs drop constraint llm_prvin_llm_mtype_fk1;

--changeset clive:create_constraint_orac_core_llm_prvin_dom_refval_fk1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_PRVIN_DOM_REFVAL_FK1';
alter table orac_core.llm_provider_inputs add constraint llm_prvin_dom_refval_fk1
  foreign key (evidence_state_domain_code, evidence_state_ref_value_code)
  references orac_core.domain_ref_values (domain_code, ref_value_code);
--rollback alter table orac_core.llm_provider_inputs drop constraint llm_prvin_dom_refval_fk1;

--changeset clive:create_constraint_orac_core_llm_prvin_dom_refval_fk2 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_PRVIN_DOM_REFVAL_FK2';
alter table orac_core.llm_provider_inputs add constraint llm_prvin_dom_refval_fk2
  foreign key (adapter_status_domain_code, adapter_status_ref_value_code)
  references orac_core.domain_ref_values (domain_code, ref_value_code);
--rollback alter table orac_core.llm_provider_inputs drop constraint llm_prvin_dom_refval_fk2;

