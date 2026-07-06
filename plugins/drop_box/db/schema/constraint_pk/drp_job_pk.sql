--liquibase formatted sql

--changeset clive:drop_box_constraint_pk_drp_job_pk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_JOB_PK'
alter table orac_dropbox.drop_job add constraint drp_job_pk primary key (drop_job_id) using index orac_dropbox.drp_job_pk_idx;

--rollback alter table orac_dropbox.drop_job drop constraint drp_job_pk;
