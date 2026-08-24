--liquibase formatted sql
-- Author: clive
-- Date: 2026-08-12
-- Description: Implements insert-only access for immutable knowledge artefacts.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_package_body_orac_api_knowledge_artefacts_tapi context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package body orac_api.knowledge_artefacts_tapi
as
  procedure ins(
    p_row in out orac_api.knowledge_artefacts_v%rowtype
  )
  is
  begin
    insert into orac_api.knowledge_artefacts_v (
      extraction_id,
      artefact_role_code,
      media_type,
      content_sha256,
      storage_key,
      byte_size,
      logical_name,
      member_ordinal,
      metadata_json
    )
    values (
      p_row.extraction_id,
      p_row.artefact_role_code,
      p_row.media_type,
      p_row.content_sha256,
      p_row.storage_key,
      p_row.byte_size,
      p_row.logical_name,
      p_row.member_ordinal,
      p_row.metadata_json
    )
    returning artefact_id,
              created_by,
              created_on
         into p_row.artefact_id,
              p_row.created_by,
              p_row.created_on;
  end ins;
end knowledge_artefacts_tapi;
/
--rollback drop package body orac_api.knowledge_artefacts_tapi;
