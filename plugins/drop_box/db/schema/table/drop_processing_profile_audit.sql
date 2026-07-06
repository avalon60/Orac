--liquibase formatted sql

--changeset clive:drop_box_profile_audit_add_created_by context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_DROPBOX' and table_name = 'DROP_PROCESSING_PROFILE' and column_name = 'CREATED_BY'
alter table orac_dropbox.drop_processing_profile add (
  created_by varchar2(128 char) default coalesce(sys_context('apex$session', 'app_user'), sys_context('userenv', 'proxy_user'), sys_context('userenv', 'session_user'), user) not null
);

--rollback alter table orac_dropbox.drop_processing_profile drop column created_by;

--changeset clive:drop_box_profile_audit_add_created_on context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_DROPBOX' and table_name = 'DROP_PROCESSING_PROFILE' and column_name = 'CREATED_ON'
alter table orac_dropbox.drop_processing_profile add (created_on timestamp with time zone default systimestamp not null);

--rollback alter table orac_dropbox.drop_processing_profile drop column created_on;

--changeset clive:drop_box_profile_audit_copy_created_at context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:2 select count(1) from all_tab_columns where owner = 'ORAC_DROPBOX' and table_name = 'DROP_PROCESSING_PROFILE' and column_name in ('CREATED_AT', 'CREATED_ON')
update orac_dropbox.drop_processing_profile
   set created_on = cast(created_at as timestamp with time zone)
 where created_at is not null;

--rollback empty

--changeset clive:drop_box_profile_audit_add_updated_by context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_DROPBOX' and table_name = 'DROP_PROCESSING_PROFILE' and column_name = 'UPDATED_BY'
alter table orac_dropbox.drop_processing_profile add (
  updated_by varchar2(128 char) default coalesce(sys_context('apex$session', 'app_user'), sys_context('userenv', 'proxy_user'), sys_context('userenv', 'session_user'), user) not null
);

--rollback alter table orac_dropbox.drop_processing_profile drop column updated_by;

--changeset clive:drop_box_profile_audit_add_updated_on context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_DROPBOX' and table_name = 'DROP_PROCESSING_PROFILE' and column_name = 'UPDATED_ON'
alter table orac_dropbox.drop_processing_profile add (updated_on timestamp with time zone default systimestamp not null);

--rollback alter table orac_dropbox.drop_processing_profile drop column updated_on;

--changeset clive:drop_box_profile_audit_copy_updated_at context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:2 select count(1) from all_tab_columns where owner = 'ORAC_DROPBOX' and table_name = 'DROP_PROCESSING_PROFILE' and column_name in ('UPDATED_AT', 'UPDATED_ON')
update orac_dropbox.drop_processing_profile
   set updated_on = cast(updated_at as timestamp with time zone)
 where updated_at is not null;

--rollback empty

--changeset clive:drop_box_profile_audit_add_row_version context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_DROPBOX' and table_name = 'DROP_PROCESSING_PROFILE' and column_name = 'ROW_VERSION'
alter table orac_dropbox.drop_processing_profile add (row_version number default 1 not null);

--rollback alter table orac_dropbox.drop_processing_profile drop column row_version;

--changeset clive:drop_box_profile_audit_drop_created_at context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_tab_columns where owner = 'ORAC_DROPBOX' and table_name = 'DROP_PROCESSING_PROFILE' and column_name = 'CREATED_AT'
alter table orac_dropbox.drop_processing_profile drop column created_at;

--rollback alter table orac_dropbox.drop_processing_profile add created_at timestamp;

--changeset clive:drop_box_profile_audit_drop_updated_at context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_tab_columns where owner = 'ORAC_DROPBOX' and table_name = 'DROP_PROCESSING_PROFILE' and column_name = 'UPDATED_AT'
alter table orac_dropbox.drop_processing_profile drop column updated_at;

--rollback alter table orac_dropbox.drop_processing_profile add updated_at timestamp;
