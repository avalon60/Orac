--liquibase formatted sql
-- Author: clive
-- Date: 13-Sep-2026
-- Description: Documents permanent scope and operational ownership semantics.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:knowledge_source_objects_scope_annotations context:core labels:core stripComments:false runOnChange:true
alter table orac_core.knowledge_source_objects modify knowledge_scope_id annotations (
  add if not exists semantic_role 'foreign_key',
  add if not exists rel_target 'orac_core.knowledge_scopes.knowledge_scope_id',
  add if not exists display_name 'Immutable source scope'
);
