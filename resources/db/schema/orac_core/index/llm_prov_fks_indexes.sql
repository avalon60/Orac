--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Creates foreign-key indexes for llm_providers.

--changeset clive:create_index_orac_core_llm_prov_dom_refval_fk1_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_PROV_DOM_REFVAL_FK1_IDX';
create index orac_core.llm_prov_dom_refval_fk1_idx on orac_core.llm_providers (processing_locality_domain_code, processing_locality_ref_value_code);
--rollback drop index orac_core.llm_prov_dom_refval_fk1_idx;

--changeset clive:create_index_orac_core_llm_prov_dom_refval_fk2_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_PROV_DOM_REFVAL_FK2_IDX';
create index orac_core.llm_prov_dom_refval_fk2_idx on orac_core.llm_providers (metadata_status_domain_code, metadata_status_ref_value_code);
--rollback drop index orac_core.llm_prov_dom_refval_fk2_idx;

