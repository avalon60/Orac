--liquibase formatted sql
-- Author: clive
-- Date: 2026-08-12
-- Description: Grants the API layer minimal knowledge artefact table access.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:grant_orac_core_knowledge_artefacts_to_orac_api context:core labels:core stripComments:false runOnChange:true
grant select, insert on orac_core.knowledge_artefacts to orac_api with grant option;
--rollback revoke select, insert on orac_core.knowledge_artefacts from orac_api;
