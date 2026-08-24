--liquibase formatted sql
-- Author: clive
-- Date: 2026-08-13
-- Description: Defines controlled legacy knowledge inspection and migration operations.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_package_spec_orac_code_knowledge_migration_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package orac_code.knowledge_migration_api
authid definer
as
  procedure open_backfill_candidates(
    p_candidates          out sys_refcursor,
    p_after_extraction_id in number default null,
    p_limit               in number default 100
  );

  procedure open_raw_locator_candidates(
    p_candidates                out sys_refcursor,
    p_after_document_version_id in number default null,
    p_limit                     in number default 100
  );

  function backfill_extraction(
    p_extraction_id   in number,
    p_output_set_json in clob
  ) return clob;

  function migrate_raw_locator(
    p_document_version_id in number,
    p_expected_locator    in varchar2,
    p_expected_sha256     in varchar2
  ) return clob;
end knowledge_migration_api;
/
--rollback drop package orac_code.knowledge_migration_api;
