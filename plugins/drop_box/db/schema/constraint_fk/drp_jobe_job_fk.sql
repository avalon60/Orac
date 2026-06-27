--liquibase formatted sql
declare
  l_count number;
begin
  select count(*) into l_count from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_JOBE_JOB_FK';
  if l_count = 0 then
    execute immediate 'alter table orac_dropbox.drop_job_event add constraint drp_jobe_job_fk foreign key (drop_job_id) references orac_dropbox.drop_job (drop_job_id)';
  end if;
end;
/
