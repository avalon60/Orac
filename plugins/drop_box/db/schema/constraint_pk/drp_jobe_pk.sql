--liquibase formatted sql
declare
  l_count number;
begin
  select count(*) into l_count from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_JOBE_PK';
  if l_count = 0 then
    execute immediate 'alter table orac_dropbox.drop_job_event add constraint drp_jobe_pk primary key (drop_job_event_id) using index orac_dropbox.drp_jobe_pk_idx';
  end if;
end;
/
