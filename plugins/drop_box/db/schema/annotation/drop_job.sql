--liquibase formatted sql
-- Author: clive
-- Date: 13-Sep-2026
-- Description: Documents permanent scope and operational ownership semantics.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:drop_box_job_scope_annotations context:plugin,prod labels:plugin,drop_box stripComments:false runOnChange:true
alter table orac_dropbox.drop_job modify target_knowledge_scope_id annotations (
  add if not exists display_name 'Queued knowledge scope',
  add if not exists semantic_role 'logical_reference',
  add if not exists rel_basis 'api:orac_plugin.knowledge_scope_validation_api.resolve_scope_id'
);

--changeset clive:drop_box_job_producer_scope_annotations context:plugin,prod labels:plugin,drop_box stripComments:false runOnChange:true
alter table orac_dropbox.drop_job modify producer_knowledge_scope_id annotations (
  add if not exists display_name 'Producer knowledge scope',
  add if not exists semantic_role 'logical_reference',
  add if not exists rel_basis 'api:orac_plugin.knowledge_scope_validation_api.resolve_scope_id'
);
