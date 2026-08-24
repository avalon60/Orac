--liquibase formatted sql
-- Author: clive
-- Date: 2026-08-12
-- Description: Defines insert-only table access for immutable knowledge artefacts.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_package_spec_orac_api_knowledge_artefacts_tapi context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package orac_api.knowledge_artefacts_tapi
authid definer
as
  procedure ins(
    p_row in out orac_api.knowledge_artefacts_v%rowtype
  );
end knowledge_artefacts_tapi;
/
--rollback drop package orac_api.knowledge_artefacts_tapi;
