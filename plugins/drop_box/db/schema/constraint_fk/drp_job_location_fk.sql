--liquibase formatted sql

--changeset clive:drop_box_constraint_fk_drp_job_location_fk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_JOB_LOCATION_FK'
alter table orac_dropbox.drop_job add constraint drp_job_location_fk foreign key (drop_location_id) references orac_dropbox.drop_location (drop_location_id);

--rollback alter table orac_dropbox.drop_job drop constraint drp_job_location_fk;
