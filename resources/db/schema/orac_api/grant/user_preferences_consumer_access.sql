--liquibase formatted sql
-- Author: clive
-- Date: 11-Aug-2026
-- Description: Removes legacy direct DML access to the user preferences API view.

--changeset clive:revoke_insert_orac_api_user_preferences_v_from_orac_apx_pub context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from dba_tab_privs where owner = 'ORAC_API' and table_name = 'USER_PREFERENCES_V' and grantee = 'ORAC_APX_PUB' and privilege = 'INSERT';
revoke insert on orac_api.user_preferences_v from orac_apx_pub;
--rollback grant insert on orac_api.user_preferences_v to orac_apx_pub;

--changeset clive:revoke_update_orac_api_user_preferences_v_from_orac_apx_pub context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from dba_tab_privs where owner = 'ORAC_API' and table_name = 'USER_PREFERENCES_V' and grantee = 'ORAC_APX_PUB' and privilege = 'UPDATE';
revoke update on orac_api.user_preferences_v from orac_apx_pub;
--rollback grant update on orac_api.user_preferences_v to orac_apx_pub;

--changeset clive:revoke_delete_orac_api_user_preferences_v_from_orac_apx_pub context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from dba_tab_privs where owner = 'ORAC_API' and table_name = 'USER_PREFERENCES_V' and grantee = 'ORAC_APX_PUB' and privilege = 'DELETE';
revoke delete on orac_api.user_preferences_v from orac_apx_pub;
--rollback grant delete on orac_api.user_preferences_v to orac_apx_pub;

--changeset clive:revoke_insert_orac_api_user_preferences_v_from_orac context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from dba_tab_privs where owner = 'ORAC_API' and table_name = 'USER_PREFERENCES_V' and grantee = 'ORAC' and privilege = 'INSERT';
revoke insert on orac_api.user_preferences_v from orac;
--rollback grant insert on orac_api.user_preferences_v to orac;

--changeset clive:revoke_update_orac_api_user_preferences_v_from_orac context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from dba_tab_privs where owner = 'ORAC_API' and table_name = 'USER_PREFERENCES_V' and grantee = 'ORAC' and privilege = 'UPDATE';
revoke update on orac_api.user_preferences_v from orac;
--rollback grant update on orac_api.user_preferences_v to orac;

--changeset clive:revoke_delete_orac_api_user_preferences_v_from_orac context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from dba_tab_privs where owner = 'ORAC_API' and table_name = 'USER_PREFERENCES_V' and grantee = 'ORAC' and privilege = 'DELETE';
revoke delete on orac_api.user_preferences_v from orac;
--rollback grant delete on orac_api.user_preferences_v to orac;

--changeset clive:revoke_insert_orac_api_user_preferences_v_from_orac_code context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from dba_tab_privs where owner = 'ORAC_API' and table_name = 'USER_PREFERENCES_V' and grantee = 'ORAC_CODE' and privilege = 'INSERT';
revoke insert on orac_api.user_preferences_v from orac_code;
--rollback grant insert on orac_api.user_preferences_v to orac_code with grant option;

--changeset clive:revoke_update_orac_api_user_preferences_v_from_orac_code context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from dba_tab_privs where owner = 'ORAC_API' and table_name = 'USER_PREFERENCES_V' and grantee = 'ORAC_CODE' and privilege = 'UPDATE';
revoke update on orac_api.user_preferences_v from orac_code;
--rollback grant update on orac_api.user_preferences_v to orac_code with grant option;

--changeset clive:revoke_delete_orac_api_user_preferences_v_from_orac_code context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from dba_tab_privs where owner = 'ORAC_API' and table_name = 'USER_PREFERENCES_V' and grantee = 'ORAC_CODE' and privilege = 'DELETE';
revoke delete on orac_api.user_preferences_v from orac_code;
--rollback grant delete on orac_api.user_preferences_v to orac_code with grant option;
