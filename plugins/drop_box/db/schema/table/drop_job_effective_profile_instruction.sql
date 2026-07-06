--liquibase formatted sql
declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_tab_columns
   where owner = 'ORAC_DROPBOX'
     and table_name = 'DROP_JOB'
     and column_name = 'EFFECTIVE_PROFILE_INSTRUCTION';

  if l_count = 0
  then
    execute immediate
      'alter table orac_dropbox.drop_job add (effective_profile_instruction clob)';
  end if;
end;
/
