--liquibase formatted sql
-- Author: clive
-- Date: 13-Sep-2026
-- Description: Documents privileged operational APEX ownership receipts.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:plugin_apex_apps_receipt_annotations context:core labels:core stripComments:false runOnChange:true
alter table orac_core.plugin_apex_apps modify installation_receipt annotations (
  add if not exists display_name 'Privileged APEX installation receipt',
  add if not exists semantic_role 'audit'
);
