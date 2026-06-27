--liquibase formatted sql
declare
  l_count number;
begin
  select count(*) into l_count from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_JOB_PK';
  if l_count = 0 then
    execute immediate 'alter table orac_dropbox.drop_job add constraint drp_job_pk primary key (drop_job_id) using index orac_dropbox.drp_job_pk_idx';
  end if;
end;
/
