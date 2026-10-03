--liquibase formatted sql
-- Author: clive
-- Date: 13-Sep-2026
-- Description: Documents permanent scope and operational ownership semantics.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:plugin_services_owner_annotations context:core labels:core stripComments:false runOnChange:true
alter table orac_core.plugin_services modify service_owner_type annotations (
  add if not exists semantic_role 'dimension',
  add if not exists display_name 'Core or plugin ownership'
);

--changeset clive:plugin_services_registration_annotations context:core labels:core stripComments:false runOnChange:true
alter table orac_core.plugin_services modify plugin_registry_id annotations (
  add if not exists semantic_role 'foreign_key',
  add if not exists rel_target 'orac_core.plugin_registry.plugin_registry_id'
);
