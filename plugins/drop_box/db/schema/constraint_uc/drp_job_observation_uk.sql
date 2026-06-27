--liquibase formatted sql
declare
  l_count number;
begin
  select count(*) into l_count from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_JOB_OBSERVATION_UK';
  if l_count = 0 then
    execute immediate 'alter table orac_dropbox.drop_job add constraint drp_job_observation_uk unique (drop_location_id, source_path, source_size_bytes, source_mtime)';
  end if;
end;
/
