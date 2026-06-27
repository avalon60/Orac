--liquibase formatted sql
declare
  l_count number;
begin
  select count(*) into l_count from all_indexes where owner = 'ORAC_DROPBOX' and index_name = 'DRP_JOBE_PK_IDX';
  if l_count = 0 then
    execute immediate 'create unique index orac_dropbox.drp_jobe_pk_idx on orac_dropbox.drop_job_event (drop_job_event_id)';
  end if;
end;
/
