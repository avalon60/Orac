--liquibase formatted sql
-- Author: clive
-- Date: 2026-08-12
-- Description: Defines canonical UTF-8 identity validation for knowledge text.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_package_spec_orac_code_knowledge_text_identity_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package orac_code.knowledge_text_identity_api
authid definer
as
  procedure calculate_canonical_markdown(
    p_text      in clob,
    p_sha256    out varchar2,
    p_byte_size out number
  );
end knowledge_text_identity_api;
/
--rollback drop package orac_code.knowledge_text_identity_api;
