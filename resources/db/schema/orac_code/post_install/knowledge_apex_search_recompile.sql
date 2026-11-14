--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 25-Oct-2026
-- Description: Recompiles APEX search packages after Core searchable views exist.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:recompile_orac_code_knowledge_apex_search_api context:core labels:core stripComments:false runOnChange:true
alter package orac_code.knowledge_apex_search_api compile body;
--rollback alter package orac_code.knowledge_apex_search_api compile body;

--changeset clive:recompile_orac_code_knowledge_apex_search_worker_api context:core labels:core stripComments:false runOnChange:true
alter package orac_code.knowledge_apex_search_worker_api compile body;
--rollback alter package orac_code.knowledge_apex_search_worker_api compile body;
