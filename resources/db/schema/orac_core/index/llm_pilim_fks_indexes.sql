--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Creates foreign-key indexes for llm_provider_input_limits.

--changeset clive:create_index_orac_core_llm_pilim_llm_prvin_fk1_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_PILIM_LLM_PRVIN_FK1_IDX';
create index orac_core.llm_pilim_llm_prvin_fk1_idx on orac_core.llm_provider_input_limits (provider_input_id);
--rollback drop index orac_core.llm_pilim_llm_prvin_fk1_idx;

--changeset clive:create_index_orac_core_llm_pilim_dom_refval_fk1_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_PILIM_DOM_REFVAL_FK1_IDX';
create index orac_core.llm_pilim_dom_refval_fk1_idx on orac_core.llm_provider_input_limits (limit_dimension_domain_code, limit_dimension_ref_value_code);
--rollback drop index orac_core.llm_pilim_dom_refval_fk1_idx;

--changeset clive:create_index_orac_core_llm_pilim_dom_refval_fk2_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_PILIM_DOM_REFVAL_FK2_IDX';
create index orac_core.llm_pilim_dom_refval_fk2_idx on orac_core.llm_provider_input_limits (bound_operator_domain_code, bound_operator_ref_value_code);
--rollback drop index orac_core.llm_pilim_dom_refval_fk2_idx;

--changeset clive:create_index_orac_core_llm_pilim_dom_refval_fk3_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_PILIM_DOM_REFVAL_FK3_IDX';
create index orac_core.llm_pilim_dom_refval_fk3_idx on orac_core.llm_provider_input_limits (limit_unit_domain_code, limit_unit_ref_value_code);
--rollback drop index orac_core.llm_pilim_dom_refval_fk3_idx;

