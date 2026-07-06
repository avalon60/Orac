--liquibase formatted sql

--changeset clive:drop_box_constraint_fk_drp_jobe_job_fk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_JOBE_JOB_FK'
alter table orac_dropbox.drop_job_event add constraint drp_jobe_job_fk foreign key (drop_job_id) references orac_dropbox.drop_job (drop_job_id);

--rollback alter table orac_dropbox.drop_job_event drop constraint drp_jobe_job_fk;
