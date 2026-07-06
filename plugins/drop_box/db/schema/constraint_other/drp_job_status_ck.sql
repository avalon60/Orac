--liquibase formatted sql

--changeset clive:drop_box_constraint_other_drp_job_status_ck context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_JOB_STATUS_CK'
alter table orac_dropbox.drop_job add constraint drp_job_status_ck
  check (status_code in (
    'queued',
    'processing',
    'handed_off',
    'completed',
    'failed',
    'quarantined',
    'skipped_duplicate',
    'skipped_disallowed_type',
    'skipped_too_large'
  ));

--rollback alter table orac_dropbox.drop_job drop constraint drp_job_status_ck;
