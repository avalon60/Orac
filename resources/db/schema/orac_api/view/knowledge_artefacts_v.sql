--liquibase formatted sql
-- Author: clive
-- Date: 2026-08-12
-- Description: Exposes immutable knowledge artefacts through the API layer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_view_orac_api_knowledge_artefacts_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.knowledge_artefacts_v as
select artefact_id,
       extraction_id,
       artefact_role_code,
       media_type,
       content_sha256,
       storage_key,
       byte_size,
       logical_name,
       member_ordinal,
       metadata_json,
       created_by,
       created_on
  from orac_core.knowledge_artefacts;
--rollback drop view orac_api.knowledge_artefacts_v;
