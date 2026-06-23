declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_tables
   where owner = 'ORAC_HA'
     and table_name = 'DEVICE_ALIASES';

  if l_count = 0
  then
    execute immediate q'~
      create table orac_ha.device_aliases
      (
        alias_name   varchar2(255 char) not null,
        entity_id   varchar2(255 char) not null,
        enabled_flag varchar2(1 char) default 'Y' not null,
        created_on   timestamp with time zone default systimestamp not null,
        updated_on   timestamp with time zone default systimestamp not null,
        row_version  number default 1 not null
      )
      logging
      no inmemory
    ~';
  end if;
end;
/
