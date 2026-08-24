--liquibase formatted sql
-- Author: clive
-- Date: 2026-08-12
-- Description: Defines atomic normalised artefact output-set registration.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_package_spec_orac_code_knowledge_artefact_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package orac_code.knowledge_artefact_api
authid definer
as
  function register_output_set(
    p_extraction_id  in number,
    p_output_set_json in clob
  ) return clob;

  procedure assert_complete_set(
    p_extraction_id in number
  );

  function output_set_json(
    p_extraction_id in number
  ) return clob;
end knowledge_artefact_api;
/
--rollback drop package orac_code.knowledge_artefact_api;
