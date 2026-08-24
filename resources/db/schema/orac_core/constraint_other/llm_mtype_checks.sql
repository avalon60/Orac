--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Enforces canonical MIME values and constrained wildcards.

--changeset clive:create_constraints_orac_core_llm_mtype_checks context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_MTYPE_CK1';
alter table orac_core.llm_input_media_types add (
  constraint llm_mtype_ck1 check (media_type = lower(media_type) and instr(media_type, ';') = 0),
  constraint llm_mtype_ck2 check (mime_match_kind_domain_code = 'MIME_MATCH_KIND'),
  constraint llm_mtype_ck3 check (
       (mime_match_kind_ref_value_code = 'EXACT'
        and regexp_like(media_type, '^[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+$')
        and instr(media_type, '*') = 0)
    or (mime_match_kind_ref_value_code = 'TYPE_WILDCARD'
        and regexp_like(media_type, '^[a-z0-9!#$&^_.+-]+/[*]$'))
  )
);
--rollback alter table orac_core.llm_input_media_types drop constraint llm_mtype_ck3; alter table orac_core.llm_input_media_types drop constraint llm_mtype_ck2; alter table orac_core.llm_input_media_types drop constraint llm_mtype_ck1;
