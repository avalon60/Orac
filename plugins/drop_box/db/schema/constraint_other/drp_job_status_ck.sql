--liquibase formatted sql
declare
  l_count number;
begin
  select count(*) into l_count from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_JOB_STATUS_CK';
  if l_count = 0 then
    execute immediate q'~
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
  ))
    ~';
  end if;
end;
/
