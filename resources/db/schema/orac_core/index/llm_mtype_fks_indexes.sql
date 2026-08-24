--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Creates foreign-key indexes for llm_input_media_types.

--changeset clive:create_index_orac_core_llm_mtype_dom_refval_fk1_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'LLM_MTYPE_DOM_REFVAL_FK1_IDX';
create index orac_core.llm_mtype_dom_refval_fk1_idx on orac_core.llm_input_media_types (mime_match_kind_domain_code, mime_match_kind_ref_value_code);
--rollback drop index orac_core.llm_mtype_dom_refval_fk1_idx;

