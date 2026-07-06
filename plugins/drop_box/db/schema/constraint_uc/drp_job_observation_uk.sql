--liquibase formatted sql

--changeset clive:drop_box_constraint_uc_drp_job_observation_uk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_JOB_OBSERVATION_UK'
alter table orac_dropbox.drop_job add constraint drp_job_observation_uk unique (drop_location_id, source_path, source_size_bytes, source_mtime);

--rollback alter table orac_dropbox.drop_job drop constraint drp_job_observation_uk;
