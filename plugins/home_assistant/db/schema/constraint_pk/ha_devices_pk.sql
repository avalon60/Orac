declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_constraints
   where owner = 'ORAC_HA'
     and constraint_name = 'HA_DEVICES_PK';

  if l_count = 0
  then
    execute immediate q'~
alter table orac_ha.ha_devices
  add constraint ha_devices_pk
  primary key (device_id)
  using index orac_ha.ha_devices_pk_idx
    ~';
  end if;
end;
/
