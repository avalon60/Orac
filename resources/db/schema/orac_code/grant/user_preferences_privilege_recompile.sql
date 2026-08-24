--liquibase formatted sql
-- Author: clive
-- Date: 11-Aug-2026
-- Description: Recompiles preference objects invalidated by API-view privilege revokes.
-- Purpose: Leaves existing deployments valid after removing legacy direct DML grants.
-- Usage: Applied by the ORAC_CODE grant phase of the Core Liquibase controller.
-- Codex-assisted generated.
-- Codex SDK reviewability guardrails followed.

--changeset clive:compile_user_preferences_api_after_api_view_revokes context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from dba_objects where owner = 'ORAC_CODE' and object_name = 'USER_PREFERENCES_API' and object_type = 'PACKAGE' and status = 'INVALID';
alter package orac_code.user_preferences_api compile;
--rollback alter package orac_code.user_preferences_api compile;

--changeset clive:compile_user_preferences_api_body_after_api_view_revokes context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from dba_objects where owner = 'ORAC_CODE' and object_name = 'USER_PREFERENCES_API' and object_type = 'PACKAGE BODY' and status = 'INVALID';
alter package orac_code.user_preferences_api compile body;
--rollback alter package orac_code.user_preferences_api compile body;

--changeset clive:compile_orac_prefs_seed_body_after_api_view_revokes context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from dba_objects where owner = 'ORAC_CODE' and object_name = 'ORAC_PREFS_SEED' and object_type = 'PACKAGE BODY' and status = 'INVALID';
alter package orac_code.orac_prefs_seed compile body;
--rollback alter package orac_code.orac_prefs_seed compile body;

--changeset clive:compile_user_pref_v_iud_after_api_view_revokes context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from dba_objects where owner = 'ORAC_CODE' and object_name = 'USER_PREF_V_IUD' and object_type = 'TRIGGER' and status = 'INVALID';
alter trigger orac_code.user_pref_v_iud compile;
--rollback alter trigger orac_code.user_pref_v_iud compile;
