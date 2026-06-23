declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_constraints
   where owner = 'ORAC_HA'
     and constraint_name = 'HA_AREAS_ALIASES_JSON';

  if l_count = 0
  then
    execute immediate q'~
alter table orac_ha.ha_areas
  add constraint ha_areas_aliases_json
  check (aliases is json)
    ~';
  end if;
end;
/
