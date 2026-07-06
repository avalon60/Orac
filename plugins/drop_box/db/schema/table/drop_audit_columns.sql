--liquibase formatted sql

--changeset clive:drop_box_audit_backfill_drop_location_updated_by context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_tab_columns where owner = 'ORAC_DROPBOX' and table_name = 'DROP_LOCATION' and column_name = 'UPDATED_BY' and nullable = 'Y'
update orac_dropbox.drop_location
   set updated_by = coalesce(updated_by, created_by, sys_context('userenv', 'session_user'), user)
 where updated_by is null;
--rollback empty

--changeset clive:drop_box_audit_require_drop_location_updated_by context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_tab_columns where owner = 'ORAC_DROPBOX' and table_name = 'DROP_LOCATION' and column_name = 'UPDATED_BY' and nullable = 'Y'
alter table orac_dropbox.drop_location modify (updated_by varchar2(128 char) default coalesce(sys_context('apex$session', 'app_user'), sys_context('userenv', 'proxy_user'), sys_context('userenv', 'session_user'), user) not null);
--rollback alter table orac_dropbox.drop_location modify (updated_by null);

--changeset clive:drop_box_audit_backfill_drop_location_updated_on context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_tab_columns where owner = 'ORAC_DROPBOX' and table_name = 'DROP_LOCATION' and column_name = 'UPDATED_ON' and nullable = 'Y'
update orac_dropbox.drop_location
   set updated_on = coalesce(updated_on, created_on, systimestamp)
 where updated_on is null;
--rollback empty

--changeset clive:drop_box_audit_require_drop_location_updated_on context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_tab_columns where owner = 'ORAC_DROPBOX' and table_name = 'DROP_LOCATION' and column_name = 'UPDATED_ON' and nullable = 'Y'
alter table orac_dropbox.drop_location modify (updated_on timestamp with time zone default systimestamp not null);
--rollback alter table orac_dropbox.drop_location modify (updated_on null);

--changeset clive:drop_box_audit_backfill_drop_job_updated_by context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_tab_columns where owner = 'ORAC_DROPBOX' and table_name = 'DROP_JOB' and column_name = 'UPDATED_BY' and nullable = 'Y'
update orac_dropbox.drop_job
   set updated_by = coalesce(updated_by, created_by, sys_context('userenv', 'session_user'), user)
 where updated_by is null;
--rollback empty

--changeset clive:drop_box_audit_require_drop_job_updated_by context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_tab_columns where owner = 'ORAC_DROPBOX' and table_name = 'DROP_JOB' and column_name = 'UPDATED_BY' and nullable = 'Y'
alter table orac_dropbox.drop_job modify (updated_by varchar2(128 char) default coalesce(sys_context('apex$session', 'app_user'), sys_context('userenv', 'proxy_user'), sys_context('userenv', 'session_user'), user) not null);
--rollback alter table orac_dropbox.drop_job modify (updated_by null);

--changeset clive:drop_box_audit_backfill_drop_job_updated_on context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_tab_columns where owner = 'ORAC_DROPBOX' and table_name = 'DROP_JOB' and column_name = 'UPDATED_ON' and nullable = 'Y'
update orac_dropbox.drop_job
   set updated_on = coalesce(updated_on, created_on, systimestamp)
 where updated_on is null;
--rollback empty

--changeset clive:drop_box_audit_require_drop_job_updated_on context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_tab_columns where owner = 'ORAC_DROPBOX' and table_name = 'DROP_JOB' and column_name = 'UPDATED_ON' and nullable = 'Y'
alter table orac_dropbox.drop_job modify (updated_on timestamp with time zone default systimestamp not null);
--rollback alter table orac_dropbox.drop_job modify (updated_on null);
