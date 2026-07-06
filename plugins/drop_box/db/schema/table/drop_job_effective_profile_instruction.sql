--liquibase formatted sql

--changeset clive:drop_box_table_drop_job_effective_profile_instruction context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_DROPBOX' and table_name = 'DROP_JOB' and column_name = 'EFFECTIVE_PROFILE_INSTRUCTION'
alter table orac_dropbox.drop_job add (effective_profile_instruction clob);

--rollback alter table orac_dropbox.drop_job drop column effective_profile_instruction;
