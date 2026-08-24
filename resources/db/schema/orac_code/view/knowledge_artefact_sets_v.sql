--liquibase formatted sql
-- Author: clive
-- Date: 2026-08-12
-- Description: Derives structural completeness for normalised artefact sets.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_view_orac_code_knowledge_artefact_sets_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_code.knowledge_artefact_sets_v as
select ext.extraction_id,
       count(art.artefact_id) member_count,
       sum(case when art.artefact_role_code in ('PRIMARY', 'MANIFEST') then 1 else 0 end) primary_member_count,
       sum(case when art.artefact_role_code = 'TABLE' then 1 else 0 end) table_member_count,
       min(art.member_ordinal) minimum_ordinal,
       max(art.member_ordinal) maximum_ordinal,
       case
         when count(art.artefact_id) > 0
          and sum(case when art.artefact_role_code in ('PRIMARY', 'MANIFEST') then 1 else 0 end) = 1
          and min(art.member_ordinal) = 1
          and max(art.member_ordinal) = count(art.artefact_id)
          and min(case when art.artefact_role_code in ('PRIMARY', 'MANIFEST') then art.content_sha256 end) = ext.text_sha256
          and (
            (sum(case when art.artefact_role_code = 'PRIMARY' then 1 else 0 end) = 1
             and sum(case when art.artefact_role_code = 'TABLE' then 1 else 0 end) = 0)
            or
            (sum(case when art.artefact_role_code = 'MANIFEST' then 1 else 0 end) = 1
             and sum(case when art.artefact_role_code = 'TABLE' then 1 else 0 end) > 0)
          )
         then 'Y'
         else 'N'
       end complete_yn
  from orac_api.knowledge_extractions_v ext
  left join orac_api.knowledge_artefacts_v art
    on art.extraction_id = ext.extraction_id
 group by ext.extraction_id, ext.text_sha256;
--rollback drop view orac_code.knowledge_artefact_sets_v;
