declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_constraints
   where owner = 'ORAC_HA'
     and constraint_name = 'HA_ENTITIES_OPTIONS_JSON';

  if l_count = 0
  then
    execute immediate q'~
alter table orac_ha.ha_entities
  add constraint ha_entities_options_json
  check (options is json)
    ~';
  end if;
end;
/
