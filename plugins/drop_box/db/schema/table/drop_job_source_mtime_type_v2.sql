--liquibase formatted sql

--changeset clive:drop_box_table_drop_job_source_mtime_type_v2_block_nonempty context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns col where col.owner = 'ORAC_DROPBOX' and col.table_name = 'DROP_JOB' and col.column_name = 'SOURCE_MTIME' and col.data_type like 'TIMESTAMP%WITH TIME ZONE' and exists (select 1 from orac_dropbox.drop_job)
update orac_dropbox.drop_job
   set source_mtime = source_mtime
 where 1 = 0;

--rollback empty

--changeset clive:drop_box_table_drop_job_source_mtime_type_v2_modify_column context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_tab_columns col where col.owner = 'ORAC_DROPBOX' and col.table_name = 'DROP_JOB' and col.column_name = 'SOURCE_MTIME' and col.data_type like 'TIMESTAMP%WITH TIME ZONE' and not exists (select 1 from orac_dropbox.drop_job)
alter table orac_dropbox.drop_job modify (source_mtime timestamp);

--rollback alter table orac_dropbox.drop_job modify (source_mtime timestamp with time zone);
