--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Creates foreign-key indexes for llm_capabilities.

--changeset clive:create_index_orac_core_llm_cap_dom_refval_fk1_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_CAP_DOM_REFVAL_FK1_IDX';
create index orac_core.llm_cap_dom_refval_fk1_idx on orac_core.llm_capabilities (capability_class_domain_code, capability_class_ref_value_code);
--rollback drop index orac_core.llm_cap_dom_refval_fk1_idx;

--changeset clive:create_index_orac_core_llm_cap_dom_refval_fk2_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_CAP_DOM_REFVAL_FK2_IDX';
create index orac_core.llm_cap_dom_refval_fk2_idx on orac_core.llm_capabilities (capability_lifecycle_domain_code, capability_lifecycle_ref_value_code);
--rollback drop index orac_core.llm_cap_dom_refval_fk2_idx;

