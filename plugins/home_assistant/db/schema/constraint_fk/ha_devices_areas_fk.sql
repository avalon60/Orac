declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_constraints
   where owner = 'ORAC_HA'
     and constraint_name = 'HA_DEVICES_AREAS_FK';

  if l_count = 0
  then
    execute immediate q'~
alter table orac_ha.ha_devices
  add constraint ha_devices_areas_fk
  foreign key
  (
    area_id
  )
  references orac_ha.ha_areas
  (
    area_id
  )
  not deferrable
    ~';
  end if;
end;
/
