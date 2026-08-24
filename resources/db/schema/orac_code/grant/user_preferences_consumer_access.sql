--liquibase formatted sql
-- Author: clive
-- Date: 11-Aug-2026
-- Description: Removes legacy direct DML access to the user preferences view.
-- Purpose: Keeps user preference writes on the package-authoritative API path.
-- Usage: Applied by the ORAC_CODE grant phase of the Core Liquibase controller.
-- Codex-assisted generated.
-- Codex SDK reviewability guardrails followed.

--changeset clive:revoke_insert_orac_code_user_preferences_v_from_orac_apx_pub context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from dba_tab_privs where owner = 'ORAC_CODE' and table_name = 'USER_PREFERENCES_V' and grantee = 'ORAC_APX_PUB' and privilege = 'INSERT';
revoke insert on orac_code.user_preferences_v from orac_apx_pub;
-- Direct consumer DML restoration is intentionally unsupported; writes use ORAC_CODE.USER_PREFERENCES_API.
--rollback select 1 from dual;

--changeset clive:revoke_update_orac_code_user_preferences_v_from_orac_apx_pub context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from dba_tab_privs where owner = 'ORAC_CODE' and table_name = 'USER_PREFERENCES_V' and grantee = 'ORAC_APX_PUB' and privilege = 'UPDATE';
revoke update on orac_code.user_preferences_v from orac_apx_pub;
-- Direct consumer DML restoration is intentionally unsupported; writes use ORAC_CODE.USER_PREFERENCES_API.
--rollback select 1 from dual;

--changeset clive:revoke_delete_orac_code_user_preferences_v_from_orac_apx_pub context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from dba_tab_privs where owner = 'ORAC_CODE' and table_name = 'USER_PREFERENCES_V' and grantee = 'ORAC_APX_PUB' and privilege = 'DELETE';
revoke delete on orac_code.user_preferences_v from orac_apx_pub;
-- Direct consumer DML restoration is intentionally unsupported; writes use ORAC_CODE.USER_PREFERENCES_API.
--rollback select 1 from dual;

--changeset clive:revoke_insert_orac_code_user_preferences_v_from_orac context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from dba_tab_privs where owner = 'ORAC_CODE' and table_name = 'USER_PREFERENCES_V' and grantee = 'ORAC' and privilege = 'INSERT';
revoke insert on orac_code.user_preferences_v from orac;
-- Direct consumer DML restoration is intentionally unsupported; writes use ORAC_CODE.USER_PREFERENCES_API.
--rollback select 1 from dual;

--changeset clive:revoke_update_orac_code_user_preferences_v_from_orac context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from dba_tab_privs where owner = 'ORAC_CODE' and table_name = 'USER_PREFERENCES_V' and grantee = 'ORAC' and privilege = 'UPDATE';
revoke update on orac_code.user_preferences_v from orac;
-- Direct consumer DML restoration is intentionally unsupported; writes use ORAC_CODE.USER_PREFERENCES_API.
--rollback select 1 from dual;

--changeset clive:revoke_delete_orac_code_user_preferences_v_from_orac context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from dba_tab_privs where owner = 'ORAC_CODE' and table_name = 'USER_PREFERENCES_V' and grantee = 'ORAC' and privilege = 'DELETE';
revoke delete on orac_code.user_preferences_v from orac;
-- Direct consumer DML restoration is intentionally unsupported; writes use ORAC_CODE.USER_PREFERENCES_API.
--rollback select 1 from dual;
