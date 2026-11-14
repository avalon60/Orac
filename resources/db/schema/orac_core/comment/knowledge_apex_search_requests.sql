--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 25-Oct-2026
-- Description: Documents transient plugin APEX search request fields.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:comment_orac_core_knowledge_apex_search_requests context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.knowledge_apex_search_requests is 'Transient Core queue for authenticated plugin APEX semantic searches; excerpts are read from current searchable chunks, not persisted here.';
--rollback comment on table orac_core.knowledge_apex_search_requests is '';

--changeset clive:comment_orac_core_kn_apxsr_result_refs context:core labels:core stripComments:false runOnChange:true
comment on column orac_core.knowledge_apex_search_requests.result_refs_json is 'Array of at most six document_id, document_version_id, chunk_id, chunk_no and score objects. No passage text.';
--rollback comment on column orac_core.knowledge_apex_search_requests.result_refs_json is '';
