--liquibase formatted sql

--changeset clive:drop_box_constraint_pk_drp_jobe_pk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_JOBE_PK'
alter table orac_dropbox.drop_job_event add constraint drp_jobe_pk primary key (drop_job_event_id) using index orac_dropbox.drp_jobe_pk_idx;

--rollback alter table orac_dropbox.drop_job_event drop constraint drp_jobe_pk;
