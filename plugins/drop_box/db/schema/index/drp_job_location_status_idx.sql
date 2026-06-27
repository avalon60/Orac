--liquibase formatted sql
declare
  l_count number;
begin
  select count(*) into l_count from all_indexes where owner = 'ORAC_DROPBOX' and index_name = 'DRP_JOB_LOCATION_STATUS_IDX';
  if l_count = 0 then
    execute immediate 'create index orac_dropbox.drp_job_location_status_idx on orac_dropbox.drop_job (drop_location_id, status_code)';
  end if;
end;
/
