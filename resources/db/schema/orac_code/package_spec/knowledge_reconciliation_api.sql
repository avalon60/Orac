--liquibase formatted sql
-- Author: clive
-- Date: 2026-08-14
-- Description: Defines bounded read-only knowledge reconciliation inventories.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_package_spec_orac_code_knowledge_reconciliation_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package orac_code.knowledge_reconciliation_api
authid definer
as
  procedure open_registered_references(
    p_rows  out sys_refcursor,
    p_limit in number default 100001
  );

  procedure open_lineage_inventory(
    p_rows  out sys_refcursor,
    p_limit in number default 100001
  );
end knowledge_reconciliation_api;
/
--rollback drop package orac_code.knowledge_reconciliation_api;
