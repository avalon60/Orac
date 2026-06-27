--liquibase formatted sql
declare
  l_wrong_type_count number;
  l_row_count        number;
begin
  select count(*)
    into l_wrong_type_count
    from all_tab_columns
   where owner       = 'ORAC_DROPBOX'
     and table_name  = 'DROP_JOB'
     and column_name = 'SOURCE_MTIME'
     and data_type like 'TIMESTAMP%WITH TIME ZONE';

  if l_wrong_type_count = 1
  then
    select count(*)
      into l_row_count
      from orac_dropbox.drop_job;

    if l_row_count = 0
    then
      execute immediate 'alter table orac_dropbox.drop_job modify (source_mtime timestamp)';
    else
      raise_application_error(
        -20000,
        'Cannot convert ORAC_DROPBOX.DROP_JOB.SOURCE_MTIME while rows exist.'
      );
    end if;
  end if;
end;
/
