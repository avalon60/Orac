--liquibase formatted sql

--changeset clive:drop_box_expand_job_statuses context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(*) from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_JOB_STATUS_CK';
alter table orac_dropbox.drop_job drop constraint drp_job_status_ck;
alter table orac_dropbox.drop_job add constraint drp_job_status_ck
  check (status_code in (
    'queued',
    'processing',
    'handed_off',
    'completed',
    'failed',
    'quarantined',
    'deferred_prerequisite',
    'conversion_retry_wait',
    'skipped_duplicate',
    'skipped_disallowed_type',
    'skipped_too_large'
  ));
--rollback alter table orac_dropbox.drop_job drop constraint drp_job_status_ck; alter table orac_dropbox.drop_job add constraint drp_job_status_ck check (status_code in ('queued','processing','handed_off','completed','failed','quarantined','skipped_duplicate','skipped_disallowed_type','skipped_too_large'));
