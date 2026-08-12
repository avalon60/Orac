-- Author: Clive Bostock
-- Date: 11 Aug 2026
-- Description: Adds ORDS proxy grants for APEX-managed database users.
-- Codex-assisted modified.
-- Codex SDK reviewability guardrails followed.
--
-- Orac script to add grants to ords_public_user. This was a workaround as we couldn't
-- get the ORDS installer to behave.
--
-- 024-ords-post-install.sql
whenever sqlerror exit failure rollback

alter session set container=FREEPDB1;

alter user apex_public_user grant connect through ords_public_user;
alter user apex_rest_public_user grant connect through ords_public_user;
alter user apex_listener grant connect through ords_public_user;
