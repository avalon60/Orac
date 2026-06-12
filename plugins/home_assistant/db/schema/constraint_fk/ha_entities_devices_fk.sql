declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_constraints
   where owner = 'ORAC_HA'
     and constraint_name = 'HA_ENTITIES_DEVICES_FK';

  if l_count = 0
  then
    execute immediate q'~
alter table orac_ha.ha_entities
  add constraint ha_entities_devices_fk
  foreign key
  (
    device_id
  )
  references orac_ha.ha_devices
  (
    device_id
  )
  not deferrable
    ~';
  end if;
end;
/
