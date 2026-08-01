--liquibase formatted sql

--changeset clive:verify_dbms_crypto_access_for_orac_code context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(*) from dba_tab_privs where owner = 'SYS' and table_name = 'DBMS_CRYPTO' and grantee = 'ORAC_CODE' and privilege = 'EXECUTE'
select 1 from dual;
--rollback select 1 from dual;
