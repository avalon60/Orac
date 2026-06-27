--liquibase formatted sql
declare
  l_count number;
begin
  select count(*) into l_count from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_JOB_LOCATION_FK';
  if l_count = 0 then
    execute immediate 'alter table orac_dropbox.drop_job add constraint drp_job_location_fk foreign key (drop_location_id) references orac_dropbox.drop_location (drop_location_id)';
  end if;
end;
/
