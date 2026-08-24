--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Defines foreign keys for llm_input_media_types.

--changeset clive:create_constraint_orac_core_llm_mtype_dom_refval_fk1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_MTYPE_DOM_REFVAL_FK1';
alter table orac_core.llm_input_media_types add constraint llm_mtype_dom_refval_fk1
  foreign key (mime_match_kind_domain_code, mime_match_kind_ref_value_code)
  references orac_core.domain_ref_values (domain_code, ref_value_code);
--rollback alter table orac_core.llm_input_media_types drop constraint llm_mtype_dom_refval_fk1;

