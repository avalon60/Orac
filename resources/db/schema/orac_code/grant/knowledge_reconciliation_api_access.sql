--liquibase formatted sql
-- Author: clive
-- Date: 2026-08-14
-- Description: Grants the Core runtime read-only reconciliation access.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:grant_execute_orac_code_knowledge_reconciliation_api_to_orac context:core labels:core stripComments:false runOnChange:true
grant execute on orac_code.knowledge_reconciliation_api to orac;
--rollback revoke execute on orac_code.knowledge_reconciliation_api from orac;
