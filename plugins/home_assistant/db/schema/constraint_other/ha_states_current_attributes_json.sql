declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_constraints
   where owner = 'ORAC_HA'
     and constraint_name = 'HA_STATES_CURRENT_ATTRIBUTES_JSON';

  if l_count = 0
  then
    execute immediate q'~
alter table orac_ha.ha_states_current
  add constraint ha_states_current_attributes_json
  check (attributes is json)
    ~';
  end if;
end;
/
