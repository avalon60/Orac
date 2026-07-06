--liquibase formatted sql
declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_tables
   where owner = 'ORAC_DROPBOX'
     and table_name = 'DROP_PROCESSING_PROFILE';

  if l_count = 0
  then
    execute immediate q'~
create table orac_dropbox.drop_processing_profile
(
  profile_code        varchar2(100 char) not null,
  display_name        varchar2(200 char) not null,
  description         varchar2(1000 char) not null,
  default_instruction clob not null,
  active_yn           varchar2(1 char) default 'Y' not null,
  system_yn           varchar2(1 char) default 'N' not null,
  sort_order          number default 100 not null,
  created_at          timestamp default systimestamp not null,
  updated_at          timestamp
)
logging
no inmemory
    ~';
  end if;
end;
/
