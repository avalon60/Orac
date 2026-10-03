--liquibase formatted sql
-- Author: clive
-- Date: 13-Sep-2026
-- Description: Documents permanent scope and operational ownership semantics.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:plugin_registry_scope_annotations context:core labels:core stripComments:false runOnChange:true
alter table orac_core.plugin_registry modify knowledge_scope_id annotations (
  add if not exists semantic_role 'foreign_key',
  add if not exists rel_target 'orac_core.knowledge_scopes.knowledge_scope_id',
  add if not exists display_name 'Current installation knowledge scope'
);
