--liquibase formatted sql
-- Author: clive
-- Date: 13-Sep-2026
-- Description: Documents permanent scope and operational ownership semantics.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:knowledge_scopes_plugin_attribution_annotations context:core labels:core stripComments:false runOnChange:true
alter table orac_core.knowledge_scopes modify plugin_id annotations (
  add if not exists semantic_role 'logical_reference',
  add if not exists display_name 'Immutable plugin attribution'
);

--changeset clive:knowledge_scopes_retirement_annotations context:core labels:core stripComments:false runOnChange:true
alter table orac_core.knowledge_scopes modify retired_on annotations (
  add if not exists semantic_role 'timestamp',
  add if not exists display_name 'Irreversible retirement'
);
