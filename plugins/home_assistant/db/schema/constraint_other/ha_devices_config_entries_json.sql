declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_constraints
   where owner = 'ORAC_HA'
     and constraint_name = 'HA_DEVICES_CONFIG_ENTRIES_JSON';

  if l_count = 0
  then
    execute immediate q'~
alter table orac_ha.ha_devices
  add constraint ha_devices_config_entries_json
  check (config_entries is json)
    ~';
  end if;
end;
/
